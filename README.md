# Vero 🚀
> **The Open-Source "Cursor for Data" (Nao Labs Alternative)**

Vero is a headless analytics agent framework and AI-powered workspace built for data teams, analysts, and software engineers. It integrates directly with data warehouses (PostgreSQL, DuckDB, SQLite, Snowflake, BigQuery) to provide context-engineered Text-to-Insights, safe query sandboxes, an MCP (Model Context Protocol) endpoint for Cursor/Claude, and an interactive local Analytics Studio.

---

## 🏗️ Architecture

```
verodata/
├── vero-cli/       # Python core engine & CLI (managed with uv)
│   ├── vero/
│   │   ├── agent.py    # LLM reasoning & Text-to-SQL orchestrator
│   │   ├── cli.py      # Rich terminal commands (init, sync, chat, mcp, serve)
│   │   ├── config.py   # Workspace & dialect configuration
│   │   ├── context.py  # Markdown context engineering engine
│   │   ├── db.py       # Safe read-only multi-dialect query executor
│   │   ├── mcp.py      # FastMCP server for Cursor and Claude Desktop
│   │   └── server.py   # FastAPI server powering the web studio
│   └── .vero/          # Local context filesystem (RULES.md, schemas, skills)
│
└── vero-studio/    # Local web UI (React + Vite + TypeScript + Vanilla CSS)
    └── src/        # Interactive Chat, Schema Explorer & Recharts visualizer
```

---

## ⚡ Quickstart

### 1. Requirements
* [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
* Node.js 18+ and npm

### 2. Set Up `vero-cli`
```bash
cd vero-cli

# Initialize project & sample eCommerce database
uv run vero init

# Introspect schemas & generate context files
uv run vero sync

# Launch the terminal chat loop
uv run vero chat
```

### 3. Connect to Cursor / Claude Desktop (MCP)
Vero includes a built-in FastMCP server. Run:
```bash
uv run vero mcp
```
Or configure your Cursor or Claude Desktop `mcpServers`:
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
