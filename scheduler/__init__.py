"""
AgenticS Scheduler — Cron-like task scheduling for crews and agents
Inspired by maw-js loops + OpenClaw cron system
"""

import json
import uuid
import asyncio
import threading
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum


class ScheduleType(str, Enum):
    ONCE = "once"           # Run once at specific time
    INTERVAL = "interval"   # Run every N seconds
    CRON = "cron"           # Cron-style (simplified: daily, weekly, etc.)
    MANUAL = "manual"       # Triggered manually only


class ScheduleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScheduledTask:
    id: str
    name: str
    description: str
    task_prompt: str
    crew_name: Optional[str]
    agent_name: Optional[str]
    schedule_type: ScheduleType
    schedule_value: str  # e.g. "3600" for interval, "daily 09:00" for cron
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    last_result: Optional[str] = None
    created_at: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schedule_type"] = self.schedule_type.value
        d["status"] = self.status.value
        return d


class Scheduler:
    """Task scheduler with loop execution."""

    def __init__(self):
        self.tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: dict[str, Callable] = {}

    def register_callback(self, name: str, callback: Callable):
        """Register a callback for task execution."""
        self._callbacks[name] = callback

    def add_task(self, task: ScheduledTask) -> str:
        """Add a scheduled task."""
        self.tasks[task.id] = task
        return task.id

    def create_task(
        self,
        name: str,
        task_prompt: str,
        crew_name: Optional[str] = None,
        agent_name: Optional[str] = None,
        schedule_type: ScheduleType = ScheduleType.MANUAL,
        schedule_value: str = "",
        description: str = "",
        tags: Optional[list[str]] = None,
    ) -> ScheduledTask:
        """Create and register a new scheduled task."""
        task = ScheduledTask(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            task_prompt=task_prompt,
            crew_name=crew_name,
            agent_name=agent_name,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            tags=tags or [],
        )
        self.add_task(task)
        return task

    def remove_task(self, task_id: str):
        """Remove a scheduled task."""
        self.tasks.pop(task_id, None)

    def pause_task(self, task_id: str):
        """Pause a scheduled task."""
        if task_id in self.tasks:
            self.tasks[task_id].status = ScheduleStatus.PAUSED

    def resume_task(self, task_id: str):
        """Resume a paused task."""
        if task_id in self.tasks:
            self.tasks[task_id].status = ScheduleStatus.ACTIVE

    def trigger_task(self, task_id: str, callback: Optional[Callable] = None) -> Optional[dict]:
        """Manually trigger a task immediately."""
        task = self.tasks.get(task_id)
        if not task:
            return None

        task.last_run = datetime.now().isoformat()
        task.run_count += 1

        result = {
            "task_id": task_id,
            "name": task.name,
            "prompt": task.task_prompt,
            "crew": task.crew_name,
            "agent": task.agent_name,
            "triggered_at": task.last_run,
        }

        if callback:
            try:
                exec_result = callback(task)
                result["result"] = exec_result
                task.last_result = "success"
            except Exception as e:
                result["error"] = str(e)
                task.last_result = f"error: {e}"

        return result

    def get_tasks(self, status: Optional[ScheduleStatus] = None) -> list[ScheduledTask]:
        """Get all tasks, optionally filtered by status."""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a specific task."""
        return self.tasks.get(task_id)

    def to_dict(self) -> list[dict]:
        """Serialize all tasks."""
        return [t.to_dict() for t in self.tasks.values()]

    def save_to_file(self, path: str):
        """Save tasks to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def load_from_file(self, path: str):
        """Load tasks from JSON file."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
                for item in data:
                    item["schedule_type"] = ScheduleType(item["schedule_type"])
                    item["status"] = ScheduleStatus(item["status"])
                    task = ScheduledTask(**item)
                    self.tasks[task.id] = task
        except FileNotFoundError:
            pass


# Global scheduler
_scheduler = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler
