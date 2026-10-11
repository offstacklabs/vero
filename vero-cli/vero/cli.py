import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from pathlib import Path
from typing import Optional, Dict, Any, List
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
    dialect: str = typer.Option("bigquery", "--dialect", "-d", help="Database dialect (bigquery, snowflake, postgres, duckdb)"),
    conn: str = typer.Option("bigquery://my-project-id/my_analytics_dataset", "--conn", "-c", help="Connection string")
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

    try:
        with console.status("Checking metadata storage and migrations..."):
            engine = ContextEngine()
            mig_res = engine.migrate()
            console.print(f"[bold green]✓ {mig_res['message']}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ Metadata Storage Error:[/bold red] {str(e)}")

@app.command("migrate")
def cli_migrate():
    """Applies schema migrations to centralized metadata database."""
    console.print(Panel.fit("[bold cyan]Running Metadata Database Migrations[/bold cyan]", border_style="cyan"))
    engine = ContextEngine()
    res = engine.migrate()
    console.print(f"[bold green]✓ {res['message']}[/bold green]")

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
def chat(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Scope context to a specific domain (e.g. finance, marketing)")
):
    """Launches the Vero Interactive Analytics Terminal."""
    domain_msg = f" [bold magenta]({domain.capitalize()} Domain)[/bold magenta]" if domain else ""
    console.print(Panel.fit(f"[bold cyan]Vero Analytics Agent{domain_msg}[/bold cyan] (Type 'exit' to quit)", border_style="cyan"))
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
                res = agent.ask(question, domain=domain)

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

rules_app = typer.Typer(
    name="rules",
    help="Manage business and SQL rules context.",
    no_args_is_help=True
)
app.add_typer(rules_app, name="rules")

@rules_app.command("show")
def rules_show(
    domain: str = typer.Option("global", "--domain", "-d", help="Domain scope (default: global)")
):
    """Displays active business rules for a domain (inherits global rules)."""
    engine = ContextEngine()
    rules = engine.get_rules(domain=domain)
    title = f"Vero Rules [{domain.capitalize()} Domain]"
    console.print(Panel(Markdown(rules) if rules else "[dim]No rules configured yet.[/dim]", title=title))

@rules_app.command("add")
def rules_add(
    rule: str = typer.Argument(..., help="Rule or convention to add"),
    domain: str = typer.Option("global", "--domain", "-d", help="Domain to attach rule to")
):
    """Appends a new business rule to a specific domain."""
    engine = ContextEngine()
    engine.append_rule(rule, domain=domain)
    console.print(f"[bold green]✓ Rule added to {domain}:[/bold green] {rule}")

metrics_app = typer.Typer(
    name="metrics",
    help="Manage semantic metrics.",
    no_args_is_help=True
)
app.add_typer(metrics_app, name="metrics")

@metrics_app.command("list")
def metrics_list(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter metrics by domain")
):
    """Lists registered semantic metrics (optionally filtered by domain)."""
    engine = ContextEngine()
    metrics = engine.get_metrics(domain=domain)
    table = Table(title=f"Semantic Metrics {f'[{domain.capitalize()}]' if domain else '[All Domains]'}", show_header=True, header_style="bold magenta")
    table.add_column("Metric Name", style="cyan")
    table.add_column("Domain", style="yellow")
    table.add_column("Description", style="white")
    table.add_column("SQL Formula", style="green")
    for m in metrics:
        table.add_row(m["name"], m.get("domain", "global"), m.get("description", "-"), m.get("sql", "-"))
    console.print(table)

@metrics_app.command("add")
def metrics_add(
    name: str = typer.Option(..., "--name", "-n", help="Metric identifier (e.g. mrr)"),
    sql: str = typer.Option(..., "--sql", "-s", help="SQL aggregation expression"),
    description: str = typer.Option("", "--desc", "-d", help="Metric description"),
    domain: str = typer.Option("global", "--domain", "-d", help="Domain namespace (e.g. finance, marketing)")
):
    """Creates or updates a semantic metric in a domain."""
    engine = ContextEngine()
    engine.save_metric({"name": name, "sql": sql, "description": description, "domain": domain}, domain=domain)
    console.print(f"[bold green]✓ Metric saved to {domain}:[/bold green] [cyan]{name}[/cyan] = `{sql}`")

domains_app = typer.Typer(
    name="domains",
    help="Manage multi-domain business namespaces.",
    no_args_is_help=True
)
app.add_typer(domains_app, name="domains")

@domains_app.command("list")
def domains_list():
    """Lists all available business domains."""
    engine = ContextEngine()
    domains = engine.get_domains()
    table = Table(title="Business Domains", show_header=True, header_style="bold magenta")
    table.add_column("Domain ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Description", style="dim")
    for d in domains:
        table.add_row(d["id"], d["name"], d.get("description", "-"))
    console.print(table)

@domains_app.command("add")
def domains_add(
    domain_id: str = typer.Argument(..., help="Unique domain slug (e.g. sales, logistics)"),
    name: str = typer.Option(..., "--name", "-n", help="Display name (e.g. 'Sales & Operations')"),
    description: str = typer.Option("", "--desc", "-d", help="Description of this domain scope")
):
    """Registers a new business domain partition."""
    engine = ContextEngine()
    created = engine.create_domain(domain_id=domain_id, name=name, description=description)
    console.print(f"[bold green]✓ Created business domain:[/bold green] [cyan]{created['id']}[/cyan] ({created['name']})")

@metrics_app.command("sync")
def metrics_sync(
    source: str = typer.Option(..., "--from", help="Source framework: lookml, dbt, cube, or ossie"),
    path: str = typer.Option(..., "--path", "-p", help="Path to manifest.json, .lkml folder, or schema file"),
    domain: str = typer.Option("global", "--domain", "-d", help="Domain namespace to import into")
):
    """Imports and synchronizes external semantic metrics into Vero."""
    from vero.semantic import SemanticImporter
    from pathlib import Path

    target = Path(path)
    if not target.exists():
        console.print(f"[bold red]✗ Path not found:[/bold red] {path}")
        raise typer.Exit(1)

    importer = SemanticImporter()
    try:
        s_lower = source.lower()
        if s_lower == "lookml":
            metrics = importer.import_lookml(target, domain=domain)
        elif s_lower == "dbt":
            metrics = importer.import_dbt(target, domain=domain)
        elif s_lower == "cube":
            metrics = importer.import_cube(target, domain=domain)
        elif s_lower in ["ossie", "osi", "apache_ossie"]:
            metrics = importer.import_ossie(target, domain=domain)
        else:
            console.print(f"[bold red]✗ Unsupported source:[/bold red] {source}. Use lookml, dbt, cube, or ossie.")
            raise typer.Exit(1)

        count = importer.sync_to_vero(metrics, domain=domain)
        console.print(f"[bold green]✓ Successfully imported {count} semantic metrics from {source.upper()} to domain '{domain}'.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ Import Failed:[/bold red] {str(e)}")
        raise typer.Exit(1)

users_app = typer.Typer(
    name="users",
    help="Manage enterprise users, roles, and domain-scoped access.",
    no_args_is_help=True
)
app.add_typer(users_app, name="users")

@users_app.command("list")
def users_list():
    """Lists all users and their assigned roles and domains."""
    from vero.auth import AuthManager
    mgr = AuthManager()
    mgr.seed_default_admin()
    users = mgr.get_all_users()

    table = Table(title="Vero Users & Roles", show_header=True, header_style="bold magenta")
    table.add_column("User ID", style="dim")
    table.add_column("Name", style="white")
    table.add_column("Email", style="cyan")
    table.add_column("Role", style="magenta")
    table.add_column("Allowed Domains", style="green")
    table.add_column("Status", style="yellow")

    for u in users:
        domains_str = ", ".join(u.allowed_domains)
        status_str = "Active" if u.is_active else "Inactive"
        table.add_row(u.id, u.name, u.email, u.role.upper(), domains_str, status_str)

    console.print(table)

@users_app.command("add")
def users_add(
    email: str = typer.Argument(..., help="User's email address"),
    name: str = typer.Option(..., "--name", "-n", help="User's full name"),
    role: str = typer.Option("analyst", "--role", "-r", help="Role: admin, analyst, or viewer"),
    domains: str = typer.Option("*", "--domains", "-d", help="Comma-separated allowed domains (e.g. 'finance,marketing' or '*')"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="User password (optional, generates API key)")
):
    """Creates a new user and prints their credentials and API key."""
    from vero.auth import AuthManager
    mgr = AuthManager()
    mgr.seed_default_admin()

    clean_role = role.lower().strip()
    if clean_role not in ["admin", "analyst", "viewer"]:
        console.print(f"[bold red]✗ Invalid role '{role}'. Must be admin, analyst, or viewer.[/bold red]")
        raise typer.Exit(1)

    allowed = [d.strip() for d in domains.split(",") if d.strip()]
    user, api_key = mgr.create_user(
        email=email,
        name=name,
        password=password,
        role=clean_role,
        allowed_domains=allowed
    )

    console.print(Panel.fit(
        f"[bold green]✓ User created successfully![/bold green]\n\n"
        f"• [bold]ID:[/bold] {user.id}\n"
        f"• [bold]Name:[/bold] {user.name}\n"
        f"• [bold]Email:[/bold] {user.email}\n"
        f"• [bold]Role:[/bold] {user.role.upper()}\n"
        f"• [bold]Allowed Domains:[/bold] {', '.join(user.allowed_domains)}\n"
        f"• [bold]API Key:[/bold] [yellow]{api_key}[/yellow]\n"
        f"  (Store this API key safely; it will not be shown again)",
        title="User Provisioned",
        border_style="green"
    ))

@users_app.command("delete")
def users_delete(user_id: str = typer.Argument(..., help="User ID to delete (e.g. usr_...)")):
    """Deletes a user from the system."""
    from vero.auth import AuthManager
    mgr = AuthManager()
    deleted = mgr.delete_user(user_id)
    if deleted:
        console.print(f"[bold green]✓ Deleted user {user_id}[/bold green]")
    else:
        console.print(f"[bold red]✗ User {user_id} not found[/bold red]")

if __name__ == "__main__":
    app()
