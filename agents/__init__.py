"""
AgenticS Agent System — Role-based AI agents with memory and tools
"""

import json
import uuid
from datetime import datetime
from typing import Optional
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


@dataclass
class AgentResult:
    agent_name: str
    task: str
    output: str
    usage: dict = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)
    iterations: int = 0
    timestamp: str = ""

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
        }


class Agent:
    """A role-based AI agent with memory and tool execution."""

    def __init__(self, config: AgentConfig, tool_registry: Optional[ToolRegistry] = None):
        self.config = config
        self.model = ModelClient(model_name=config.model)
        self.tool_registry = tool_registry or get_tool_registry()
        self.memory: list[Message] = []
        self.id = str(uuid.uuid4())[:8]

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
"""
        self.memory.append(Message(role="system", content=system_prompt))

    def run(self, task: str, context: str = "") -> AgentResult:
        """Execute a task with ReAct-style tool calling loop."""
        # Add task to memory
        task_msg = task
        if context:
            task_msg = f"{task}\n\n[Context from previous agent]:\n{context}"
        self.memory.append(Message(role="user", content=task_msg))

        tool_calls_log = []
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        final_output = ""

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

            # Check if model wants to call tools
            if response.raw and response.raw.get("choices", [{}])[0].get("message", {}).get("tool_calls"):
                # Model wants to use tools
                tool_calls = response.raw["choices"][0]["message"]["tool_calls"]
                self.memory.append(Message(role="assistant", content=response.content or ""))

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    result = self.tool_registry.execute(fn_name, **fn_args)

                    tool_calls_log.append({
                        "tool": fn_name,
                        "args": fn_args,
                        "result": result[:500],
                    })

                    self.memory.append(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tc["id"],
                    ))

                if self.config.verbose:
                    print(f"  [Agent {self.config.name}] Iteration {iteration + 1}: used tools {[tc['function']['name'] for tc in tool_calls]}")
            else:
                # Model gave a final answer
                final_output = response.content
                self.memory.append(Message(role="assistant", content=final_output))
                break
        else:
            final_output = final_output or "[Max iterations reached without a final answer]"

        return AgentResult(
            agent_name=self.config.name,
            task=task,
            output=final_output,
            usage=total_usage,
            tool_calls=tool_calls_log,
            iterations=iteration + 1 if "iteration" in dir() else 0,
        )

    async def run_async(self, task: str, context: str = "") -> AgentResult:
        """Async version of run."""
        return self.run(task, context)  # Delegate to sync for now

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
