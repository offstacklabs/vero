import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from pathlib import Path
import uvicorn
import json
import sqlite3

from vero.config import VeroConfig, DatabaseConfig
from vero.context import ContextEngine
from vero.db import DatabaseManager
from vero.agent import VeroAgent
from vero.mcp import run_mcp_server

app = typer.Typer(
    name="vero",
    help="Vero: Open-Source Headless Analytics Agent Framework (Cursor for Data)",
    add_completion=False
)
console = Console()

@app.command()
def init(
    dialect: str = typer.Option("sqlite", "--dialect", "-d", help="Database dialect (sqlite, duckdb, postgres, snowflake)"),
    conn: str = typer.Option("sqlite:///vero_sample.db", "--conn", "-c", help="Connection string")
):
    """Initializes the .vero context directory and configuration."""
    console.print(Panel.fit("[bold cyan]Initializing Vero Project[/bold cyan]", border_style="cyan"))

    config = VeroConfig(
        database=DatabaseConfig(dialect=dialect, connection_string=conn)
    )
    config.save()
    console.print("[green]✓ Created[/green] .vero/config.yaml")

    engine = ContextEngine()
    engine.initialize_workspace()
    console.print("[green]✓ Initialized[/green] .vero/ context directory and RULES.md")

    # If using default sample sqlite, seed sample ecommerce tables
    if "vero_sample.db" in conn:
        _seed_sample_db("vero_sample.db")
        console.print("[green]✓ Seeded[/green] sample eCommerce database at vero_sample.db")

    console.print("\n[bold green]Ready![/bold green] Run [cyan]vero sync[/cyan] to introspect schemas.")

def _seed_sample_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            signup_date TEXT,
            plan TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount REAL,
            status TEXT,
            created_at TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        );
    """)
    cur.execute("DELETE FROM customers;")
    cur.execute("DELETE FROM orders;")

    customers = [
        (1, "Alice Smith", "alice@example.com", "2024-01-15", "enterprise"),
        (2, "Bob Jones", "bob@example.com", "2024-02-01", "pro"),
        (3, "Charlie Brown", "charlie@example.com", "2024-03-10", "starter"),
        (4, "Diana Prince", "diana@example.com", "2024-03-22", "pro"),
    ]
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers)

    orders = [
        (101, 1, 1200.00, "completed", "2024-03-01"),
        (102, 1, 2400.00, "completed", "2024-03-15"),
        (103, 2, 450.00, "completed", "2024-03-16"),
        (104, 3, 50.00, "refunded", "2024-03-18"),
        (105, 4, 399.00, "completed", "2024-03-25"),
    ]
    cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)
    conn.commit()
    conn.close()

@app.command()
def sync():
    """Introspects connected database and synchronizes schemas to .vero/schemas/."""
    console.print(Panel.fit("[bold cyan]Syncing Database Schemas[/bold cyan]", border_style="cyan"))
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)

    try:
        schema_info = db.introspect_schema()
        engine = ContextEngine()
        engine.sync_schemas(schema_info)

        table = Table(title="Synced Tables", show_header=True, header_style="bold magenta")
        table.add_column("Table Name", style="cyan")
        table.add_column("Columns", style="green")
        table.add_column("Foreign Keys", style="yellow")

        for name, details in schema_info.items():
            col_count = len(details["columns"])
            fk_count = len(details.get("foreign_keys", []))
            table.add_row(name, str(col_count), str(fk_count))

        console.print(table)
        console.print(f"[bold green]✓ Successfully synced {len(schema_info)} tables to .vero/schemas/[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Sync Failed:[/bold red] {str(e)}")

@app.command()
def chat():
    """Launches the Vero Interactive Analytics Terminal."""
    console.print(Panel.fit("[bold cyan]Vero Analytics Agent[/bold cyan] (Type 'exit' to quit)", border_style="cyan"))
    agent = VeroAgent()

    while True:
        try:
            question = console.input("\n[bold yellow]Ask Vero > [/bold yellow]").strip()
            if not question:
                continue
            if question.lower() in ["exit", "quit", "q"]:
                console.print("[dim]Goodbye![/dim]")
                break

            with console.status("[bold green]Generating SQL and reasoning...[/bold green]"):
                res = agent.ask(question)

            if res.get("thought"):
                console.print(f"[dim italic]Reasoning: {res['thought']}[/dim italic]")

            if res.get("sql"):
                console.print(Panel(f"[bold green]Generated SQL:[/bold green]\n{res['sql']}", border_style="green"))

            if res.get("explanation"):
                console.print(f"[bold white]{res['explanation']}[/bold white]")

            if res.get("error"):
                console.print(f"[bold red]Execution Error:[/bold red] {res['error']}")
            elif res.get("data"):
                data = res["data"]
                table = Table(show_header=True, header_style="bold cyan")
                for col in data["columns"]:
                    table.add_column(str(col))
                for row in data["rows"]:
                    table.add_row(*[str(cell) for cell in row])
                console.print(table)
                console.print(f"[dim]Returned {data['row_count']} row(s)[/dim]")

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

@app.command()
def mcp(transport: str = typer.Option("stdio", "--transport", "-t", help="stdio or sse")):
    """Starts the Vero Model Context Protocol (MCP) server for Cursor/Claude."""
    run_mcp_server(transport=transport)

@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p")
):
    """Starts the Vero Studio backend server."""
    console.print(Panel.fit(f"[bold cyan]Starting Vero Studio Server on http://{host}:{port}[/bold cyan]", border_style="cyan"))
    uvicorn.run("vero.server:app", host=host, port=port, reload=True)

if __name__ == "__main__":
    app()
