# AgenticS — Handoff Document
## สำหรับ Agent คนถัดไป หรือ ผู้สานต่อ

---

## 📋 สถานะปัจจุบัน

**Repo:** https://github.com/dmz2001TH/AgenticS
**Version:** 0.2.0
**Branch:** main
**สถานะ:** โค้ดเสร็จสมบูรณ์ทุก feature แต่ **ยังไม่ได้เทสกับ LLM จริง** (ขาด API key)

---

## 🏗️ Architecture Overview

```
AgenticS/
├── __init__.py              # Version metadata
├── config.py                # Config manager (YAML + env vars)
├── config.yaml              # Default config (models, server)
├── models.py                # Model layer (LiteLLM + Gemini CLI)
├── server.py                # FastAPI server + WebSocket + all API routes
├── cli.py                   # CLI (click-based)
├── requirements.txt         # Dependencies
├── setup.sh                 # One-command setup script
├── start.sh                 # (generated) Launch server
├── chat.sh                  # (generated) CLI shortcut
├── .gitignore
│
├── agents/
│   └── __init__.py          # Agent class, AgentConfig, AgentBuilder
│                            # - ReAct tool-calling loop
│                            # - Memory loading from past tasks
│                            # - Sub-agent spawning
│                            # - Streaming support
│                            # - Trajectory tracking
│
├── orchestration/
│   └── __init__.py          # Crew class, CrewConfig, ProcessType
│                            # - Sequential: agents run in order
│                            # - Parallel: agents run concurrently
│                            # - Handoff: router agent + conditional routing
│                            # - Swarm: consensus/voting pattern
│                            # - YAML crew loader
│
├── tools/
│   └── __init__.py          # ToolRegistry + built-in tools
│                            # Tools: file_read, file_write, shell,
│                            # web_search, list_files, python_execute,
│                            # spawn_agent
│
├── memory/
│   └── __init__.py          # MemoryStore
│                            # - Conversation persistence (JSONL files)
│                            # - User profiles
│                            # - Agent learned patterns
│                            # - Keyword search across sessions
│
├── scheduler/
│   └── __init__.py          # Scheduler
│                            # - Manual / Interval / Cron tasks
│                            # - Trigger, pause, resume
│                            # - File persistence
│
├── plugins/
│   ├── __init__.py          # PluginManager
│   │                        # - Discover/load plugins from plugins/ dir
│   │                        # - Dynamic tool registration
│   │                        # - Plugin template creation
│   └── weather/
│       ├── plugin.json      # Plugin metadata
│       └── __init__.py      # get_weather tool (wttr.in)
│
├── trajectories/
│   └── __init__.py          # TrajectoryStore
│                            # - Track reasoning chains
│                            # - Export to JSONL training format
│
├── dashboard/
│   └── static/
│       └── index.html       # Full dashboard (7 tabs)
│                            # Chat (streaming), History, Crews,
│                            # Schedule, Memory, Trajectories, Plugins
│
├── crews/
│   ├── research-team.yaml   # researcher → analyst → writer (sequential)
│   ├── dev-team.yaml        # tech-lead → architect → developer → tester (handoff)
│   └── content-team.yaml    # creative + editor + seo-expert (swarm)
│
├── memory_store/            # (generated) Persistent memory data
├── trajectory_store/        # (generated) Saved trajectories
└── plugins/                 # Plugin directory (auto-loaded)
```

---

## 🔧 สิ่งที่ทำเสร็จแล้ว

### v0.1.0 (commit f11f1d1)
- [x] Config system (YAML + env override)
- [x] Model layer (LiteLLM: Gemini, OpenAI, Claude, Ollama, OpenRouter)
- [x] Agent class with ReAct loop
- [x] Tool registry + 6 built-in tools
- [x] Crew orchestration (sequential, parallel, handoff)
- [x] FastAPI server + REST API
- [x] Dashboard UI (basic)
- [x] CLI interface
- [x] 2 default crew templates (research-team, dev-team)
- [x] Setup script

### v0.2.0 (commit 60baa08)
- [x] Streaming responses (WebSocket token-by-token)
- [x] Memory persistence (conversations, user profiles, agent learning)
- [x] Gemini CLI integration (provider="gemini-cli")
- [x] Conditional handoff routing (follow-up detection)
- [x] Scheduled loops (manual, interval, cron)
- [x] Sub-agent spawning (spawn_agent tool + Agent.spawn_sub_agent)
- [x] Plugin system (dynamic load + weather example)
- [x] Multi-model per agent support
- [x] Swarm orchestration (consensus pattern)
- [x] Trajectory export (RL training format)
- [x] Dashboard v2 (7 tabs + streaming)
- [x] content-team.yaml (swarm crew)

---

## ⚠️ สิ่งที่ยังไม่ได้เทส

### ❌ ไม่มี API key = ไม่ได้เทส
1. **Agent LLM calls** — ยังไม่เคยเห็น agent เรียก model จริง
2. **Tool calling loop** — ReAct loop กับ LLM จริง
3. **Crew execution** — ไม่รู้ sequential/parallel/handoff/swarm ทำงานจริงยังไง
4. **Streaming** — WebSocket streaming กับ LLM
5. **Gemini CLI** — ยังไม่ได้ install `gemini` CLI

### ✅ เทสแล้ว (ไม่ต้อง API key)
- Module imports ทั้งหมด
- Tool execution (file, python, shell)
- Memory save/load/search
- Scheduler create/trigger
- Plugin discovery + loading
- Trajectory tracking + export
- API endpoints (all 14+)
- Crew YAML loading (3 crews)
- AgentBuilder pattern

---

## 🚀 สิ่งที่ต้องทำต่อ (Priority)

### 🔴 P0 — Critical (ต้องทำก่อนใช้จริง)
1. **Set API key แล้วเทส agent จริง**
   ```bash
   export GOOGLE_API_KEY="AIza..."
   cd AgenticS
   python3 cli.py chat "สวัสดี ช่วยอธิบายตัวเองหน่อย"
   ```

2. **เทส crew execution**
   ```bash
   python3 cli.py run "ค้นหาข่าว AI ล่าสุดแล้วสรุป" -c research-team
   ```

3. **Fix bugs ที่เจอตอนเทสจริง**
   - คาดว่าจะเจอ edge cases ใน tool calling loop
   - อาจต้องปรับ system prompts
   - อาจต้องแก้ streaming flow

### 🟡 P1 — Important (ทำต่อได้เลย)
4. **เพิ่ม error handling ที่ดีกว่านี้**
   - Rate limiting awareness (429 errors)
   - Timeout handling สำหรับ long tasks
   - Retry logic สำหรับ API failures
   - Graceful degradation เมื่อ model ไม่ available

5. **เพิ่ม tools ที่มีประโยชน์**
   - `web_fetch` — อ่านหน้าเว็บ (URL → text)
   - `database_query` — query SQL/NoSQL
   - `image_analyze` — วิเคราะห์รูป (multimodal)
   - `email_send` — ส่งอีเมล
   - `github_operations` — PR, Issue, etc.

6. **Improve memory system**
   - Semantic search (ใช้ embedding แทน keyword)
   - Auto-summarize old conversations
   - Importance scoring สำหรับ memories

7. **Dashboard improvements**
   - Real-time agent execution visualization
   - Token usage graphs
   - Cost tracking
   - Dark/light theme toggle

### 🟢 P2 — Nice to Have
8. **Authentication** — API key auth สำหรับ server
9. **Multi-user support** — separate memory per user
10. **Voice input/output** — TTS/STT integration
11. **Mobile responsive** dashboard
12. **Docker packaging** — `docker-compose up`
13. **More crew templates** — data-pipeline, code-review, translation

---

## 🐛 Known Issues

1. **PluginManager path** — plugins_dir ควร指向 project root ไม่ใช่ module dir
   - แก้แล้วใน v0.2.0 แต่ยังไม่ได้เทสใน environment อื่น

2. **Gemini CLI provider** — ยังไม่ได้ install gemini CLI จริง
   - ต้อง `npm install -g @anthropic-ai/gemini-cli` หรือ gcloud SDK

3. **Scheduler state** — ไม่ persist อัตโนมัติ
   - ต้องเรียก `save_to_file()` ด้วยตัวเอง

4. **WebSocket reconnect** — อาจ reconnect หลายครั้ง
   - ควรเพิ่ม backoff logic

5. **`import os` 位置** — trajectories/__init__.py มี `import os` อยู่ผิดที่ (หลัง function)
   - ย้ายขึ้นมาด้านบนได้

---

## 📝 วิธีเทส (สำหรับ agent คนถัดไป)

### Step 1: Clone & Setup
```bash
cd /root/.openclaw/workspace
git clone https://github.com/dmz2001TH/AgenticS.git
cd AgenticS
pip install --break-system-packages litellm fastapi uvicorn pyyaml rich click aiofiles httpx jinja2 python-multipart websockets
```

### Step 2: Set API Key
```bash
export GOOGLE_API_KEY="your-key-here"  # ฟรีที่ aistudio.google.com/apikey
```

### Step 3: Test Agent Chat
```bash
python3 cli.py chat "อธิบายตัวเองหน่อย" -v
python3 cli.py chat "เขียน Python hello world" -v
python3 cli.py chatloop  # Interactive mode
```

### Step 4: Test Crew
```bash
python3 cli.py run "ค้นหาข่าว AI Agent ล่าสุด" -c research-team -v
python3 cli.py run "ออกแบบ REST API สำหรับ todo app" -c dev-team -v
python3 cli.py run "เขียนบทความเกี่ยวกับ Agentic AI" -c content-team -v
```

### Step 5: Test Server
```bash
python3 server.py &
# แล้วเทส API:
curl http://localhost:7860/api/health
curl -X POST http://localhost:7860/api/chat -H "Content-Type: application/json" -d '{"message":"hello"}'
```

### Step 6: Test Streaming
```bash
# WebSocket test (ใช้ wscat หรือ browser)
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:7860/ws') as ws:
        await ws.send(json.dumps({'message': 'hello', 'stream': True}))
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print(data.get('type'), ':', data.get('content', '')[:50])
            if data.get('type') == 'stream_end':
                break
asyncio.run(test())
"
```

### Step 7: Test Schedule
```bash
python3 cli.py schedule "test-loop" "Say hello" -t manual
python3 cli.py loops
python3 cli.py trigger <task-id>
```

### Step 8: Test Trajectories
```bash
python3 cli.py trajectories
python3 cli.py export -o training.jsonl
cat training.jsonl | python3 -m json.tool | head
```

### Step 9: Test Plugin
```bash
python3 cli.py plugins
# Weather plugin should show as loaded
# Test: python3 -c "from tools import get_tool_registry; r = get_tool_registry(); print(r.execute('get_weather', location='Bangkok'))"
```

---

## 🔑 Config ที่สำคัญ

### config.yaml
```yaml
models:
  default: gemini          # Model ที่ใช้โดย default
  providers:
    gemini:                # Google Gemini API
      provider: google
      model: gemini-2.0-flash
      api_key: null        # หรือ set GOOGLE_API_KEY env
    gemini-cli:            # Gemini CLI (login ผ่าน Google)
      provider: gemini-cli
      model: gemini
    openai:                # OpenAI
      provider: openai
      model: gpt-4o-mini
      api_key: null
    claude:                # Anthropic
      provider: anthropic
      model: claude-sonnet-4-20250514
      api_key: null
    ollama:                # Local Ollama
      provider: ollama
      model: llama3.1
      api_base: http://localhost:11434

server:
  host: 0.0.0.0
  port: 7860
  debug: true
```

---

## 📊 Git History

```
60baa08 (HEAD -> main) v0.2.0 — Full agentic feature set
42525bb fix: graceful litellm import for verification
f11f1d1 Initial commit: AgenticS v0.1.0
```

---

## 👤 เจ้าของโปรเจค

- **GitHub:** dmz2001TH
- **ความต้องการ:** Clone-and-run multi-agent AI system
- **Model ที่สนใจ:** Gemini (login ผ่าน Google)
- **ภาษา:** ไทย (Thai)

---

## 💡 Notes สำหรับ Agent คนถัดไป

1. **อย่าแก้ core architecture** — 除非 มี bug จริง ๆ โครงสร้างออกแบบมาดีแล้ว
2. **Focus ที่ P0** — เทสกับ LLM จริงก่อน แล้ว fix bugs
3. **Commit ทุกครั้ง** — `git add -A && git commit -m "fix: ..."`
4. **Push ด้วย** — `git remote set-url origin https://dmz2001TH:$(gh auth token)@github.com/dmz2001TH/AgenticS.git && git push && git remote set-url origin https://github.com/dmz2001TH/AgenticS.git`
5. **อัพเดท handoff doc นี้** — เมื่อทำอะไรเสร็จแล้ว
6. **ผู้ใช้ชื่อพิชัย** — คุยกับเขาเป็นภาษาไทย

---

*Handoff document created: 2026-04-17 20:57 GMT+8*
*Created by: AgenticS Agent on OpenClaw*
