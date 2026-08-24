#!/bin/bash
# AI Chat - Dictate + AI query tool with orb-like theme
SCRIPT_DIR="$(dirname "$0")"
[ -f "$SCRIPT_DIR/.env" ] && export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)

if [ -z "$GROQ_API_KEY" ]; then
    notify-send "AI Chat Error" "GROQ_API_KEY not found in .env"
    exit 1
fi

exec python3 "$SCRIPT_DIR/ai_chat.py"
