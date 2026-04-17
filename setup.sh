#!/bin/bash
# AgenticS Setup — One-command installation
set -e

echo "
╔══════════════════════════════════════╗
║       🤖 AgenticS Setup             ║
║   Multi-Agent AI System v0.1.0      ║
╚══════════════════════════════════════╝
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
echo "Select which model to configure (or press Enter to skip):"
echo "  1) Google Gemini (recommended — free tier available)"
echo "  2) OpenAI GPT"
echo "  3) Anthropic Claude"
echo "  4) Ollama (local, no API key needed)"
echo "  5) Skip — configure later in config.yaml"
echo ""
read -p "Choice [1-5]: " choice

case $choice in
    1)
        read -p "Google API Key (get from https://aistudio.google.com/apikey): " api_key
        if [ -n "$api_key" ]; then
            echo "export GOOGLE_API_KEY='$api_key'" >> .env
            echo "✅ Gemini configured!"
        fi
        ;;
    2)
        read -p "OpenAI API Key: " api_key
        if [ -n "$api_key" ]; then
            echo "export OPENAI_API_KEY='$api_key'" >> .env
            echo "✅ OpenAI configured!"
        fi
        ;;
    3)
        read -p "Anthropic API Key: " api_key
        if [ -n "$api_key" ]; then
            echo "export ANTHROPIC_API_KEY='$api_key'" >> .env
            echo "✅ Claude configured!"
        fi
        ;;
    4)
        echo "🟡 Ollama selected — make sure ollama is running at http://localhost:11434"
        echo "   Install: curl -fsSL https://ollama.com/install.sh | sh"
        echo "   Pull model: ollama pull llama3.1"
        ;;
    *)
        echo "⏭️  Skipping — edit config.yaml to configure later"
        ;;
esac

# Create .env loader script
cat > load_env.sh << 'EOF'
#!/bin/bash
# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "✅ Environment loaded"
else
    echo "⚠️  No .env file found"
fi
EOF
chmod +x load_env.sh

# Create launch scripts
cat > start.sh << 'EOF'
#!/bin/bash
source .venv/bin/activate
[ -f .env ] && source .env
python server.py
EOF
chmod +x start.sh

cat > chat.sh << 'EOF'
#!/bin/bash
source .venv/bin/activate
[ -f .env ] && source .env
python cli.py chat "$@"
EOF
chmod +x chat.sh

echo ""
echo "╔══════════════════════════════════════╗"
echo "║      ✅ Setup Complete!              ║"
echo "╠══════════════════════════════════════╣"
echo "║  Start server:  ./start.sh          ║"
echo "║  CLI chat:      ./chat.sh \"hello\"   ║"
echo "║  Dashboard:     localhost:7860      ║"
echo "╚══════════════════════════════════════╝"
echo ""
