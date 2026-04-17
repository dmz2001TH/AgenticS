"""
AgenticS Agent System — Role-based AI agents with memory, tools, and streaming
"""

import json
import uuid
import asyncio
import concurrent.futures
from datetime import datetime
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field

from models import ModelClient, Message, ModelResponse
from tools import get_tool_registry, ToolRegistry


@dataclass
class AgentConfig:
    name: str
    role: str = "Assistant"
    goal: str = "Help the user with their tasks"
    backstory: str = ""
    model: str = "gemini"
    tools: list[str] = field(default_factory=list)
    max_iterations: int = 10
    temperature: float = 0.7
    verbose: bool = True
    memory_enabled: bool = True


@dataclass
class AgentResult:
    agent_name: str
    task: str
    output: str
    usage: dict = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)
    iterations: int = 0
    timestamp: str = ""
    trajectory_id: Optional[str] = None
    sub_agent_results: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "task": self.task,
            "output": self.output,
            "usage": self.usage,
            "tool_calls": self.tool_calls,
            "iterations": self.iterations,
            "timestamp": self.timestamp,
            "trajectory_id": self.trajectory_id,
            "sub_agent_results": self.sub_agent_results,
        }


class Agent:
    """A role-based AI agent with memory, tools, streaming, and sub-agent spawning."""

    def __init__(self, config: AgentConfig, tool_registry: Optional[ToolRegistry] = None):
        self.config = config
        self.model = ModelClient(model_name=config.model)
        self.tool_registry = tool_registry or get_tool_registry()
        self.memory: list[Message] = []
        self.id = str(uuid.uuid4())[:8]
        self._memory_store = None
        self._trajectory_store = None

        # Initialize system prompt
        self._init_system_prompt()

    def _init_system_prompt(self):
        tools_desc = ""
        if self.config.tools:
            available = self.tool_registry.to_openai_tools(self.config.tools)
            tools_desc = "\n\nAvailable tools:\n"
            for t in available:
                fn = t["function"]
                tools_desc += f"- {fn['name']}: {fn['description']}\n"

        system_prompt = f"""You are {self.config.name}, a {self.config.role}.

## Your Goal
{self.config.goal}

## Your Backstory
{self.config.backstory or f"You are an expert {self.config.role} with deep knowledge in your domain."}
{tools_desc}

## Instructions
- Provide thorough, detailed responses
- If you need to use a tool, explain what you're doing
- Use Thai or English based on the user's language
- Be concise but comprehensive
- Think step by step before answering
- You can spawn sub-agents for complex sub-tasks
"""
        self.memory.append(Message(role="system", content=system_prompt))

    def _load_memory_context(self, task: str):
        """Load relevant past context from memory store."""
        if not self.config.memory_enabled:
            return ""
        try:
            from memory import get_memory_store
            store = get_memory_store()
            similar = store.get_similar_past_tasks(self.config.name, task, limit=3)
            if similar:
                context = "\n[Past similar tasks]:\n"
                for s in similar:
                    context += f"- {s.get('task_pattern', '')[:100]} → used tools: {s.get('tools_used', [])}\n"
                return context
        except Exception:
            pass
        return ""

    def run(self, task: str, context: str = "") -> AgentResult:
        """Execute a task with ReAct-style tool calling loop."""
        import time
        start = time.time()

        # Load memory context
        memory_context = self._load_memory_context(task)
        if memory_context:
            context = (context or "") + memory_context

        # Start trajectory tracking
        traj_id = None
        try:
            from trajectories import get_trajectory_store, TrajectoryStep
            store = get_trajectory_store()
            traj = store.start_trajectory(task, self.config.name)
            traj_id = traj.id
        except Exception:
            store = None

        # Add task to memory
        task_msg = task
        if context:
            task_msg = f"{task}\n\n[Context]:\n{context}"
        self.memory.append(Message(role="user", content=task_msg))

        tool_calls_log = []
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        final_output = ""
        iteration = 0

        for iteration in range(self.config.max_iterations):
            # Get model response
            tools = self.tool_registry.to_openai_tools(self.config.tools) if self.config.tools else None
            response = self.model.chat(
                self.memory,
                temperature=self.config.temperature,
                tools=tools,
            )

            # Accumulate usage
            for k in total_usage:
                total_usage[k] += response.usage.get(k, 0)

            # Track thought in trajectory
            if store and traj_id:
                store.add_step(traj_id, TrajectoryStep(
                    step_type="thought",
                    content=response.content[:500] if response.content else "[tool call]",
                    agent_name=self.config.name,
                    timestamp=datetime.now().isoformat(),
                ))

            # Check if model wants to call tools
            tool_calls_raw = response.raw.get("choices", [{}])[0].get("message", {}).get("tool_calls") if response.raw else None
            if tool_calls_raw:
                tool_calls = tool_calls_raw
                self.memory.append(Message(role="assistant", content=response.content or ""))

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])

                    # Sub-agent spawning
                    if fn_name == "spawn_agent":
                        sub_result = self._spawn_sub_agent(
                            fn_args.get("name", "sub"),
                            fn_args.get("role", "Assistant"),
                            fn_args.get("task", task),
                            fn_args.get("model", self.config.model),
                        )
                        result = sub_result.output
                        tool_calls_log.append({"tool": fn_name, "args": fn_args, "result": result[:500]})
                    else:
                        result = self.tool_registry.execute(fn_name, **fn_args)
                        tool_calls_log.append({"tool": fn_name, "args": fn_args, "result": result[:500]})

                    # Track action in trajectory
                    if store and traj_id:
                        store.add_step(traj_id, TrajectoryStep(
                            step_type="action",
                            content=f"Using {fn_name}",
                            agent_name=self.config.name,
                            timestamp=datetime.now().isoformat(),
                            tool_name=fn_name,
                            tool_args=fn_args,
                        ))
                        store.add_step(traj_id, TrajectoryStep(
                            step_type="observation",
                            content=result[:500],
                            agent_name=self.config.name,
                            timestamp=datetime.now().isoformat(),
                        ))

                    self.memory.append(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tc["id"],
                    ))

                if self.config.verbose:
                    print(f"  [{self.config.name}] Iteration {iteration + 1}: tools {[tc['function']['name'] for tc in tool_calls]}")
            else:
                # Model gave a final answer
                final_output = response.content
                self.memory.append(Message(role="assistant", content=final_output))

                if store and traj_id:
                    store.add_step(traj_id, TrajectoryStep(
                        step_type="result",
                        content=final_output[:1000],
                        agent_name=self.config.name,
                        timestamp=datetime.now().isoformat(),
                    ))
                break
        else:
            final_output = final_output or "[Max iterations reached]"

        duration = round(time.time() - start, 2)

        # Save trajectory
        if store and traj_id:
            store.finish_trajectory(traj_id, final_output, success="[Error" not in final_output)

        # Save to memory store
        try:
            from memory import get_memory_store
            mem_store = get_memory_store()
            mem_store.learn_from_task(
                self.config.name, task, final_output,
                tool_calls=[tc["tool"] for tc in tool_calls_log],
                success="[Error" not in final_output,
            )
        except Exception:
            pass

        return AgentResult(
            agent_name=self.config.name,
            task=task,
            output=final_output,
            usage=total_usage,
            tool_calls=tool_calls_log,
            iterations=iteration + 1,
            trajectory_id=traj_id,
        )

    async def run_async(self, task: str, context: str = "") -> AgentResult:
        """Async version of run."""
        return self.run(task, context)

    async def run_stream(self, task: str, context: str = ""):
        """Stream the response token by token."""
        task_msg = task
        if context:
            task_msg = f"{task}\n\n[Context]:\n{context}"
        self.memory.append(Message(role="user", content=task_msg))

        full_content = ""
        async for chunk in self.model.chat_stream(self.memory, temperature=self.config.temperature):
            full_content += chunk
            yield chunk

        self.memory.append(Message(role="assistant", content=full_content))

    def _spawn_sub_agent(self, name: str, role: str, task: str, model: str) -> AgentResult:
        """Spawn a sub-agent for a specific task."""
        sub_config = AgentConfig(
            name=f"{self.config.name}/{name}",
            role=role,
            goal=f"Complete the sub-task: {task[:100]}",
            model=model or self.config.model,
            tools=self.config.tools,
            max_iterations=5,
            verbose=self.config.verbose,
            memory_enabled=False,  # Sub-agents don't persist memory
        )
        sub_agent = Agent(sub_config, self.tool_registry)
        return sub_agent.run(task)

    def spawn_sub_agent(self, name: str, role: str, task: str, model: Optional[str] = None) -> AgentResult:
        """Public method to spawn a sub-agent."""
        return self._spawn_sub_agent(name, role, task, model or self.config.model)

    def reset_memory(self):
        """Reset agent memory, keeping only system prompt."""
        system_msg = self.memory[0]
        self.memory = [system_msg]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.config.name,
            "role": self.config.role,
            "goal": self.config.goal,
            "model": self.config.model,
            "tools": self.config.tools,
            "memory_length": len(self.memory),
        }


class AgentBuilder:
    """Fluent builder for creating agents."""

    def __init__(self):
        self._config = AgentConfig(name="Agent")

    def name(self, name: str) -> "AgentBuilder":
        self._config.name = name
        return self

    def role(self, role: str) -> "AgentBuilder":
        self._config.role = role
        return self

    def goal(self, goal: str) -> "AgentBuilder":
        self._config.goal = goal
        return self

    def backstory(self, backstory: str) -> "AgentBuilder":
        self._config.backstory = backstory
        return self

    def model(self, model: str) -> "AgentBuilder":
        self._config.model = model
        return self

    def tools(self, *tools: str) -> "AgentBuilder":
        self._config.tools = list(tools)
        return self

    def temperature(self, temp: float) -> "AgentBuilder":
        self._config.temperature = temp
        return self

    def build(self) -> Agent:
        return Agent(self._config)
