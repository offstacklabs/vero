import json
import re
import time
from typing import Dict, Any, Optional, List
import litellm
from vero.context import ContextEngine
from vero.db import DatabaseManager
from vero.config import VeroConfig

class VeroAgent:
    def __init__(
        self,
        config: Optional[VeroConfig] = None,
        context_engine: Optional[ContextEngine] = None,
        db_manager: Optional[DatabaseManager] = None
    ):
        self.config = config or VeroConfig.load()
        self.context_engine = context_engine or ContextEngine()
        self.db_manager = db_manager or DatabaseManager(
            dialect=self.config.database.dialect,
            connection_string=self.config.database.connection_string
        )
        self.history: List[Dict[str, str]] = []

    def generate_sql(self, question: str) -> Dict[str, Any]:
        """Translates natural language question into valid SQL and explanation."""
        context = self.context_engine.get_full_context_prompt(query_hint=question)
        dialect = self.config.database.dialect

        system_prompt = (
            f"You are Vero, an expert AI analytics engineer and headless data intelligence agent.\n"
            f"Your database dialect is: {dialect}.\n"
            f"You must translate business questions into accurate, high-performance, and safe SQL queries.\n\n"
            f"Context:\n{context}\n\n"
            f"Instructions:\n"
            f"1. Only return valid JSON with keys: 'thought' (detailed reasoning), 'sql' (executable SQL query), 'explanation' (user-facing description), 'suggested_visualization' ('bar', 'line', 'pie', 'table'), 'tables_used' (list of table names), and 'suggested_followups' (list of 2-3 short follow-up questions to explore next).\n"
            f"2. Never generate mutation operations (INSERT, UPDATE, DELETE, DROP, ALTER).\n"
            f"3. Strictly adhere to foreign keys and schema definitions provided in the context.\n"
            f"4. Output purely the JSON object without markdown fences or additional text."
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": f"Question: {question}"})

        try:
            response = litellm.completion(
                model=self.config.llm.model,
                messages=messages,
                temperature=self.config.llm.temperature,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content
            cleaned = re.sub(r"^```json\s*", "", raw_content.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed = json.loads(cleaned)
            
            # Save to history for multi-turn
            self.history.append({"role": "user", "content": f"Question: {question}"})
            self.history.append({"role": "assistant", "content": raw_content.strip()})
            
            if len(self.history) > 20:
                self.history = self.history[-20:]

            return parsed
        except Exception as e:
            return {
                "thought": "Error contacting LLM or parsing output.",
                "sql": None,
                "explanation": f"LLM Error: {str(e)}",
                "suggested_visualization": "table",
                "tables_used": [],
                "suggested_followups": [],
                "error": str(e)
            }

    def reflect_and_heal(
        self,
        question: str,
        failed_sql: str,
        error_message: str,
        attempt: int
    ) -> Dict[str, Any]:
        """
        Reflexion Loop: Feeds compiler or runtime database error back to the LLM
        along with the failed SQL query to autonomously repair it.
        """
        context = self.context_engine.get_full_context_prompt(query_hint=question)
        dialect = self.config.database.dialect

        system_prompt = (
            f"You are Vero, an expert AI analytics engineer and headless data intelligence agent.\n"
            f"Your database dialect is: {dialect}.\n"
            f"A previously generated SQL query failed validation or execution.\n"
            f"You must analyze the exact compiler/database error and output a corrected, valid SQL query.\n\n"
            f"Context:\n{context}\n\n"
            f"Instructions:\n"
            f"1. Only return valid JSON with keys: 'thought' (explanation of what caused the error and how you fixed it), 'sql' (corrected executable SQL query), 'explanation' (user-facing description), 'suggested_visualization' ('bar', 'line', 'pie', 'table'), 'tables_used' (list of table names), and 'suggested_followups' (list of 2-3 follow-ups).\n"
            f"2. Never generate mutation operations (INSERT, UPDATE, DELETE, DROP, ALTER).\n"
            f"3. Output purely the JSON object without markdown fences or additional text."
        )

        heal_prompt = (
            f"Original Question: {question}\n\n"
            f"Failed SQL (Attempt {attempt}):\n```sql\n{failed_sql}\n```\n\n"
            f"Exact Database Error:\n{error_message}\n\n"
            f"Analyze why this query failed against {dialect} and return the fixed query."
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": heal_prompt})

        try:
            response = litellm.completion(
                model=self.config.llm.model,
                messages=messages,
                temperature=self.config.llm.temperature,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content
            cleaned = re.sub(r"^```json\s*", "", raw_content.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed = json.loads(cleaned)
            
            # Record healed attempt to history
            self.history.append({"role": "user", "content": f"Query failed: {error_message}"})
            self.history.append({"role": "assistant", "content": raw_content.strip()})
            
            if len(self.history) > 20:
                self.history = self.history[-20:]

            return parsed
        except Exception as e:
            return {
                "thought": f"Failed during reflection retry {attempt}.",
                "sql": None,
                "explanation": f"Reflection error: {str(e)}",
                "suggested_visualization": "table",
                "tables_used": [],
                "suggested_followups": [],
                "error": str(e)
            }

    def ask(self, question: str, execute: bool = True, max_retries: int = 2) -> Dict[str, Any]:
        """
        End-to-end question answering with autonomous self-healing reflection loop:
        1. Draft candidate SQL
        2. Validate AST safety
        3. Execute against database
        4. If error occurs, autonomously reflect and heal (up to max_retries)
        """
        plan = self.generate_sql(question)
        reflection_steps = []
        attempt = 0

        result = {
            "question": question,
            "thought": plan.get("thought", ""),
            "sql": plan.get("sql"),
            "explanation": plan.get("explanation", ""),
            "suggested_visualization": plan.get("suggested_visualization", "table"),
            "tables_used": plan.get("tables_used", []),
            "suggested_followups": plan.get("suggested_followups", []),
            "data": None,
            "duration_ms": 0,
            "reflection_steps": reflection_steps,
            "error": plan.get("error")
        }

        while attempt <= max_retries:
            sql = plan.get("sql")
            if not sql:
                result["error"] = plan.get("error") or "No SQL generated"
                break

            # Step 1: AST Safety Check
            if not self.db_manager.is_safe_query(sql):
                err_msg = "AST validation failed: Query contains mutation operations or syntax error."
                reflection_steps.append({
                    "attempt": attempt + 1,
                    "failed_sql": sql,
                    "error": err_msg,
                    "thought": plan.get("thought", "")
                })
                if attempt < max_retries:
                    attempt += 1
                    plan = self.reflect_and_heal(question, sql, err_msg, attempt)
                    continue
                else:
                    result["error"] = err_msg
                    result["sql"] = sql
                    break

            if not execute:
                result["sql"] = sql
                result["thought"] = plan.get("thought", "")
                result["explanation"] = plan.get("explanation", "")
                break

            # Step 2: Database Execution
            start_time = time.time()
            try:
                query_result = self.db_manager.execute_query(sql)
                result["data"] = query_result
                result["duration_ms"] = round((time.time() - start_time) * 1000, 1)
                result["sql"] = sql
                result["thought"] = plan.get("thought", "")
                result["explanation"] = plan.get("explanation", "")
                result["suggested_visualization"] = plan.get("suggested_visualization", "table")
                result["tables_used"] = plan.get("tables_used", [])
                result["suggested_followups"] = plan.get("suggested_followups", [])
                result["error"] = None
                break  # Query succeeded!
            except Exception as e:
                err_msg = str(e)
                reflection_steps.append({
                    "attempt": attempt + 1,
                    "failed_sql": sql,
                    "error": err_msg,
                    "thought": plan.get("thought", "")
                })
                if attempt < max_retries:
                    attempt += 1
                    plan = self.reflect_and_heal(question, sql, err_msg, attempt)
                else:
                    result["error"] = err_msg
                    result["sql"] = sql
                    break

        return result

    def ask_stream(self, question: str, execute: bool = True, max_retries: int = 2):
        """
        Streaming generator that emits real-time agent execution stages,
        reflection actions, and the final synthesized result.
        """
        yield {
            "type": "stage",
            "stage": "retrieval",
            "message": "Grounding warehouse schemas & semantic metrics..."
        }

        yield {
            "type": "stage",
            "stage": "generating",
            "message": "Analyzing question & drafting candidate SQL..."
        }

        plan = self.generate_sql(question)
        reflection_steps = []
        attempt = 0

        result = {
            "question": question,
            "thought": plan.get("thought", ""),
            "sql": plan.get("sql"),
            "explanation": plan.get("explanation", ""),
            "suggested_visualization": plan.get("suggested_visualization", "table"),
            "tables_used": plan.get("tables_used", []),
            "suggested_followups": plan.get("suggested_followups", []),
            "data": None,
            "duration_ms": 0,
            "reflection_steps": reflection_steps,
            "error": plan.get("error")
        }

        while attempt <= max_retries:
            sql = plan.get("sql")
            if not sql:
                result["error"] = plan.get("error") or "No SQL generated"
                break

            yield {
                "type": "stage",
                "stage": "ast_validation",
                "message": f"Validating AST safety on {self.config.database.dialect} dialect...",
                "sql": sql
            }

            if not self.db_manager.is_safe_query(sql):
                err_msg = "AST validation failed: Query contains mutation operations or syntax error."
                reflection_steps.append({
                    "attempt": attempt + 1,
                    "failed_sql": sql,
                    "error": err_msg,
                    "thought": plan.get("thought", "")
                })
                if attempt < max_retries:
                    attempt += 1
                    yield {
                        "type": "stage",
                        "stage": "reflecting",
                        "attempt": attempt,
                        "error": err_msg,
                        "message": f"AST rejection intercepted. Autonomously repairing (attempt {attempt})..."
                    }
                    plan = self.reflect_and_heal(question, sql, err_msg, attempt)
                    continue
                else:
                    result["error"] = err_msg
                    result["sql"] = sql
                    break

            if not execute:
                result["sql"] = sql
                result["thought"] = plan.get("thought", "")
                result["explanation"] = plan.get("explanation", "")
                break

            yield {
                "type": "stage",
                "stage": "executing",
                "message": f"Executing query against {self.config.database.dialect} sandbox...",
                "sql": sql
            }

            start_time = time.time()
            try:
                query_result = self.db_manager.execute_query(sql)
                result["data"] = query_result
                result["duration_ms"] = round((time.time() - start_time) * 1000, 1)
                result["sql"] = sql
                result["thought"] = plan.get("thought", "")
                result["explanation"] = plan.get("explanation", "")
                result["suggested_visualization"] = plan.get("suggested_visualization", "table")
                result["tables_used"] = plan.get("tables_used", [])
                result["suggested_followups"] = plan.get("suggested_followups", [])
                result["error"] = None
                break
            except Exception as e:
                err_msg = str(e)
                reflection_steps.append({
                    "attempt": attempt + 1,
                    "failed_sql": sql,
                    "error": err_msg,
                    "thought": plan.get("thought", "")
                })
                if attempt < max_retries:
                    attempt += 1
                    yield {
                        "type": "stage",
                        "stage": "reflecting",
                        "attempt": attempt,
                        "error": err_msg,
                        "message": f"Database compiler error intercepted. Autonomously repairing (attempt {attempt})..."
                    }
                    plan = self.reflect_and_heal(question, sql, err_msg, attempt)
                else:
                    result["error"] = err_msg
                    result["sql"] = sql
                    break

        yield {
            "type": "complete",
            "result": result
        }
