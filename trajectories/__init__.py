"""
AgenticS Trajectory System — Export and manage execution trajectories
Inspired by Hermes Agent's batch trajectory generation
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class TrajectoryStep:
    step_type: str  # "thought", "action", "observation", "result"
    content: str
    agent_name: str
    timestamp: str
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    tool_result: Optional[str] = None


@dataclass
class Trajectory:
    id: str
    task: str
    agent_name: str
    crew_name: Optional[str]
    steps: list[TrajectoryStep] = field(default_factory=list)
    final_result: str = ""
    total_tokens: int = 0
    duration_seconds: float = 0.0
    success: bool = True
    created_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def to_training_format(self) -> dict:
        """Convert to a format suitable for RL/training."""
        messages = []
        messages.append({"role": "system", "content": f"You are {self.agent_name}."})
        messages.append({"role": "user", "content": self.task})

        for step in self.steps:
            if step.step_type == "thought":
                messages.append({"role": "assistant", "content": f"[thinking] {step.content}"})
            elif step.step_type == "action":
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": str(uuid.uuid4())[:8],
                        "function": {
                            "name": step.tool_name,
                            "arguments": json.dumps(step.tool_args or {}),
                        },
                    }],
                })
            elif step.step_type == "observation":
                messages.append({"role": "tool", "content": step.content})
            elif step.step_type == "result":
                messages.append({"role": "assistant", "content": step.content})

        return {
            "id": self.id,
            "task": self.task,
            "agent": self.agent_name,
            "success": self.success,
            "tokens": self.total_tokens,
            "duration": self.duration_seconds,
            "messages": messages,
            "created_at": self.created_at,
        }


class TrajectoryStore:
    """Store and export execution trajectories."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(__file__).parent.parent / "trajectory_store"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._active_trajectories: dict[str, Trajectory] = {}

    def start_trajectory(self, task: str, agent_name: str, crew_name: Optional[str] = None) -> Trajectory:
        """Start tracking a new trajectory."""
        traj = Trajectory(
            id=str(uuid.uuid4())[:8],
            task=task,
            agent_name=agent_name,
            crew_name=crew_name,
        )
        self._active_trajectories[traj.id] = traj
        return traj

    def add_step(self, trajectory_id: str, step: TrajectoryStep):
        """Add a step to an active trajectory."""
        if trajectory_id in self._active_trajectories:
            self._active_trajectories[trajectory_id].steps.append(step)

    def finish_trajectory(self, trajectory_id: str, final_result: str, success: bool = True) -> Optional[Trajectory]:
        """Finish and save a trajectory."""
        if trajectory_id not in self._active_trajectories:
            return None

        traj = self._active_trajectories.pop(trajectory_id)
        traj.final_result = final_result
        traj.success = success

        # Save to file
        filename = f"{traj.created_at[:10]}_{traj.id}.json"
        filepath = self.base_dir / filename
        with open(filepath, "w") as f:
            json.dump(traj.to_dict(), f, ensure_ascii=False, indent=2)

        return traj

    def get_trajectories(self, limit: int = 20) -> list[dict]:
        """List saved trajectories."""
        files = sorted(self.base_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        results = []
        for f in files[:limit]:
            try:
                with open(f) as fh:
                    data = json.load(fh)
                    results.append({
                        "id": data.get("id"),
                        "task": data.get("task", "")[:100],
                        "agent": data.get("agent_name"),
                        "success": data.get("success"),
                        "steps": len(data.get("steps", [])),
                        "tokens": data.get("total_tokens", 0),
                        "created_at": data.get("created_at"),
                    })
            except Exception:
                pass
        return results

    def export_for_training(self, output_path: str, min_success: bool = True):
        """Export all trajectories in training format."""
        results = []
        for f in self.base_dir.glob("*.json"):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                    if min_success and not data.get("success"):
                        continue
                    traj = Trajectory(**{
                        k: v for k, v in data.items()
                        if k in Trajectory.__dataclass_fields__
                    })
                    results.append(traj.to_training_format())
            except Exception:
                pass

        with open(output_path, "w") as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        return len(results)


import os  # noqa: E402

_store = None


def get_trajectory_store(base_dir: Optional[str] = None) -> TrajectoryStore:
    global _store
    if _store is None:
        _store = TrajectoryStore(base_dir)
    return _store
