"""
AgenticS Tool System — Modular tool framework
"""

import os
import json
import subprocess
import asyncio
from typing import Callable, Optional
from dataclasses import dataclass, field


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema
    function: Callable
    async_func: Optional[Callable] = None


class ToolRegistry:
    """Register and manage tools for agents."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._register_builtins()

    def register(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def register_function(
        self,
        name: str,
        description: str,
        parameters: dict,
        function: Callable,
        async_func: Optional[Callable] = None,
    ):
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            function=function,
            async_func=async_func,
        )

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def to_openai_tools(self, tool_names: Optional[list[str]] = None) -> list[dict]:
        """Convert to OpenAI function calling format."""
        tools = []
        names = tool_names or self._tools.keys()
        for name in names:
            if name in self._tools:
                t = self._tools[name]
                tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                })
        return tools

    def execute(self, name: str, **kwargs) -> str:
        """Execute a tool synchronously."""
        tool = self.get(name)
        if not tool:
            return f"[Tool '{name}' not found]"
        try:
            result = tool.function(**kwargs)
            return str(result)
        except Exception as e:
            return f"[Tool error: {e}]"

    async def execute_async(self, name: str, **kwargs) -> str:
        """Execute a tool asynchronously."""
        tool = self.get(name)
        if not tool:
            return f"[Tool '{name}' not found]"
        try:
            if tool.async_func:
                result = await tool.async_func(**kwargs)
            else:
                result = tool.function(**kwargs)
            return str(result)
        except Exception as e:
            return f"[Tool error: {e}]"

    def _register_builtins(self):
        """Register built-in tools."""
        # File read
        self.register_function(
            name="file_read",
            description="Read contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                },
                "required": ["path"],
            },
            function=self._file_read,
        )

        # File write
        self.register_function(
            name="file_write",
            description="Write content to a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
            function=self._file_write,
        )

        # Shell command
        self.register_function(
            name="shell",
            description="Execute a shell command",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                },
                "required": ["command"],
            },
            function=self._shell,
        )

        # Web search (using a simple approach)
        self.register_function(
            name="web_search",
            description="Search the web for information",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results", "default": 5},
                },
                "required": ["query"],
            },
            function=self._web_search,
        )

        # List files
        self.register_function(
            name="list_files",
            description="List files in a directory",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path", "default": "."},
                },
            },
            function=self._list_files,
        )

        # Python execute
        self.register_function(
            name="python_execute",
            description="Execute Python code and return output",
            parameters={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                },
                "required": ["code"],
            },
            function=self._python_execute,
        )

    # --- Built-in tool implementations ---

    @staticmethod
    def _file_read(path: str) -> str:
        try:
            with open(path, "r") as f:
                return f.read()
        except FileNotFoundError:
            return f"[File not found: {path}]"
        except Exception as e:
            return f"[Error reading file: {e}]"

    @staticmethod
    def _file_write(path: str, content: str) -> str:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return f"[Written {len(content)} bytes to {path}]"
        except Exception as e:
            return f"[Error writing file: {e}]"

    @staticmethod
    def _shell(command: str, timeout: int = 30) -> str:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr: {result.stderr}]"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output[:5000]  # Limit output
        except subprocess.TimeoutExpired:
            return "[Command timed out]"
        except Exception as e:
            return f"[Shell error: {e}]"

    @staticmethod
    def _web_search(query: str, num_results: int = 5) -> str:
        """Simple web search using DuckDuckGo instant answer."""
        import urllib.request
        import urllib.parse
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
            req = urllib.request.Request(url, headers={"User-Agent": "AgenticS/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            results = []
            if data.get("AbstractText"):
                results.append(f"Summary: {data['AbstractText']}")
            for r in data.get("RelatedTopics", [])[:num_results]:
                if "Text" in r:
                    results.append(f"- {r['Text'][:200]}")
            return "\n".join(results) if results else "[No results found]"
        except Exception as e:
            return f"[Search error: {e}]"

    @staticmethod
    def _list_files(path: str = ".") -> str:
        try:
            entries = os.listdir(path)
            result = []
            for e in sorted(entries):
                full = os.path.join(path, e)
                if os.path.isdir(full):
                    result.append(f"📁 {e}/")
                else:
                    size = os.path.getsize(full)
                    result.append(f"📄 {e} ({size} bytes)")
            return "\n".join(result) if result else "[Empty directory]"
        except Exception as e:
            return f"[Error: {e}]"

    @staticmethod
    def _python_execute(code: str, timeout: int = 30) -> str:
        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True, text=True, timeout=timeout
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr: {result.stderr}]"
            return output[:5000] if output else "[No output]"
        except subprocess.TimeoutExpired:
            return "[Execution timed out]"
        except Exception as e:
            return f"[Error: {e}]"


# Global registry
_global_registry = None


def get_tool_registry() -> ToolRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry
