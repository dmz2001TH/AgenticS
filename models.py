"""
AgenticS Model Layer — Multi-Model abstraction using LiteLLM
Supports: Gemini, OpenAI, Claude, Ollama, OpenRouter, Gemini CLI
"""

import os
import json
import subprocess
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field

from config import get_config

# LiteLLM handles all model providers
try:
    import litellm
    litellm.suppress_debug_info = True
    litellm.set_verbose = False
    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False
    litellm = None


@dataclass
class Message:
    role: str  # "system", "user", "assistant", "tool"
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class ModelResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""
    raw: dict = field(default_factory=dict)


# Provider name mapping for LiteLLM
PROVIDER_MAP = {
    "google": "gemini",
    "openai": "openai",
    "anthropic": "anthropic",
    "ollama": "ollama",
    "openrouter": "openrouter",
    "gemini-cli": "gemini-cli",
}


def _build_litellm_model_id(provider_config: dict) -> str:
    """Build LiteLLM model identifier from config."""
    provider = provider_config.get("provider", "google")
    model = provider_config.get("model", "gemini-2.0-flash")

    if provider == "google":
        return f"gemini/{model}"
    elif provider == "openai":
        return model
    elif provider == "anthropic":
        return f"anthropic/{model}"
    elif provider == "ollama":
        return f"ollama/{model}"
    elif provider == "openrouter":
        return f"openrouter/{model}"
    elif provider == "gemini-cli":
        return "gemini-cli"  # Special handling
    else:
        return f"{provider}/{model}"


def _set_api_keys(provider_config: dict):
    """Set API keys in environment for LiteLLM."""
    api_key = provider_config.get("api_key")
    provider = provider_config.get("provider", "")

    if api_key:
        key_env_map = {
            "google": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_var = key_env_map.get(provider)
        if env_var and not os.environ.get(env_var):
            os.environ[env_var] = api_key


def _call_gemini_cli(messages: list[dict], temperature: float = 0.7, **kwargs) -> str:
    """Call Gemini CLI directly."""
    # Build prompt from messages
    prompt_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            prompt_parts.append(f"[System]: {content}")
        elif role == "user":
            prompt_parts.append(content)
        elif role == "assistant":
            prompt_parts.append(f"[Assistant]: {content}")
        elif role == "tool":
            prompt_parts.append(f"[Tool Result]: {content}")

    prompt = "\n".join(prompt_parts)

    try:
        # Try `gemini` CLI
        result = subprocess.run(
            ["gemini", "--prompt", prompt],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "TERM": "dumb"},
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        # Fallback: try with different flag
        result = subprocess.run(
            ["gemini", "-p", prompt],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "TERM": "dumb"},
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return f"[Gemini CLI error: {result.stderr}]"
    except FileNotFoundError:
        return "[Gemini CLI not installed. Install: npm i -g @anthropic-ai/gemini-cli OR use API key instead]"
    except subprocess.TimeoutExpired:
        return "[Gemini CLI timed out]"
    except Exception as e:
        return f"[Gemini CLI error: {e}]"


def _call_gemini_cli_stream(messages: list[dict], temperature: float = 0.7, **kwargs):
    """Stream from Gemini CLI (simplified — returns full output then yields)."""
    result = _call_gemini_cli(messages, temperature, **kwargs)
    # Yield word by word for streaming effect
    words = result.split()
    for i in range(0, len(words), 3):
        yield " ".join(words[i:i+3]) + " "


class ModelClient:
    """Unified model client supporting multiple providers."""

    def __init__(self, model_name: Optional[str] = None, config=None):
        self.config = config or get_config()
        self.model_name = model_name or self.config.default_model
        self.provider_config = self.config.get_model_config(self.model_name)
        self.provider = self.provider_config.get("provider", "google")
        self.model_id = _build_litellm_model_id(self.provider_config)
        _set_api_keys(self.provider_config)

    def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Synchronous chat completion."""
        if not _LITELLM_AVAILABLE and self.provider != "gemini-cli":
            return ModelResponse(
                content="[litellm not installed. Run: pip install -r requirements.txt]",
                model="none",
                finish_reason="error",
            )

        formatted = self._format_messages(messages)

        # Gemini CLI special handling
        if self.provider == "gemini-cli":
            content = _call_gemini_cli(formatted, temperature)
            return ModelResponse(
                content=content,
                model="gemini-cli",
                finish_reason="stop",
            )

        params = {
            "model": self.model_id,
            "messages": formatted,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if self.provider == "ollama":
            params["api_base"] = self.provider_config.get("api_base", "http://localhost:11434")

        if tools:
            params["tools"] = tools

        params.update(kwargs)

        try:
            response = litellm.completion(**params)
            choice = response.choices[0]
            return ModelResponse(
                content=choice.message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                },
                finish_reason=choice.finish_reason or "",
                raw=response.model_dump() if hasattr(response, "model_dump") else {},
            )
        except Exception as e:
            return ModelResponse(
                content=f"[Model Error: {e}]",
                model=self.model_id,
                finish_reason="error",
            )

    async def chat_async(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ModelResponse:
        """Async chat completion."""
        formatted = self._format_messages(messages)

        if self.provider == "gemini-cli":
            content = _call_gemini_cli(formatted, temperature)
            return ModelResponse(content=content, model="gemini-cli", finish_reason="stop")

        if not _LITELLM_AVAILABLE:
            return ModelResponse(content="[litellm not installed]", model="none", finish_reason="error")

        params = {
            "model": self.model_id,
            "messages": formatted,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.provider == "ollama":
            params["api_base"] = self.provider_config.get("api_base", "http://localhost:11434")
        params.update(kwargs)

        try:
            response = await litellm.acompletion(**params)
            choice = response.choices[0]
            return ModelResponse(
                content=choice.message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                },
                finish_reason=choice.finish_reason or "",
            )
        except Exception as e:
            return ModelResponse(
                content=f"[Model Error: {e}]",
                model=self.model_id,
                finish_reason="error",
            )

    async def chat_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Streaming chat completion."""
        formatted = self._format_messages(messages)

        # Gemini CLI streaming
        if self.provider == "gemini-cli":
            for chunk in _call_gemini_cli_stream(formatted, temperature):
                yield chunk
            return

        if not _LITELLM_AVAILABLE:
            yield "[litellm not installed]"
            return

        params = {
            "model": self.model_id,
            "messages": formatted,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if self.provider == "ollama":
            params["api_base"] = self.provider_config.get("api_base", "http://localhost:11434")
        params.update(kwargs)

        try:
            response = await litellm.acompletion(**params)
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"[Model Error: {e}]"

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        formatted = []
        for msg in messages:
            entry = {"role": msg.role, "content": msg.content}
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            formatted.append(entry)
        return formatted


def list_available_models() -> list[str]:
    """List all configured model names."""
    config = get_config()
    return list(config.model_providers.keys())
