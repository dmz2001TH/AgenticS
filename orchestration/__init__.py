"""
AgenticS Orchestration — Crew & Swarm patterns for multi-agent coordination
Supports: Sequential, Parallel, Handoff (conditional routing), Sub-agent spawning
"""

import json
import uuid
import yaml
import time
from enum import Enum
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from agents import Agent, AgentConfig, AgentResult
from models import ModelClient, Message
from tools import get_tool_registry, ToolRegistry


class ProcessType(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HANDOFF = "handoff"
    SWARM = "swarm"  # New: agents vote/consensus


@dataclass
class CrewResult:
    crew_name: str
    task: str
    process: str
    agent_results: list[AgentResult] = field(default_factory=list)
    final_output: str = ""
    total_usage: dict = field(default_factory=dict)
    duration_seconds: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "crew_name": self.crew_name,
            "task": self.task,
            "process": self.process,
            "agent_results": [r.to_dict() for r in self.agent_results],
            "final_output": self.final_output,
            "total_usage": self.total_usage,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
        }


@dataclass
class CrewConfig:
    name: str
    description: str = ""
    agents: list[AgentConfig] = field(default_factory=list)
    process: ProcessType = ProcessType.SEQUENTIAL
    verbose: bool = True
    max_agents: int = 10
    routing_agent: Optional[str] = None  # Which agent does the routing for handoff


class Crew:
    """Multi-agent crew with different orchestration patterns."""

    def __init__(self, config: CrewConfig, tool_registry: Optional[ToolRegistry] = None):
        self.config = config
        self.tool_registry = tool_registry or get_tool_registry()
        self.agents: list[Agent] = []
        self.history: list[CrewResult] = []
        self.id = str(uuid.uuid4())[:8]

        # Create agents from config
        for agent_config in config.agents:
            self.agents.append(Agent(agent_config, self.tool_registry))

    def run(self, task: str) -> CrewResult:
        """Execute a task using the crew's process type."""
        start = time.time()

        if self.config.process == ProcessType.SEQUENTIAL:
            result = self._run_sequential(task)
        elif self.config.process == ProcessType.PARALLEL:
            result = self._run_parallel(task)
        elif self.config.process == ProcessType.HANDOFF:
            result = self._run_handoff(task)
        elif self.config.process == ProcessType.SWARM:
            result = self._run_swarm(task)
        else:
            result = self._run_sequential(task)

        result.duration_seconds = round(time.time() - start, 2)

        # Accumulate usage
        for ar in result.agent_results:
            for k, v in ar.usage.items():
                result.total_usage[k] = result.total_usage.get(k, 0) + v

        self.history.append(result)
        return result

    def _run_sequential(self, task: str) -> CrewResult:
        """Agents run in order, each building on the previous agent's output."""
        result = CrewResult(crew_name=self.config.name, task=task, process="sequential")

        context = ""
        for i, agent in enumerate(self.agents):
            if self.config.verbose:
                print(f"🤖 [{self.config.name}] Agent {i+1}/{len(self.agents)}: {agent.config.name} ({agent.config.role})")

            agent_task = task if i == 0 else f"Based on the previous work, continue the task.\n\nOriginal task: {task}"
            agent_result = agent.run(agent_task, context=context)
            result.agent_results.append(agent_result)
            context = agent_result.output

        result.final_output = context
        return result

    def _run_parallel(self, task: str) -> CrewResult:
        """All agents work on the same task, results are combined."""
        import concurrent.futures
        result = CrewResult(crew_name=self.config.name, task=task, process="parallel")

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
            futures = {executor.submit(agent.run, task): agent for agent in self.agents}
            for future in concurrent.futures.as_completed(futures):
                agent_result = future.result()
                result.agent_results.append(agent_result)

        # Combine outputs
        combined = []
        for ar in result.agent_results:
            combined.append(f"### {ar.agent_name}\n{ar.output}")
        result.final_output = "\n\n---\n\n".join(combined)
        return result

    def _run_handoff(self, task: str) -> CrewResult:
        """Router agent decides who handles what, then delegates with conditional routing."""
        if not self.agents:
            return CrewResult(crew_name=self.config.name, task=task, process="handoff", final_output="No agents configured")

        result = CrewResult(crew_name=self.config.name, task=task, process="handoff")

        # First agent is router
        orchestrator = self.agents[0]
        workers = self.agents[1:]

        if not workers:
            agent_result = orchestrator.run(task)
            result.agent_results.append(agent_result)
            result.final_output = agent_result.output
            return result

        # Build worker descriptions
        worker_desc = "\n".join([
            f"- {a.config.name} ({a.config.role}): {a.config.goal}" for a in workers
        ])

        routing_prompt = f"""You are the orchestrator. Given this task:
"{task}"

Available agents:
{worker_desc}

Analyze the task and decide which agent(s) should handle it. Consider:
1. Which skills are needed?
2. What order should they work in?
3. Should any step be conditional?

Respond with ONLY a JSON array of agent names in execution order.
Example: ["agent1", "agent2"]
Agent names: {[a.config.name for a in workers]}"""

        route_response = orchestrator.model.chat([Message(role="user", content=routing_prompt)])
        context = ""

        # Parse routing decision
        try:
            content = route_response.content.strip()
            if "[" in content:
                json_str = content[content.index("["):content.rindex("]") + 1]
                selected_names = json.loads(json_str)
            else:
                selected_names = [workers[0].config.name]
        except (json.JSONDecodeError, ValueError):
            selected_names = [workers[0].config.name]

        # Execute with conditional routing
        for i, name in enumerate(selected_names):
            agent = next((a for a in workers if a.config.name == name), None)
            if agent:
                if self.config.verbose:
                    print(f"🤖 [{self.config.name}] Handoff → {agent.config.name} ({agent.config.role})")

                # Conditional: if previous agent found an issue, can route to a different agent
                agent_task = task if i == 0 else f"Previous output:\n{context}\n\nContinue from here. Original task: {task}"
                agent_result = agent.run(agent_task, context=context)
                result.agent_results.append(agent_result)
                context = agent_result.output

                # Check if agent recommends further routing
                if agent_result.output and "handoff:" in agent_result.output.lower():
                    for w in workers:
                        if w.config.name.lower() in agent_result.output.lower() and w.config.name != name:
                            if self.config.verbose:
                                print(f"🤖 [{self.config.name}] Conditional handoff → {w.config.name}")
                            follow_up = w.run(f"Follow up on: {agent_result.output[:500]}", context=context)
                            result.agent_results.append(follow_up)
                            context = follow_up.output

        result.final_output = context
        return result

    def _run_swarm(self, task: str) -> CrewResult:
        """Agents vote/consensus on the best approach (inspired by CrewAI consensual)."""
        if len(self.agents) < 2:
            return self._run_sequential(task)

        result = CrewResult(crew_name=self.config.name, task=task, process="swarm")

        # Phase 1: Each agent proposes independently
        proposals = []
        for agent in self.agents:
            proposal_prompt = f"""Task: {task}

As {agent.config.name} ({agent.config.role}), propose your approach to solve this task.
Be specific about what you would do. Then provide your solution."""
            agent_result = agent.run(proposal_prompt)
            result.agent_results.append(agent_result)
            proposals.append({
                "agent": agent.config.name,
                "approach": agent_result.output[:500],
                "full": agent_result.output,
            })

        # Phase 2: Synthesize best approach
        synthesis_prompt = f"""You are the final synthesizer. Review these proposals for the task:

Task: {task}

Proposals:
{json.dumps([{"agent": p["agent"], "approach": p["approach"]} for p in proposals], ensure_ascii=False, indent=2)}

Combine the best elements from each proposal into a comprehensive final answer."""

        final_agent = self.agents[-1]  # Last agent synthesizes
        synthesis_result = final_agent.run(synthesis_prompt)
        result.final_output = synthesis_result.output

        return result

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.config.name,
            "description": self.config.description,
            "process": self.config.process.value,
            "agents": [a.to_dict() for a in self.agents],
            "history_count": len(self.history),
        }


class CrewBuilder:
    """Fluent builder for creating crews."""

    def __init__(self, name: str):
        self._config = CrewConfig(name=name)

    def description(self, desc: str) -> "CrewBuilder":
        self._config.description = desc
        return self

    def add_agent(self, config: AgentConfig) -> "CrewBuilder":
        self._config.agents.append(config)
        return self

    def process(self, process: ProcessType) -> "CrewBuilder":
        self._config.process = process
        return self

    def build(self, tool_registry: Optional[ToolRegistry] = None) -> Crew:
        return Crew(self._config, tool_registry)


def load_crew_from_yaml(path: str, tool_registry: Optional[ToolRegistry] = None) -> Crew:
    """Load crew configuration from a YAML file."""
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    config = CrewConfig(
        name=data.get("name", "unnamed-crew"),
        description=data.get("description", ""),
        process=ProcessType(data.get("process", "sequential")),
    )

    for agent_data in data.get("agents", []):
        config.agents.append(AgentConfig(
            name=agent_data["name"],
            role=agent_data.get("role", "Assistant"),
            goal=agent_data.get("goal", "Help with tasks"),
            backstory=agent_data.get("backstory", ""),
            model=agent_data.get("model", "gemini"),
            tools=agent_data.get("tools", []),
            temperature=agent_data.get("temperature", 0.7),
        ))

    return Crew(config, tool_registry)
