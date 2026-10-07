import json
from fastmcp import FastMCP
from vero.agent import VeroAgent
from vero.config import VeroConfig
from vero.db import DatabaseManager
from vero.context import ContextEngine

# Initialize FastMCP Server
mcp = FastMCP(
    name="Vero",
)

@mcp.tool()
def get_schemas() -> str:
    """Returns the Markdown context of all registered database schemas and business rules."""
    engine = ContextEngine()
    return engine.get_full_context_prompt()

@mcp.tool()
def execute_sql(sql_query: str) -> str:
    """Executes a safe read-only SQL query against the connected database and returns results in JSON."""
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    try:
        res = db.execute_query(sql_query)
        return json.dumps(res, indent=2, default=str)
    except Exception as e:
        return f"Error executing SQL: {str(e)}"

@mcp.tool()
def ask_vero(question: str) -> str:
    """Translates a natural language question into SQL, runs it against the warehouse, and returns an analytical answer with data."""
    agent = VeroAgent()
    res = agent.ask(question)
    return json.dumps(res, indent=2, default=str)

def run_mcp_server(transport: str = "stdio"):
    """Starts the Vero MCP Server."""
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse")

if __name__ == "__main__":
    run_mcp_server()
