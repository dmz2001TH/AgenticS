#!/usr/bin/env python3
"""
AgenticS CLI — Full-featured command-line interface
"""

import sys
import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

from config import get_config
from agents import Agent, AgentConfig
from orchestration import Crew, CrewConfig, ProcessType, load_crew_from_yaml
from models import ModelClient, Message, list_available_models
from tools import get_tool_registry

console = Console()


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """🤖 AgenticS — Multi-Agent AI System v0.2.0"""
    pass


# --- Chat ---
@cli.command()
@click.argument("message")
@click.option("--model", "-m", default=None, help="Model (gemini, gemini-cli, openai, claude, ollama)")
@click.option("--agent", "-a", default="ChatAgent")
@click.option("--verbose", "-v", is_flag=True)
def chat(message, model, agent, verbose):
    """Chat with a single agent."""
    config = get_config()
    agent_config = AgentConfig(
        name=agent, role="Conversational Assistant",
        goal="Help the user", model=model or config.default_model, verbose=verbose,
    )
    agent_obj = Agent(agent_config)
    with console.status("🤔 Thinking..."):
        result = agent_obj.run(message)
    console.print(Panel(result.output, title=f"🤖 {agent}", border_style="green"))
    if verbose:
        console.print(f"[dim]Tokens: {result.usage.get('total_tokens', 0)} | Iterations: {result.iterations}[/dim]")


@cli.command()
@click.option("--model", "-m", default=None)
def chatloop(model):
    """Interactive chat loop."""
    config = get_config()
    model_name = model or config.default_model
    agent_config = AgentConfig(
        name="ChatAgent", role="Conversational Assistant",
        goal="Help the user", model=model_name,
    )
    agent = Agent(agent_config)
    console.print(f"[bold green]🤖 AgenticS Chat[/bold green] (model: {model_name})")
    console.print("[dim]Type 'exit' or 'quit' to end. Type '/reset' to reset memory.[/dim]\n")

    while True:
        try:
            msg = Prompt.ask("[bold cyan]You[/bold cyan]")
            if msg.lower() in ("exit", "quit"):
                break
            if msg == "/reset":
                agent.reset_memory()
                console.print("[yellow]Memory reset.[/yellow]")
                continue
            with console.status("🤔 Thinking..."):
                result = agent.run(msg)
            console.print(f"\n[bold green]Agent:[/bold green] {result.output}\n")
        except KeyboardInterrupt:
            break
    console.print("[dim]Goodbye! 👋[/dim]")


# --- Run Crew ---
@cli.command()
@click.argument("task")
@click.option("--crew", "-c", default=None)
@click.option("--config-file", "-f", default=None)
@click.option("--process", "-p", default="sequential", type=click.Choice(["sequential", "parallel", "handoff", "swarm"]))
@click.option("--model", "-m", default=None)
@click.option("--verbose", "-v", is_flag=True)
def run(task, crew, config_file, process, model, verbose):
    """Run a task with a crew."""
    config = get_config()
    tool_registry = get_tool_registry()

    if config_file:
        crew_obj = load_crew_from_yaml(config_file, tool_registry)
    elif crew:
        import os
        crew_path = os.path.join(os.path.dirname(__file__), "crews", f"{crew}.yaml")
        crew_obj = load_crew_from_yaml(crew_path, tool_registry)
    else:
        model_name = model or config.default_model
        crew_config = CrewConfig(
            name="default", process=ProcessType(process), verbose=verbose,
            agents=[
                AgentConfig(name="researcher", role="Researcher", goal="Research", model=model_name),
                AgentConfig(name="analyst", role="Analyst", goal="Analyze", model=model_name),
                AgentConfig(name="writer", role="Writer", goal="Write", model=model_name),
            ],
        )
        crew_obj = Crew(crew_config, tool_registry)

    console.print(f"\n[bold cyan]🚀 Running: {crew_obj.config.name}[/bold cyan] ({crew_obj.config.process.value})")
    with console.status("⏳ Working..."):
        result = crew_obj.run(task)
    console.print(Panel(result.final_output, title="✅ Result", border_style="green"))
    console.print(f"[dim]Duration: {result.duration_seconds}s | Tokens: {result.total_usage.get('total_tokens', 0)}[/dim]")


# --- Schedule ---
@cli.command()
@click.argument("name")
@click.argument("task_prompt")
@click.option("--crew", "-c", default=None)
@click.option("--type", "-t", "schedule_type", default="manual", type=click.Choice(["manual", "interval", "cron"]))
@click.option("--value", "-v", default="", help="Schedule value (e.g. 3600 for interval)")
def schedule(name, task_prompt, crew, schedule_type, value):
    """Create a scheduled task."""
    from scheduler import get_scheduler, ScheduleType
    s = get_scheduler()
    task = s.create_task(name=name, task_prompt=task_prompt, crew_name=crew,
                         schedule_type=ScheduleType(schedule_type), schedule_value=value)
    console.print(f"[green]✅ Scheduled: {task.name} ({schedule_type})[/green]")


@cli.command()
def loops():
    """List scheduled tasks."""
    from scheduler import get_scheduler
    s = get_scheduler()
    table = Table(title="Scheduled Tasks")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Status")
    table.add_column("Runs", style="yellow")
    for t in s.get_tasks():
        status = "🟢" if t.status.value == "active" else "⏸️"
        table.add_row(t.id, t.name, t.schedule_type.value, status, str(t.run_count))
    console.print(table)


@cli.command()
@click.argument("task_id")
def trigger(task_id):
    """Manually trigger a scheduled task."""
    from scheduler import get_scheduler
    config = get_config()
    tool_registry = get_tool_registry()
    s = get_scheduler()

    def execute(task):
        if task.crew_name:
            import os
            crew_path = os.path.join(os.path.dirname(__file__), "crews", f"{task.crew_name}.yaml")
            crew_obj = load_crew_from_yaml(crew_path, tool_registry)
            result = crew_obj.run(task.task_prompt)
            return result.final_output
        agent_config = AgentConfig(name="trigger", model=config.default_model)
        return Agent(agent_config, tool_registry).run(task.task_prompt).output

    result = s.trigger_task(task_id, callback=execute)
    if result:
        console.print(Panel(result.get("result", result.get("error", "done")), title="⚡ Triggered", border_style="green"))
    else:
        console.print("[red]Task not found[/red]")


# --- Memory ---
@cli.command()
def memory():
    """List memory sessions."""
    from memory import get_memory_store
    store = get_memory_store()
    sessions = store.list_sessions()
    table = Table(title="Memory Sessions")
    table.add_column("Session", style="cyan")
    table.add_column("Messages", style="yellow")
    table.add_column("Last")
    for s in sessions:
        table.add_row(s["session_id"][:16]+"...", str(s["message_count"]), s["last_message"][:50])
    console.print(table)


@cli.command()
@click.argument("query")
@click.option("--limit", "-l", default=10)
def search(query, limit):
    """Search memory."""
    from memory import get_memory_store
    store = get_memory_store()
    results = store.search_messages(query, limit)
    for r in results:
        console.print(f"[dim]{r.timestamp}[/dim] [{r.agent_name}] {r.content[:100]}")


# --- Trajectories ---
@cli.command()
def trajectories():
    """List trajectories."""
    from trajectories import get_trajectory_store
    store = get_trajectory_store()
    trajs = store.get_trajectories()
    table = Table(title="Trajectories")
    table.add_column("Task", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Steps", style="yellow")
    table.add_column("Status")
    for t in trajs:
        status = "✅" if t["success"] else "❌"
        table.add_row(t["task"][:40], t["agent"], str(t["steps"]), status)
    console.print(table)


@cli.command()
@click.option("--output", "-o", default="training_data.jsonl")
def export(output):
    """Export trajectories for training."""
    from trajectories import get_trajectory_store
    store = get_trajectory_store()
    count = store.export_for_training(output)
    console.print(f"[green]📤 Exported {count} trajectories to {output}[/green]")


# --- Plugins ---
@cli.command()
def plugins():
    """List plugins."""
    from plugins import get_plugin_manager
    pm = get_plugin_manager()
    table = Table(title="Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Description")
    table.add_column("Status")
    for p in pm.discover_plugins():
        table.add_row(p.name, p.version, p.description[:40], "✅" if p.name in [l.name for l in pm.get_loaded_plugins()] else "—")
    console.print(table)


# --- Tools ---
@cli.command()
def tools():
    """List available tools."""
    registry = get_tool_registry()
    table = Table(title="Tools")
    table.add_column("Tool", style="cyan")
    table.add_column("Description")
    for name in registry.list_tools():
        tool = registry.get(name)
        table.add_row(name, tool.description)
    console.print(table)


# --- Models ---
@cli.command()
def models():
    """List available models."""
    config = get_config()
    table = Table(title="Models")
    table.add_column("Name", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Model ID", style="yellow")
    for name, cfg in config.model_providers.items():
        is_default = "⭐" if name == config.default_model else "  "
        table.add_row(f"{is_default} {name}", cfg.get("provider", "?"), cfg.get("model", "?"))
    console.print(table)


# --- Status ---
@cli.command()
def status():
    """System status."""
    config = get_config()
    from scheduler import get_scheduler
    s = get_scheduler()
    from plugins import get_plugin_manager
    pm = get_plugin_manager()

    table = Table(title="AgenticS v0.2.0 Status")
    table.add_column("Item", style="cyan")
    table.add_column("Value")
    table.add_row("Default Model", config.default_model)
    table.add_row("Models", str(len(config.model_providers)))
    table.add_row("Tools", str(len(get_tool_registry().list_tools())))
    table.add_row("Scheduled Tasks", str(len(s.tasks)))
    table.add_row("Plugins", str(len(pm.get_loaded_plugins())))
    table.add_row("Server Port", str(config.server_config.get("port", 7860)))
    console.print(table)


# --- Server ---
@cli.command()
def serve():
    """Start the web server."""
    import uvicorn
    from server import app, load_defaults
    config = get_config()
    load_defaults()
    cfg = config.server_config
    console.print(Panel(
        f"Dashboard: http://localhost:{cfg['port']}\n"
        f"API:       http://localhost:{cfg['port']}/docs\n"
        f"WebSocket: ws://localhost:{cfg['port']}/ws",
        title="🤖 AgenticS Server v0.2.0", border_style="green",
    ))
    uvicorn.run(app, host=cfg["host"], port=cfg["port"])


if __name__ == "__main__":
    cli()
