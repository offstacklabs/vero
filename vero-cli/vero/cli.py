import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from pathlib import Path
import uvicorn
import json
import sqlite3
import sqlalchemy

from vero.config import VeroConfig, DatabaseConfig
from vero.context import ContextEngine
from vero.db import DatabaseManager
from vero.agent import VeroAgent
from vero.mcp import run_mcp_server

app = typer.Typer(
    name="vero",
    help="Vero: Open-Source Headless Analytics Agent Framework & AI Data Workspace",
    add_completion=False
)
console = Console()

@app.command()
def init(
    dialect: str = typer.Option("postgres", "--dialect", "-d", help="Database dialect (postgres, snowflake, bigquery, duckdb)"),
    conn: str = typer.Option("postgresql://user:password@localhost:5432/vero_db", "--conn", "-c", help="Connection string")
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
    console.print("[green]✓ Initialized[/green] .vero/ context directory (schemas, metrics, rules)")

    console.print("\n[bold green]Ready![/bold green] Update config.yaml with your credentials, then run [cyan]vero sync[/cyan] to introspect schemas.")

@app.command()
def doctor():
    """Diagnoses the environment and checks database connectivity."""
    console.print(Panel.fit("[bold cyan]Vero Doctor - Environment Check[/bold cyan]", border_style="cyan"))
    
    config = VeroConfig.load()
    console.print(f"Loaded config from workspace: [bold]{VeroConfig.get_workspace_root()}[/bold]")
    console.print(f"Dialect: [green]{config.database.dialect}[/green]")
    
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    
    try:
        with console.status("Testing database connection..."):
            db.execute_query("SELECT 1")
        console.print("[bold green]✓ Database Connection Successful[/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ Database Connection Failed:[/bold red] {str(e)}")

@app.command()
def run(query: str):
    """Executes a raw SQL query directly against the connected warehouse."""
    config = VeroConfig.load()
    db = DatabaseManager(dialect=config.database.dialect, connection_string=config.database.connection_string)
    
    try:
        with console.status("Executing query..."):
            data = db.execute_query(query)
            
        table = Table(show_header=True, header_style="bold cyan")
        for col in data["columns"]:
            table.add_column(str(col))
        for row in data["rows"]:
            table.add_row(*[str(cell) for cell in row])
        console.print(table)
        console.print(f"[dim]Returned {data['row_count']} row(s)[/dim]")
    except Exception as e:
        console.print(f"[bold red]Execution Error:[/bold red] {str(e)}")

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

        table = Table(title="Synced Tables/Views", show_header=True, header_style="bold magenta")
        table.add_column("Entity Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Columns", style="green")
        table.add_column("Foreign Keys", style="yellow")

        for name, details in schema_info.items():
            entity_type = "View" if details.get("is_view") else "Table"
            col_count = len(details["columns"])
            fk_count = len(details.get("foreign_keys", []))
            table.add_row(name, entity_type, str(col_count), str(fk_count))

        console.print(table)
        console.print(f"[bold green]✓ Successfully synced {len(schema_info)} entities to .vero/schemas/[/bold green]")
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
            
            # Simple terminal command intercepts
            if question.startswith("/"):
                cmd = question.lower()
                if cmd == "/clear":
                    agent.history = []
                    console.print("[dim]Chat history cleared.[/dim]")
                else:
                    console.print(f"[dim]Unknown command: {cmd}[/dim]")
                continue

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
    """Starts the Vero Model Context Protocol (MCP) server for any MCP client (Claude, Cursor, Zed, Windsurf, custom agents)."""
    run_mcp_server(transport=transport)

@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p"),
    open_browser: bool = typer.Option(False, "--open", "-o", help="Automatically open studio in default browser")
):
    """Starts the Vero Studio server (serves both API and Web UI)."""
    url = f"http://{host}:{port}"
    console.print(Panel.fit(
        f"[bold magenta]Vero Analytics Studio[/bold magenta]\n"
        f"URL: [bold cyan]{url}[/bold cyan]\n"
        f"[dim]Serving both full Web UI and AI agent API on port {port}[/dim]",
        border_style="magenta"
    ))
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    uvicorn.run("vero.server:app", host=host, port=port, reload=False)

@app.command()
def studio(
    host: str = typer.Option("127.0.0.1", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p"),
):
    """Launches the Vero Studio web workspace and opens it in your browser."""
    serve(host=host, port=port, open_browser=True)

dbt_app = typer.Typer(
    name="dbt",
    help="dbt Core integration and manifest synchronization.",
    no_args_is_help=True
)
app.add_typer(dbt_app, name="dbt")

@dbt_app.command("sync")
def dbt_sync(
    project_dir: Path = typer.Option(
        Path.cwd(),
        "--project-dir",
        "-p",
        help="Path to dbt project containing target/manifest.json (or direct path to manifest.json)"
    )
):
    """Parses dbt target/manifest.json and synchronizes models, columns, descriptions, tests, and metrics."""
    from vero.dbt import DbtSyncEngine
    console.print(Panel.fit("[bold cyan]Syncing dbt Project Manifest[/bold cyan]", border_style="cyan"))

    try:
        engine = DbtSyncEngine()
        res = engine.sync(project_dir)

        table = Table(title="Synced dbt Models", show_header=True, header_style="bold magenta")
        table.add_column("Model Name", style="cyan")
        table.add_column("Columns", style="green")
        table.add_column("Relationships", style="yellow")
        table.add_column("Documented", style="magenta")

        for name, details in res["models"].items():
            table.add_row(
                name,
                str(details["columns"]),
                str(details["relationships"]),
                "✓" if details["description"] else "-"
            )

        console.print(table)
        console.print(
            f"[bold green]✓ Successfully synced {res['models_synced']} models and {res['metrics_synced']} semantic metrics from dbt[/bold green]"
        )
    except Exception as e:
        console.print(f"[bold red]dbt Sync Failed:[/bold red] {str(e)}")

if __name__ == "__main__":
    app()
