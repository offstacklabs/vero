import json
import re
from typing import Dict, Any, Optional
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

    def generate_sql(self, question: str) -> Dict[str, Any]:
        """Translates natural language question into valid SQL and explanation."""
        context = self.context_engine.get_full_context_prompt()
        dialect = self.config.database.dialect

        system_prompt = (
            f"You are Vero, an expert AI analytics engineer and 'Cursor for Data'.\n"
            f"Your database dialect is: {dialect}.\n"
            f"You must translate business questions into accurate, high-performance, and safe SQL queries.\n\n"
            f"Context:\n{context}\n\n"
            f"Instructions:\n"
            f"1. Only return valid JSON with keys: 'thought' (your reasoning), 'sql' (executable SQL query), 'explanation' (concise description of the query for the user), and 'suggested_visualization' ('bar', 'line', 'pie', 'table').\n"
            f"2. Never generate mutation operations (INSERT, UPDATE, DELETE, DROP, ALTER).\n"
            f"3. Strictly adhere to foreign keys and schema definitions provided in the context.\n"
            f"4. Output purely the JSON object without markdown fences or additional text."
        )

        user_prompt = f"Question: {question}"

        try:
            response = litellm.completion(
                model=self.config.llm.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.llm.temperature,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content
            # Clean possible markdown wrap
            cleaned = re.sub(r"^```json\s*", "", raw_content.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed = json.loads(cleaned)
            return parsed
        except Exception as e:
            return {
                "thought": "Error contacting LLM or parsing output.",
                "sql": None,
                "explanation": f"LLM Error: {str(e)}",
                "suggested_visualization": "table"
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
            "data": None,
            "error": None
        }

        if execute and sql:
            try:
                query_result = self.db_manager.execute_query(sql)
                result["data"] = query_result
            except Exception as e:
                result["error"] = str(e)

        return result
