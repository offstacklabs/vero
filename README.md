# Vero 🚀
> **Open-Source Headless Analytics Agent Framework & AI Data Workspace (Nao Labs Alternative)**

Vero is a headless analytics agent framework and AI-powered workspace built for data teams, analysts, and software engineers. It integrates directly with data warehouses (PostgreSQL, Snowflake, BigQuery, DuckDB, SQLite) to provide context-engineered Text-to-Insights, safe query sandboxes, a Model Context Protocol (MCP) endpoint for any AI editor or agent, and an interactive local Analytics Studio.

---

## 🏗️ Architecture

```
verodata/
├── vero-cli/       # Python core engine & CLI (managed with uv)
│   ├── vero/
│   │   ├── agent.py    # LLM reasoning, reflection & Text-to-SQL orchestrator
│   │   ├── cli.py      # Rich terminal commands (init, sync, doctor, run, chat, mcp, serve)
│   │   ├── config.py   # Workspace & dialect configuration
│   │   ├── context.py  # Context engineering engine (in-memory + local .vero/)
│   │   ├── db.py       # Safe read-only multi-dialect query executor
│   │   ├── mcp.py      # FastMCP server for any MCP-compatible client
│   │   └── server.py   # FastAPI server powering the web studio
│   └── .vero/          # Local context filesystem (RULES.md, schemas, metrics.yaml)
│
└── vero-studio/    # Local web UI (React + Vite + TypeScript + Vanilla CSS)
    └── src/        # Interactive Copilot, SQL Studio, Schema Explorer & Visualizer
```

---

## ⚡ Quickstart

### 1. Requirements
* [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
* Node.js 18+ and npm

### 2. Set Up `vero-cli`
```bash
cd vero-cli

# Initialize project configuration
uv run vero init

# Introspect schemas & generate context files
uv run vero sync

# Launch the terminal chat loop
uv run vero chat
```

### 3. Connect via MCP (Model Context Protocol)
Vero includes a built-in FastMCP server compatible with any MCP client (Claude Desktop, Cursor, Zed, Windsurf, or custom agent frameworks):
```bash
uv run vero mcp
```
Example client configuration (`mcpServers`):
```json
{
  "mcpServers": {
    "vero": {
      "command": "uv",
      "args": ["--directory", "/path/to/verodata/vero-cli", "run", "vero", "mcp"]
    }
  }
}
```

### 4. Launch Vero Studio (Web UI)
Start the backend server:
```bash
cd vero-cli
uv run vero serve --port 8000
```

Start the frontend:
```bash
cd ../vero-studio
npm run dev
```
Navigate to `http://localhost:5173` to explore your database schemas, converse with the agent, inspect generated SQL, and view interactive charts!
