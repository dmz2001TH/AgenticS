# AgenticS

**Clone-and-run multi-agent AI system** — สร้างทีม AI agent ของคุณเอง รันได้ทันที

## 🚀 Quick Start

```bash
git clone https://github.com/dmz2001TH/AgenticS.git
cd AgenticS
bash setup.sh      # ติดตั้ง + ตั้งค่า model
./start.sh         # เปิด dashboard
```

## ✦ Features

### 🤖 Multi-Agent Orchestration
- **Sequential** — agents ทำงานตามลำดับ, ส่ง output ต่อให้ agent ถัดไป
- **Parallel** — agents ทำงานพร้อมกัน, รวมผลลัพธ์
- **Handoff** — agent แรกตัดสินใจ routing, ส่งงานให้ agent ที่เหมาะสม (conditional routing)
- **Swarm** — agents โหวต/consensus แล้วสรุปผลรวม

### 🧩 Multi-Model Support
| Provider | ตัวอย่าง Models |
|----------|----------------|
| Google   | gemini-2.0-flash, gemini-2.0-pro |
| Gemini CLI | ใช้ `gemini` command (login ผ่าน Google) |
| OpenAI   | gpt-4o, gpt-4o-mini, o1 |
| Anthropic| claude-sonnet-4, claude-opus-4 |
| Ollama   | llama3.1, codellama (local) |
| OpenRouter | 200+ models |

### 💬 Streaming Responses
- Real-time token streaming via WebSocket
- เห็นคำตอบทีละคำ ไม่ต้องรอจนเสร็จ

### 🧠 Memory Persistence
- บันทึก conversation history ข้าม session
- Agent เรียนรู้จาก task ที่ทำสำเร็จ (skill auto-creation)
- User profile — จำความชอบและหัวข้อที่สนใจ
- Keyword search ข้ามทุก session

### ⏰ Scheduled Loops
- Manual trigger — กดปุ่มเมื่อต้องการ
- Interval — ทำงานทุก N วินาที
- Cron-style — daily, weekly schedule
- ผูกกับ crew ได้ — ให้ทีม agent ทำงานอัตโนมัติ

### 🏃 Sub-Agent Spawning
- Agent สามารถ spawn sub-agent สำหรับงานย่อย
- ทำงาน independent, ไม่กิน memory หลัก
- Multi-model — sub-agent ใช้ model ต่างจาก parent ได้

### 🔌 Plugin System
- สร้าง tool plugin ใหม่ได้ modular
- Dynamic loading — ไม่ต้อง restart server
- ตัวอย่าง: weather plugin (เช็คสภาพอากาศ)

### 📊 Trajectory Export
- บันทึก reasoning chain ของทุก task
- Export เป็น training data (JSONL format)
- เหมาะสำหรับ fine-tune model ต่อ

### 🖥️ Dashboard
- Interactive chat with streaming
- Crew management (create, run, delete)
- Scheduled task management
- Memory browser
- Trajectory viewer
- Plugin manager
- Real-time stats

## 📖 Usage

### Web Dashboard
```bash
./start.sh
# เปิด http://localhost:7860
```

### CLI
```bash
# คุยกับ agent
./chat.sh chat "วิเคราะห์ข่าว AI ล่าสุด"
./chat.sh chat "hello" -m gemini-cli    # ใช้ Gemini CLI

# Interactive chat
./chat.sh chatloop

# รัน crew
./chat.sh run "วิเคราะห์แนวโน้ม AI" -c research-team
./chat.sh run "task" -f crews/custom.yaml

# Schedule
./chat.sh schedule "daily-report" "สรุปข่าว AI วันนี้" -c research-team -t cron -v "daily 09:00"
./chat.sh loops
./chat.sh trigger <task-id>

# Memory
./chat.sh memory
./chat.sh search "AI agent"

# Trajectories
./chat.sh trajectories
./chat.sh export -o training.jsonl

# Plugins
./chat.sh plugins
./chat.sh status
```

### API
```bash
# REST API docs
open http://localhost:7860/docs

# WebSocket
wscat -c ws://localhost:7860/ws
```

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│       Dashboard + WebSocket         │
│    (Browser — Streaming Chat UI)    │
└──────────────┬──────────────────────┘
               │ HTTP / WebSocket
┌──────────────▼──────────────────────┐
│         FastAPI Server              │
│  Routes + WS + Scheduler + Plugins  │
└──────┬──────┬──────┬──────┬─────────┘
       │      │      │      │
┌──────▼─┐ ┌─▼────┐ │ ┌────▼─────┐
│ Memory │ │Sched.│ │ │Trajectory│
│ Store  │ │      │ │ │ Store    │
└────────┘ └──────┘ │ └──────────┘
                    │
┌───────────────────▼─────────────────┐
│       Orchestration Layer           │
│  Sequential / Parallel / Handoff    │
│  / Swarm / Sub-Agent Spawning      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Agent Layer                 │
│  Role + Goal + Memory + Tools       │
│  + ReAct Loop + Streaming           │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Model Layer (LiteLLM)       │
│  Gemini / Gemini CLI / OpenAI /     │
│  Claude / Ollama / OpenRouter       │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       Tools + Plugins               │
│  file / shell / web / python /      │
│  weather / spawn_agent / custom     │
└─────────────────────────────────────┘
```

## 🧩 Built-in Tools
- `file_read` — อ่านไฟล์
- `file_write` — เขียนไฟล์
- `shell` — รัน shell command
- `web_search` — ค้นหาเว็บ
- `python_execute` — รัน Python code
- `list_files` — ดูไฟล์ใน directory
- `spawn_agent` — สร้าง sub-agent
- `get_weather` — เช็คสภาพอากาศ (plugin)

## 📋 Default Crews
- **research-team** — นักวิจัย → นักวิเคราะห์ → นักเขียน (sequential)
- **dev-team** — Tech Lead → Architect → Developer → Tester (handoff)
- **content-team** — Creative → Editor → SEO (swarm)

## 🔧 Configuration

`config.yaml`:
```yaml
models:
  default: gemini
  providers:
    gemini:
      provider: google
      model: gemini-2.0-flash
      api_key: null  # หรือ set GOOGLE_API_KEY env var
    gemini-cli:
      provider: gemini-cli
      model: gemini
    openai:
      provider: openai
      model: gpt-4o-mini
    # ...
server:
  host: 0.0.0.0
  port: 7860
```

## License

MIT
