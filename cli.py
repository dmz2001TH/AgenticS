#!/usr/bin/env python3
"""
AgenticS CLI — Command-line interface for multi-agent AI
"""

import sys
import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from config import get_config
from agents import Agent, AgentConfig
from orchestration import Crew, CrewConfig, ProcessType, load_crew_from_yaml
from models import ModelClient, Message, list_available_models
from tools import get_tool_registry

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """🤖 AgenticS — Multi-Agent AI System"""
    pass


@cli.command()
@click.argument("message")
@click.option("--model", "-m", default=None, help="Model to use (gemini, openai, claude, ollama)")
@click.option("--agent", "-a", default="ChatAgent", help="Agent name")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def chat(message, model, agent, verbose):
    """Chat with a single agent."""
    config = get_config()
    model_name = model or config.default_model

    agent_config = AgentConfig(
        name=agent,
        role="Conversational Assistant",
        goal="Help the user with any question or task",
        model=model_name,
        verbose=verbose,
    )

    agent_obj = Agent(agent_config)
    with console.status("🤔 กำลังคิด..."):
        result = agent_obj.run(message)

    console.print(Panel(result.output, title=f"🤖 {agent}", border_style="green"))
    if verbose:
        console.print(f"[dim]Tokens: {result.usage.get('total_tokens', 0)} | Iterations: {result.iterations}[/dim]")


@cli.command()
@click.argument("task")
@click.option("--crew", "-c", default=None, help="Crew name to use")
@click.option("--config-file", "-f", default=None, help="Crew config YAML file")
@click.option("--process", "-p", default="sequential", type=click.Choice(["sequential", "parallel", "handoff"]))
@click.option("--model", "-m", default=None, help="Default model")
@click.option("--verbose", "-v", is_flag=True)
def run(task, crew, config_file, process, model, verbose):
    """Run a task with a crew of agents."""
    config = get_config()
    tool_registry = get_tool_registry()

    if config_file:
        crew_obj = load_crew_from_yaml(config_file, tool_registry)
    elif crew:
        # Load from default crews directory
        import os
        crew_path = os.path.join(os.path.dirname(__file__), "crews", f"{crew}.yaml")
        if os.path.exists(crew_path):
            crew_obj = load_crew_from_yaml(crew_path, tool_registry)
        else:
            console.print(f"[red]Crew '{crew}' not found. Create it in crews/ directory.[/red]")
            return
    else:
        # Default: create a simple crew
        model_name = model or config.default_model
        crew_config = CrewConfig(
            name="default-crew",
            description="Auto-generated crew",
            process=ProcessType(process),
            agents=[
                AgentConfig(name="researcher", role="Researcher", goal="Research and gather information", model=model_name),
                AgentConfig(name="analyst", role="Analyst", goal="Analyze data and provide insights", model=model_name),
                AgentConfig(name="writer", role="Writer", goal="Write clear summaries", model=model_name),
            ],
            verbose=verbose,
        )
        crew_obj = Crew(crew_config, tool_registry)

    console.print(f"\n[bold cyan]🚀 Running crew: {crew_obj.config.name}[/bold cyan]")
    console.print(f"[dim]Process: {crew_obj.config.process.value} | Agents: {len(crew_obj.agents)}[/dim]\n")

    with console.status("⏳ Working..."):
        result = crew_obj.run(task)

    console.print(Panel(result.final_output, title="✅ Result", border_style="green"))
    console.print(f"\n[dim]Duration: {result.duration_seconds}s | Tokens: {result.total_usage.get('total_tokens', 0)}[/dim]")


@cli.command()
@click.option("--model", "-m", default=None, help="Filter by model")
def models(model):
    """List available models."""
    config = get_config()
    table = Table(title="Available Models")
    table.add_column("Name", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Model ID", style="yellow")
    table.add_column("Status", style="white")

    for name, cfg in config.model_providers.items():
        is_default = "⭐" if name == config.default_model else "  "
        api_key = "✅ configured" if cfg.get("api_key") else "⚠️  no key (uses env/CLI)"
        table.add_row(name, cfg.get("provider", "?"), cfg.get("model", "?"), f"{is_default} {api_key}")

    console.print(table)


@cli.command()
def tools():
    """List available tools."""
    registry = get_tool_registry()
    table = Table(title="Available Tools")
    table.add_column("Tool", style="cyan")
    table.add_column("Description", style="white")

    for name in registry.list_tools():
        tool = registry.get(name)
        table.add_row(name, tool.description)

    console.print(table)


@cli.command()
def serve():
    """Start the web server with dashboard."""
    import uvicorn
    from server import app, load_default_crews

    config = get_config()
    server_cfg = config.server_config
    load_default_crews()

    console.print(Panel(
        f"Dashboard: http://localhost:{server_cfg['port']}\n"
        f"API Docs:  http://localhost:{server_cfg['port']}/docs",
        title="🤖 AgenticS Server",
        border_style="green",
    ))

    uvicorn.run(app, host=server_cfg["host"], port=server_cfg["port"])


@cli.command()
def status():
    """Show system status."""
    config = get_config()
    table = Table(title="AgenticS Status")
    table.add_column("Item", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Version", "0.1.0")
    table.add_row("Default Model", config.default_model)
    table.add_row("Available Models", str(len(config.model_providers)))
    table.add_row("Available Tools", str(len(get_tool_registry().list_tools())))
    table.add_row("Server Port", str(config.server_config.get("port", 7860)))

    console.print(table)


if __name__ == "__main__":
    cli()
