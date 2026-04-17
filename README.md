# AgenticS

**Clone-and-run multi-agent AI system** — สร้างทีม AI agent ของคุณเอง รันได้ทันที

## จุดเด่น

- 🤖 **Multi-Agent Orchestration** — สร้างทีม agent ทำงานร่วมกัน (Sequential, Parallel, Handoff)
- 🧩 **Multi-Model Support** — Gemini, OpenAI, Claude, Ollama, OpenRouter, ฯลฯ
- 🖥️ **Localhost Dashboard** — ควบคุมทีม agent ผ่าน browser
- 🔧 **Tool System** — ต่อ tools เพิ่มได้ modular
- 💬 **Real-time Chat** — WebSocket-based คุยกับ agent แบบ real-time
- 📋 **Task Management** — มอบหมายงาน, ติดตามผล, สรุป

## Quick Start

```bash
git clone https://github.com/dmz2001TH/AgenticS.git
cd AgenticS
bash setup.sh
```

## ตั้งค่า Model

```yaml
# config.yaml
models:
  default: gemini
  providers:
    gemini:
      provider: google
      model: gemini-2.0-flash
      # Login ผ่าน Google ได้เลย หรือใส่ API key
      # api_key: YOUR_GOOGLE_API_KEY
    openai:
      provider: openai
      model: gpt-4o
      # api_key: YOUR_OPENAI_API_KEY
    claude:
      provider: anthropic
      model: claude-sonnet-4-20250514
      # api_key: YOUR_ANTHROPIC_API_KEY
    ollama:
      provider: ollama
      model: llama3.1
      api_base: http://localhost:11434
```

## สร้าง Crew (ทีม Agent)

```yaml
# crews/research-team.yaml
name: research-team
description: ทีมวิจัย - ค้นหา วิเคราะห์ สรุป
agents:
  - name: researcher
    role: Research Specialist
    goal: ค้นหาข้อมูลเชิงลึกจากแหล่งต่างๆ
    model: gemini
    tools: [web_search, file_read]
    
  - name: analyst
    role: Data Analyst
    goal: วิเคราะห์ข้อมูลและสร้าง insight
    model: gemini
    tools: [code_execute, file_write]
    
  - name: writer
    role: Technical Writer
    goal: เขียนรายงานสรุปจากผลวิเคราะห์
    model: gemini
    tools: [file_write]

process: sequential  # sequential | parallel | handoff
```

## ใช้งาน

```bash
# รัน server + dashboard
python server.py

# หรือ CLI mode
python cli.py

# ส่งงานให้ crew
python -m agents.crew run research-team "วิเคราะห์แนวโน้ม AI Agent ในปี 2026"
```

## Dashboard

เปิด browser ไปที่ `http://localhost:7860`

- เลือก crew / agent
- ส่ง task
- ดู progress แบบ real-time
- ดู history
- จัดการ tools

## Architecture

```
┌─────────────────────────────────────┐
│          Dashboard (Browser)        │
│    React + WebSocket + Chat UI      │
└──────────────┬──────────────────────┘
               │ HTTP/WebSocket
┌──────────────▼──────────────────────┐
│         FastAPI Server              │
│    Routes + WS + Task Queue         │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       Orchestration Layer           │
│  Crew / Swarm / Handoff / Graph     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Agent Layer                 │
│  Role + Goal + Memory + Tools       │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Model Layer                 │
│  LiteLLM → Gemini/OpenAI/Claude/... │
└─────────────────────────────────────┘
```

## Supported Models

| Provider | ตัวอย่าง Models |
|----------|----------------|
| Google   | gemini-2.0-flash, gemini-2.0-pro, gemini-2.5-pro |
| OpenAI   | gpt-4o, gpt-4o-mini, o1, o3-mini |
| Anthropic| claude-sonnet-4-20250514, claude-opus-4-20250514 |
| Ollama   | llama3.1, codellama, mistral (local) |
| OpenRouter | 200+ models |

## License

MIT
