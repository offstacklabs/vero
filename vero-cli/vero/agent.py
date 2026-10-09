import json
import re
import time
from typing import Dict, Any, Optional, List
import litellm
from vero.context import ContextEngine
from vero.db import DatabaseManager
from vero.config import VeroConfig

class VeroAgent:
    def __init__(self, config: Optional[VeroConfig] = None):
        self.config = config or VeroConfig.load()
        self.context_engine = ContextEngine()
        self.db_manager = DatabaseManager(
            dialect=self.config.database.dialect,
            connection_string=self.config.database.connection_string
        )
        self.history: List[Dict[str, str]] = []

    def generate_sql(self, question: str) -> Dict[str, Any]:
        """Translates natural language question into valid SQL and explanation."""
        context = self.context_engine.get_full_context_prompt(query_hint=question)
        dialect = self.config.database.dialect

        system_prompt = (
            f"You are Vero, an expert AI analytics engineer and 'Cursor for Data'.\n"
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
            # Clean possible markdown wrap
            cleaned = re.sub(r"^```json\s*", "", raw_content.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed = json.loads(cleaned)
            
            # Save to history for multi-turn
            self.history.append({"role": "user", "content": f"Question: {question}"})
            self.history.append({"role": "assistant", "content": raw_content.strip()})
            
            # Keep history manageable (last 10 turns = 20 messages)
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

    def ask(self, question: str, execute: bool = True) -> Dict[str, Any]:
        """End-to-end question answering: translates to SQL, executes against DB, and returns results."""
        plan = self.generate_sql(question)
        sql = plan.get("sql")

        result = {
            "question": question,
            "thought": plan.get("thought", ""),
            "sql": sql,
            "explanation": plan.get("explanation", ""),
            "suggested_visualization": plan.get("suggested_visualization", "table"),
            "tables_used": plan.get("tables_used", []),
            "suggested_followups": plan.get("suggested_followups", []),
            "data": None,
            "duration_ms": 0,
            "error": plan.get("error")
        }

        if execute and sql and not result["error"]:
            start_time = time.time()
            try:
                query_result = self.db_manager.execute_query(sql)
                result["data"] = query_result
                result["duration_ms"] = round((time.time() - start_time) * 1000, 1)
            except Exception as e:
                # Basic Reflection / Self-healing loop
                result["error"] = str(e)
                self.history.append({"role": "user", "content": f"The query failed with error: {str(e)}. Please fix the SQL."})

        return result
