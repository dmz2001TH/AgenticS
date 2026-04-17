"""
AgenticS Server — FastAPI backend with WebSocket real-time chat
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
app = FastAPI(title="AgenticS", version="0.1.0")
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
sessions: dict[str, dict] = {}  # WebSocket sessions


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


# --- API Routes ---
@app.get("/")
async def index():
    """Serve the dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard" / "static" / "index.html"
    return FileResponse(dashboard_path)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "timestamp": datetime.now().isoformat()}


@app.get("/api/models")
async def get_models():
    """List available models."""
    return {"models": list_available_models(), "default": config.default_model}


@app.get("/api/tools")
async def get_tools():
    """List available tools."""
    return {"tools": tool_registry.list_tools()}


@app.post("/api/crews")
async def create_crew(req: CreateCrewRequest):
    """Create a new crew."""
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
    """List all crews."""
    return {"crews": [c.to_dict() for c in crews.values()]}


@app.get("/api/crews/{crew_name}")
async def get_crew(crew_name: str):
    """Get crew details."""
    if crew_name not in crews:
        raise HTTPException(404, "Crew not found")
    return crews[crew_name].to_dict()


@app.delete("/api/crews/{crew_name}")
async def delete_crew(crew_name: str):
    """Delete a crew."""
    if crew_name not in crews:
        raise HTTPException(404, "Crew not found")
    del crews[crew_name]
    return {"status": "deleted"}


@app.post("/api/run")
async def run_task(req: TaskRequest):
    """Run a task on a crew."""
    if req.crew_name not in crews:
        raise HTTPException(404, f"Crew '{req.crew_name}' not found")
    crew = crews[req.crew_name]
    result = crew.run(req.task)
    return result.to_dict()


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Chat with an agent (quick single-shot)."""
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


@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket for real-time chat with streaming."""
    await websocket.accept()
    session_id = str(id(websocket))
    sessions[session_id] = {"connected_at": datetime.now().isoformat()}

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

            # Send acknowledgment
            await websocket.send_json({"type": "status", "content": "🤔 กำลังคิด..."})

            if crew_name and crew_name in crews:
                # Run crew task
                crew = crews[crew_name]
                result = crew.run(message)
                await websocket.send_json({
                    "type": "response",
                    "content": result.final_output,
                    "usage": result.total_usage,
                    "duration": result.duration_seconds,
                    "crew": crew_name,
                })
            else:
                # Single agent chat with streaming
                agent_config = AgentConfig(
                    name=agent_name,
                    role="Conversational Assistant",
                    goal="Help the user",
                    model=model_name,
                )
                agent = Agent(agent_config, tool_registry)
                result = agent.run(message)
                await websocket.send_json({
                    "type": "response",
                    "content": result.output,
                    "usage": result.usage,
                    "agent": agent_name,
                })

    except WebSocketDisconnect:
        sessions.pop(session_id, None)
    except Exception as e:
        await websocket.send_json({"type": "error", "content": str(e)})
        sessions.pop(session_id, None)


@app.get("/api/sessions")
async def list_sessions():
    """List active WebSocket sessions."""
    return {"sessions": sessions}


# --- Auto-load default crews from YAML ---
def load_default_crews():
    """Load crews from config."""
    crew_dir = Path(__file__).parent / "crews"
    if crew_dir.exists():
        for yaml_file in crew_dir.glob("*.yaml"):
            try:
                crew = load_crew_from_yaml(str(yaml_file), tool_registry)
                crews[crew.config.name] = crew
                print(f"  ✅ Loaded crew: {crew.config.name}")
            except Exception as e:
                print(f"  ❌ Failed to load {yaml_file.name}: {e}")


# --- Main ---
if __name__ == "__main__":
    import uvicorn

    server_cfg = config.server_config
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 7860)

    print(f"""
╔══════════════════════════════════════╗
║          🤖 AgenticS Server          ║
║    Multi-Agent AI System v0.1.0     ║
╠══════════════════════════════════════╣
║  Dashboard: http://localhost:{port}    ║
║  API Docs:  http://localhost:{port}/docs ║
╚══════════════════════════════════════╝
    """)

    load_default_crews()
    uvicorn.run(app, host=host, port=port, log_level="info")
