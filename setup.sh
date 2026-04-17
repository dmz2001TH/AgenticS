#!/bin/bash
# AgenticS v0.2.0 Setup — One-command installation
set -e

echo "
╔══════════════════════════════════════════╗
║         🤖 AgenticS v0.2.0 Setup        ║
║    Multi-Agent AI System                 ║
╠══════════════════════════════════════════╣
║  ✦ Streaming responses                   ║
║  ✦ Memory persistence                    ║
║  ✦ Multi-model (incl. Gemini CLI)        ║
║  ✦ Crew orchestration (4 types)          ║
║  ✦ Scheduled loops                       ║
║  ✦ Sub-agent spawning                    ║
║  ✦ Plugin system                         ║
║  ✦ Trajectory export                     ║
╚══════════════════════════════════════════╝
"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "🐍 Python $PYTHON_VERSION detected"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "✅ Dependencies installed!"
echo ""

# Configure API keys
echo "🔑 Model Configuration"
echo "======================"
echo ""
echo "Which model do you want to configure?"
echo "  1) Google Gemini (free tier available — recommended)"
echo "  2) Gemini CLI (login via Google account)"
echo "  3) OpenAI GPT"
echo "  4) Anthropic Claude"
echo "  5) Ollama (local, no API key)"
echo "  6) Skip — configure later"
echo ""
read -p "Choice [1-6]: " choice

case $choice in
    1)
        read -p "Google API Key (get from https://aistudio.google.com/apikey): " api_key
        if [ -n "$api_key" ]; then
            echo "export GOOGLE_API_KEY='$api_key'" >> .env
            echo "✅ Gemini configured!"
        fi
        ;;
    2)
        echo "⚡ Gemini CLI selected"
        if command -v gemini &> /dev/null; then
            echo "✅ Gemini CLI found at $(which gemini)"
        else
            echo "⚠️  Gemini CLI not found. Install it:"
            echo "   npm install -g @anthropic-ai/gemini-cli"
            echo "   or use: gcloud components install gemini-cli"
            echo ""
            echo "Then login: gemini auth login"
        fi
        echo "export AGENTIC_USE_GEMINI_CLI=true" >> .env
        ;;
    3)
        read -p "OpenAI API Key: " api_key
        if [ -n "$api_key" ]; then
            echo "export OPENAI_API_KEY='$api_key'" >> .env
            echo "✅ OpenAI configured!"
        fi
        ;;
    4)
        read -p "Anthropic API Key: " api_key
        if [ -n "$api_key" ]; then
            echo "export ANTHROPIC_API_KEY='$api_key'" >> .env
            echo "✅ Claude configured!"
        fi
        ;;
    5)
        echo "🟡 Ollama selected"
        echo "   Install: curl -fsSL https://ollama.com/install.sh | sh"
        echo "   Pull:     ollama pull llama3.1"
        ;;
    *)
        echo "⏭️  Skipping — edit config.yaml later"
        ;;
esac

# Create scripts
cat > start.sh << 'LAUNCH'
#!/bin/bash
source .venv/bin/activate
[ -f .env ] && source .env
python server.py
LAUNCH
chmod +x start.sh

cat > chat.sh << 'CHAT'
#!/bin/bash
source .venv/bin/activate
[ -f .env ] && source .env
python cli.py "$@"
CHAT
chmod +x chat.sh

cat > load_env.sh << 'ENV'
#!/bin/bash
[ -f .env ] && { set -a; source .env; set +a; echo "✅ Environment loaded"; }
ENV
chmod +x load_env.sh

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         ✅ Setup Complete!               ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  🖥️  Web Dashboard:                      ║"
echo "║     ./start.sh                           ║"
echo "║     → http://localhost:7860              ║"
echo "║                                          ║"
echo "║  💬 Chat:                                ║"
echo "║     ./chat.sh chat 'hello'               ║"
echo "║     ./chat.sh chatloop                   ║"
echo "║                                          ║"
echo "║  🏃 Run Crew:                            ║"
echo "║     ./chat.sh run 'task' -c research-team║"
echo "║                                          ║"
echo "║  ⏰ Schedule:                            ║"
echo "║     ./chat.sh schedule 'name' 'prompt'   ║"
echo "║     ./chat.sh loops                      ║"
echo "║     ./chat.sh trigger <task-id>          ║"
echo "║                                          ║"
echo "║  📊 Trajectories:                        ║"
echo "║     ./chat.sh trajectories               ║"
echo "║     ./chat.sh export -o training.jsonl   ║"
echo "║                                          ║"
echo "║  🔌 Plugins:                             ║"
echo "║     ./chat.sh plugins                    ║"
echo "║     # Edit plugins/weather/ for example  ║"
echo "║                                          ║"
echo "║  📖 All commands:                        ║"
echo "║     ./chat.sh --help                     ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
