"""
AgenticS Server — FastAPI backend with WebSocket streaming, scheduler, plugins
"""

import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_config
from agents import Agent, AgentConfig, AgentResult
from orchestration import Crew, CrewConfig, CrewResult, ProcessType, load_crew_from_yaml
from models import list_available_models
from tools import get_tool_registry

# --- App Setup ---
app = FastAPI(title="AgenticS", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- State ---
config = get_config()
tool_registry = get_tool_registry()
crews: dict[str, Crew] = {}
sessions: dict[str, dict] = {}


# --- Request/Response Models ---
class CreateAgentRequest(BaseModel):
    name: str
    role: str = "Assistant"
    goal: str = "Help with tasks"
    backstory: str = ""
    model: str = "gemini"
    tools: list[str] = []

class CreateCrewRequest(BaseModel):
    name: str
    description: str = ""
    agents: list[CreateAgentRequest]
    process: str = "sequential"

class TaskRequest(BaseModel):
    crew_name: str
    task: str

class ChatRequest(BaseModel):
    message: str
    agent_name: Optional[str] = None
    model: Optional[str] = None

class ScheduleRequest(BaseModel):
    name: str
    task_prompt: str
    crew_name: Optional[str] = None
    agent_name: Optional[str] = None
    schedule_type: str = "manual"
    schedule_value: str = ""
    description: str = ""
    tags: list[str] = []

class PluginCreateRequest(BaseModel):
    name: str
    description: str = ""


# --- API Routes ---
@app.get("/")
async def index():
    """Serve the dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard" / "static" / "index.html"
    return FileResponse(dashboard_path)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.2.0", "timestamp": datetime.now().isoformat()}


@app.get("/api/models")
async def get_models():
    """List available models."""
    return {"models": list_available_models(), "default": config.default_model}


@app.get("/api/tools")
async def get_tools():
    """List available tools."""
    return {"tools": tool_registry.list_tools()}


# --- Crew Management ---
@app.post("/api/crews")
async def create_crew(req: CreateCrewRequest):
    agent_configs = [
        AgentConfig(
            name=a.name, role=a.role, goal=a.goal,
            backstory=a.backstory, model=a.model, tools=a.tools,
        )
        for a in req.agents
    ]
    crew_config = CrewConfig(
        name=req.name,
        description=req.description,
        agents=agent_configs,
        process=ProcessType(req.process),
    )
    crew = Crew(crew_config, tool_registry)
    crews[req.name] = crew
    return {"status": "created", "crew": crew.to_dict()}

@app.get("/api/crews")
async def list_crews():
    return {"crews": [c.to_dict() for c in crews.values()]}

@app.get("/api/crews/{crew_name}")
async def get_crew(crew_name: str):
    if crew_name not in crews:
        raise HTTPException(404, "Crew not found")
    return crews[crew_name].to_dict()

@app.delete("/api/crews/{crew_name}")
async def delete_crew(crew_name: str):
    if crew_name not in crews:
        raise HTTPException(404, "Crew not found")
    del crews[crew_name]
    return {"status": "deleted"}


# --- Task Execution ---
@app.post("/api/run")
async def run_task(req: TaskRequest):
    if req.crew_name not in crews:
        raise HTTPException(404, f"Crew '{req.crew_name}' not found")
    crew = crews[req.crew_name]
    result = crew.run(req.task)
    return result.to_dict()


@app.post("/api/chat")
async def chat(req: ChatRequest):
    model_name = req.model or config.default_model
    agent_config = AgentConfig(
        name=req.agent_name or "ChatAgent",
        role="Conversational Assistant",
        goal="Help the user with any question or task",
        model=model_name,
    )
    agent = Agent(agent_config, tool_registry)
    result = agent.run(req.message)
    return result.to_dict()


# --- Scheduler ---
@app.get("/api/schedule")
async def list_scheduled_tasks():
    from scheduler import get_scheduler
    s = get_scheduler()
    return {"tasks": s.to_dict()}

@app.post("/api/schedule")
async def create_scheduled_task(req: ScheduleRequest):
    from scheduler import get_scheduler, ScheduleType
    s = get_scheduler()
    task = s.create_task(
        name=req.name,
        task_prompt=req.task_prompt,
        crew_name=req.crew_name,
        agent_name=req.agent_name,
        schedule_type=ScheduleType(req.schedule_type),
        schedule_value=req.schedule_value,
        description=req.description,
        tags=req.tags,
    )
    return {"status": "created", "task": task.to_dict()}

@app.post("/api/schedule/{task_id}/trigger")
async def trigger_task(task_id: str):
    from scheduler import get_scheduler
    s = get_scheduler()

    def execute(task):
        if task.crew_name and task.crew_name in crews:
            result = crews[task.crew_name].run(task.task_prompt)
            return result.final_output
        elif task.agent_name:
            agent_config = AgentConfig(name=task.agent_name, model=config.default_model)
            agent = Agent(agent_config, tool_registry)
            return agent.run(task.task_prompt).output
        else:
            return "No crew or agent configured for this task"

    result = s.trigger_task(task_id, callback=execute)
    if not result:
        raise HTTPException(404, "Task not found")
    return result

@app.delete("/api/schedule/{task_id}")
async def delete_scheduled_task(task_id: str):
    from scheduler import get_scheduler
    s = get_scheduler()
    s.remove_task(task_id)
    return {"status": "deleted"}

@app.patch("/api/schedule/{task_id}")
async def update_scheduled_task(task_id: str, action: str):
    from scheduler import get_scheduler
    s = get_scheduler()
    if action == "pause":
        s.pause_task(task_id)
    elif action == "resume":
        s.resume_task(task_id)
    return {"status": action}


# --- Memory ---
@app.get("/api/memory/sessions")
async def list_memory_sessions():
    from memory import get_memory_store
    store = get_memory_store()
    return {"sessions": store.list_sessions()}

@app.get("/api/memory/search")
async def search_memory(q: str, limit: int = 20):
    from memory import get_memory_store
    store = get_memory_store()
    results = store.search_messages(q, limit)
    return {"results": [{"content": r.content[:200], "agent": r.agent_name, "timestamp": r.timestamp} for r in results]}

@app.get("/api/memory/profile")
async def get_profile(user_id: str = "default"):
    from memory import get_memory_store
    store = get_memory_store()
    profile = store.get_user_profile(user_id)
    return {"profile": {
        "name": profile.name,
        "interaction_count": profile.interaction_count,
        "topics": profile.topics_of_interest[:10],
    }}


# --- Trajectories ---
@app.get("/api/trajectories")
async def list_trajectories(limit: int = 20):
    from trajectories import get_trajectory_store
    store = get_trajectory_store()
    return {"trajectories": store.get_trajectories(limit)}

@app.post("/api/trajectories/export")
async def export_trajectories(output_path: str = "training_data.jsonl"):
    from trajectories import get_trajectory_store
    store = get_trajectory_store()
    count = store.export_for_training(output_path)
    return {"status": "exported", "count": count, "path": output_path}


# --- Plugins ---
@app.get("/api/plugins")
async def list_plugins():
    from plugins import get_plugin_manager
    pm = get_plugin_manager()
    discovered = pm.discover_plugins()
    loaded = pm.get_loaded_plugins()
    return {"discovered": [{"name": p.name, "version": p.version, "description": p.description} for p in discovered],
            "loaded": [{"name": p.name, "version": p.version} for p in loaded]}

@app.post("/api/plugins")
async def create_plugin(req: PluginCreateRequest):
    from plugins import get_plugin_manager
    pm = get_plugin_manager()
    plugin_dir = pm.create_plugin_template(req.name, req.description)
    return {"status": "created", "path": str(plugin_dir)}

@app.post("/api/plugins/{name}/load")
async def load_plugin(name: str):
    from plugins import get_plugin_manager
    pm = get_plugin_manager()
    plugin_path = pm.plugins_dir / name
    if pm.load_plugin(str(plugin_path)):
        return {"status": "loaded"}
    raise HTTPException(404, "Plugin not found")


# --- WebSocket (Streaming Chat) ---
@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    session_id = str(id(websocket))
    sessions[session_id] = {"connected_at": datetime.now().isoformat()}

    # Save to memory
    try:
        from memory import get_memory_store, MemoryEntry
        mem_store = get_memory_store()
    except Exception:
        mem_store = None

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                msg = {"message": data}

            message = msg.get("message", "")
            model_name = msg.get("model", config.default_model)
            agent_name = msg.get("agent", "ChatAgent")
            crew_name = msg.get("crew", None)
            stream = msg.get("stream", True)

            # Save user message
            if mem_store:
                mem_store.save_message(MemoryEntry(
                    id=session_id[:8],
                    role="user",
                    content=message,
                    agent_name=agent_name,
                    session_id=session_id,
                    timestamp=datetime.now().isoformat(),
                ))

            if crew_name and crew_name in crews:
                # Run crew (non-streaming for now)
                await websocket.send_json({"type": "status", "content": f"👥 Running crew: {crew_name}..."})
                crew = crews[crew_name]
                result = crew.run(message)
                await websocket.send_json({
                    "type": "response",
                    "content": result.final_output,
                    "usage": result.total_usage,
                    "duration": result.duration_seconds,
                    "crew": crew_name,
                })
            elif stream:
                # Streaming single agent
                await websocket.send_json({"type": "status", "content": "🤔 Thinking..."})
                agent_config = AgentConfig(
                    name=agent_name,
                    role="Conversational Assistant",
                    goal="Help the user",
                    model=model_name,
                )
                agent = Agent(agent_config, tool_registry)

                # Send stream start
                await websocket.send_json({"type": "stream_start"})

                full_content = ""
                async for chunk in agent.run_stream(message):
                    full_content += chunk
                    await websocket.send_json({"type": "stream_chunk", "content": chunk})

                # Save to memory
                if mem_store:
                    mem_store.save_message(MemoryEntry(
                        id=session_id[:8],
                        role="assistant",
                        content=full_content,
                        agent_name=agent_name,
                        session_id=session_id,
                        timestamp=datetime.now().isoformat(),
                    ))

                await websocket.send_json({"type": "stream_end", "content": full_content})
            else:
                # Non-streaming single agent
                await websocket.send_json({"type": "status", "content": "🤔 กำลังคิด..."})
                agent_config = AgentConfig(
                    name=agent_name,
                    role="Conversational Assistant",
                    goal="Help the user",
                    model=model_name,
                )
                agent = Agent(agent_config, tool_registry)
                result = agent.run(message)

                if mem_store:
                    mem_store.save_message(MemoryEntry(
                        id=session_id[:8],
                        role="assistant",
                        content=result.output,
                        agent_name=agent_name,
                        session_id=session_id,
                        timestamp=datetime.now().isoformat(),
                    ))

                await websocket.send_json({
                    "type": "response",
                    "content": result.output,
                    "usage": result.usage,
                    "agent": agent_name,
                })

    except WebSocketDisconnect:
        # Update user profile from conversation
        if mem_store:
            try:
                mem_store.update_user_from_conversation(session_id)
            except Exception:
                pass
        sessions.pop(session_id, None)
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
        sessions.pop(session_id, None)


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": sessions}


# --- Auto-load default crews + plugins ---
def load_defaults():
    """Load crews, plugins, and scheduler state."""
    # Load crews
    crew_dir = Path(__file__).parent / "crews"
    if crew_dir.exists():
        for yaml_file in crew_dir.glob("*.yaml"):
            try:
                crew = load_crew_from_yaml(str(yaml_file), tool_registry)
                crews[crew.config.name] = crew
                print(f"  ✅ Crew: {crew.config.name}")
            except Exception as e:
                print(f"  ❌ Failed to load {yaml_file.name}: {e}")

    # Load plugins
    try:
        from plugins import get_plugin_manager
        pm = get_plugin_manager()
        pm.load_all_plugins()
    except Exception as e:
        print(f"  ⚠️ Plugin loading: {e}")

    # Load scheduler state
    try:
        from scheduler import get_scheduler
        s = get_scheduler()
        sched_file = Path(__file__).parent / "scheduler_state.json"
        if sched_file.exists():
            s.load_from_file(str(sched_file))
            print(f"  📋 Loaded {len(s.tasks)} scheduled tasks")
    except Exception as e:
        print(f"  ⚠️ Scheduler: {e}")


# --- Main ---
if __name__ == "__main__":
    import uvicorn

    server_cfg = config.server_config
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 7860)

    print(f"""
╔══════════════════════════════════════════╗
║         🤖 AgenticS v0.2.0              ║
║    Multi-Agent AI System                 ║
╠══════════════════════════════════════════╣
║  Dashboard:  http://localhost:{port}       ║
║  API Docs:   http://localhost:{port}/docs  ║
║  WebSocket:  ws://localhost:{port}/ws      ║
╠══════════════════════════════════════════╣
║  Features:                               ║
║  ✦ Streaming responses                   ║
║  ✦ Memory persistence                    ║
║  ✦ Multi-model (incl. Gemini CLI)        ║
║  ✦ Crew orchestration (4 types)          ║
║  ✦ Scheduled loops                       ║
║  ✦ Sub-agent spawning                    ║
║  ✦ Plugin system                         ║
║  ✦ Trajectory export                     ║
╚══════════════════════════════════════════╝
    """)

    load_defaults()
    uvicorn.run(app, host=host, port=port, log_level="info")
