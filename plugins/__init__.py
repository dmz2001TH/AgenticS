"""
AgenticS Plugin System — Dynamic tool/skill loading
Inspired by Soul Brews Studio's arra-oracle-skills-cli + OpenClaw skill system
"""

import os
import sys
import json
import importlib
import importlib.util
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field

from tools import ToolDefinition, ToolRegistry, get_tool_registry


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str
    author: str
    tools: list[str] = field(default_factory=list)
    enabled: bool = True
    path: str = ""


class PluginManager:
    """Manage tool plugins — install, load, unload."""

    def __init__(self, plugins_dir: Optional[str] = None):
        if plugins_dir:
            self.plugins_dir = Path(plugins_dir)
        else:
            # Default: project root's plugins/ directory
            self.plugins_dir = Path(__file__).parent.parent / "plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_plugins: dict[str, PluginInfo] = {}
        self._registry = get_tool_registry()

    def discover_plugins(self) -> list[PluginInfo]:
        """Discover available plugins in the plugins directory."""
        plugins = []
        for item in self.plugins_dir.iterdir():
            if item.is_dir() and (item / "plugin.json").exists():
                try:
                    with open(item / "plugin.json") as f:
                        data = json.load(f)
                    plugins.append(PluginInfo(
                        name=data.get("name", item.name),
                        version=data.get("version", "0.1.0"),
                        description=data.get("description", ""),
                        author=data.get("author", "unknown"),
                        tools=data.get("tools", []),
                        path=str(item),
                    ))
                except Exception as e:
                    print(f"  ⚠️ Failed to read plugin {item.name}: {e}")
        return plugins

    def load_plugin(self, plugin_path: str) -> bool:
        """Load a single plugin."""
        plugin_dir = Path(plugin_path)
        plugin_json = plugin_dir / "plugin.json"
        init_file = plugin_dir / "__init__.py"

        if not plugin_json.exists():
            return False

        with open(plugin_json) as f:
            data = json.load(f)

        plugin_name = data.get("name", plugin_dir.name)

        if init_file.exists():
            spec = importlib.util.spec_from_file_location(
                f"agentic_s.plugins.{plugin_name}",
                str(init_file),
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

                # Call register_tools if available
                if hasattr(module, "register_tools"):
                    module.register_tools(self._registry)

        info = PluginInfo(
            name=plugin_name,
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", "unknown"),
            tools=data.get("tools", []),
            path=str(plugin_path),
        )
        self._loaded_plugins[plugin_name] = info
        return True

    def load_all_plugins(self):
        """Load all discovered plugins."""
        for plugin in self.discover_plugins():
            try:
                if self.load_plugin(plugin.path):
                    print(f"  🔌 Loaded plugin: {plugin.name} v{plugin.version}")
            except Exception as e:
                print(f"  ❌ Failed to load plugin {plugin.name}: {e}")

    def get_loaded_plugins(self) -> list[PluginInfo]:
        """Get list of loaded plugins."""
        return list(self._loaded_plugins.values())

    def create_plugin_template(self, name: str, description: str = ""):
        """Create a new plugin template."""
        plugin_dir = self.plugins_dir / name
        plugin_dir.mkdir(exist_ok=True)

        # plugin.json
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump({
                "name": name,
                "version": "0.1.0",
                "description": description or f"Custom plugin: {name}",
                "author": "user",
                "tools": [f"{name}_example"],
            }, f, indent=2)

        # __init__.py template
        with open(plugin_dir / "__init__.py", "w") as f:
            f.write(f'''"""
Plugin: {name}
{description}
"""

from tools import ToolRegistry


def register_tools(registry: ToolRegistry):
    """Register tools provided by this plugin."""

    def example_tool(query: str) -> str:
        """Example tool — replace with your implementation."""
        return f"[{name}] Processed: {{query}}"

    registry.register_function(
        name="{name}_example",
        description="Example tool from {name} plugin",
        parameters={{
            "type": "object",
            "properties": {{
                "query": {{"type": "string", "description": "Input query"}},
            }},
            "required": ["query"],
        }},
        function=example_tool,
    )
''')

        return plugin_dir


# Global plugin manager
_manager = None


def get_plugin_manager(plugins_dir: Optional[str] = None) -> PluginManager:
    global _manager
    if _manager is None:
        _manager = PluginManager(plugins_dir)
    return _manager
