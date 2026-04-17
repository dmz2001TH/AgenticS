"""
AgenticS Memory System — Persistent conversation memory with semantic search
Inspired by Hermes Agent's self-improving memory + OpenClaw's memory system
"""

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class MemoryEntry:
    id: str
    role: str  # "user", "assistant", "system", "tool"
    content: str
    agent_name: str
    session_id: str
    timestamp: str
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class UserProfile:
    name: str = ""
    preferences: dict = field(default_factory=dict)
    interaction_count: int = 0
    topics_of_interest: list[str] = field(default_factory=list)
    language: str = "th"
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now


@dataclass
class AgentMemory:
    """Per-agent learned memory — skills, patterns, user preferences."""
    agent_name: str
    learned_patterns: list[dict] = field(default_factory=list)
    successful_approaches: list[dict] = field(default_factory=list)
    frequent_tools: dict = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class MemoryStore:
    """Persistent memory storage with simple keyword search."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(__file__).parent.parent / "memory_store"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir = self.base_dir / "conversations"
        self.agents_dir = self.base_dir / "agents"
        self.profiles_dir = self.base_dir / "profiles"
        self.conversations_dir.mkdir(exist_ok=True)
        self.agents_dir.mkdir(exist_ok=True)
        self.profiles_dir.mkdir(exist_ok=True)

    # --- Conversations ---

    def save_message(self, entry: MemoryEntry):
        """Save a single message to a session file."""
        session_file = self.conversations_dir / f"{entry.session_id}.jsonl"
        with open(session_file, "a") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    def get_session_history(self, session_id: str, limit: int = 50) -> list[MemoryEntry]:
        """Get messages from a session."""
        session_file = self.conversations_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            return []
        entries = []
        with open(session_file, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entries.append(MemoryEntry(**data))
        return entries[-limit:]

    def search_messages(self, query: str, limit: int = 20) -> list[MemoryEntry]:
        """Simple keyword search across all sessions."""
        query_lower = query.lower()
        results = []
        for session_file in self.conversations_dir.glob("*.jsonl"):
            with open(session_file, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        content = data.get("content", "").lower()
                        if query_lower in content:
                            results.append(MemoryEntry(**data))
        # Sort by timestamp, newest first
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """List all sessions with summary info."""
        sessions = []
        for session_file in sorted(self.conversations_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True):
            session_id = session_file.stem
            messages = self.get_session_history(session_id, limit=2)
            if messages:
                sessions.append({
                    "session_id": session_id,
                    "last_message": messages[-1].content[:100] if messages else "",
                    "message_count": sum(1 for _ in open(session_file)),
                    "last_updated": messages[-1].timestamp if messages else "",
                })
            if len(sessions) >= limit:
                break
        return sessions

    # --- User Profile ---

    def get_user_profile(self, user_id: str = "default") -> UserProfile:
        """Get or create user profile."""
        profile_file = self.profiles_dir / f"{user_id}.json"
        if profile_file.exists():
            with open(profile_file, "r") as f:
                data = json.load(f)
                return UserProfile(**data)
        return UserProfile(name=user_id)

    def save_user_profile(self, profile: UserProfile, user_id: str = "default"):
        """Save user profile."""
        profile.updated_at = datetime.now().isoformat()
        profile_file = self.profiles_dir / f"{user_id}.json"
        with open(profile_file, "w") as f:
            json.dump(asdict(profile), f, ensure_ascii=False, indent=2)

    def update_user_from_conversation(self, session_id: str, user_id: str = "default"):
        """Extract and update user preferences from conversation."""
        profile = self.get_user_profile(user_id)
        history = self.get_session_history(session_id, limit=20)

        # Simple keyword extraction for topics
        user_messages = [m.content for m in history if m.role == "user"]
        all_text = " ".join(user_messages).lower()

        # Extract common keywords
        keywords = set()
        for word in all_text.split():
            if len(word) > 3:
                keywords.add(word)

        if keywords:
            profile.topics_of_interest = list(keywords)[:20]
        profile.interaction_count += len(user_messages)
        self.save_user_profile(profile, user_id)

    # --- Agent Memory ---

    def get_agent_memory(self, agent_name: str) -> AgentMemory:
        """Get agent's learned memory."""
        agent_file = self.agents_dir / f"{agent_name}.json"
        if agent_file.exists():
            with open(agent_file, "r") as f:
                data = json.load(f)
                return AgentMemory(**data)
        return AgentMemory(agent_name=agent_name)

    def save_agent_memory(self, memory: AgentMemory):
        """Save agent memory."""
        agent_file = self.agents_dir / f"{memory.agent_name}.json"
        with open(agent_file, "w") as f:
            json.dump(asdict(memory), f, ensure_ascii=False, indent=2)

    def learn_from_task(self, agent_name: str, task: str, result: str, tools_used: list[str], success: bool):
        """Agent learns from completed task."""
        memory = self.get_agent_memory(agent_name)

        if success:
            memory.successful_approaches.append({
                "task_pattern": task[:200],
                "tools_used": tools_used,
                "timestamp": datetime.now().isoformat(),
            })
            # Keep last 50
            memory.successful_approaches = memory.successful_approaches[-50:]

        # Track tool usage
        for tool in tools_used:
            memory.frequent_tools[tool] = memory.frequent_tools.get(tool, 0) + 1

        self.save_agent_memory(memory)

    def get_similar_past_tasks(self, agent_name: str, task: str, limit: int = 5) -> list[dict]:
        """Find similar past tasks for an agent."""
        memory = self.get_agent_memory(agent_name)
        task_lower = task.lower()
        results = []
        for approach in memory.successful_approaches:
            pattern = approach.get("task_pattern", "").lower()
            # Simple word overlap similarity
            task_words = set(task_lower.split())
            pattern_words = set(pattern.split())
            if task_words and pattern_words:
                overlap = len(task_words & pattern_words) / len(task_words | pattern_words)
                if overlap > 0.2:
                    results.append({**approach, "similarity": overlap})
        results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return results[:limit]


# Global store
_store = None


def get_memory_store(base_dir: Optional[str] = None) -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore(base_dir)
    return _store
