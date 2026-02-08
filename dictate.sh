#!/bin/bash

# Configuration
# Load API key from .env file
SCRIPT_DIR="$(dirname "$0")"
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

if [ -z "$GROQ_API_KEY" ]; then
    notify-send "Dictate Error" "GROQ_API_KEY not found in .env"
    exit 1
fi

API_KEY="$GROQ_API_KEY"
LOCK_FILE="/tmp/dictate_recording.pid"
GUI_FILE="/tmp/dictate_gui.pid"
AUDIO_FILE="/tmp/dictate_audio.wav"
DEBUG_LOG="/tmp/dictate_debug.log"

log() { echo "$(date): $1" >> "$DEBUG_LOG"; }

if [ -f "$LOCK_FILE" ]; then
    # --- STOP & TRANSCRIBE ---
    
    # 1. Close the Orb
    if [ -f "$GUI_FILE" ]; then
        kill $(cat "$GUI_FILE") 2>/dev/null
        rm "$GUI_FILE"
    fi

    # 2. Stop recording cleanly
    PID=$(cat "$LOCK_FILE")
    kill -TERM $PID 2>/dev/null
    wait $PID 2>/dev/null
    rm "$LOCK_FILE"
    
    # 3. Focus Recovery Delay (CRITICAL)
    # Give Ubuntu a moment to refocus your text editor after the Orb closes
    sleep 0.3
    
    notify-send -t 2000 "Dictate" "Transcribing..."

    # 4. API Call
    RESPONSE=$(curl -s -X POST "https://api.groq.com/openai/v1/audio/transcriptions" \
      -H "Authorization: Bearer $API_KEY" \
      -F "file=@$AUDIO_FILE" \
      -F "model=whisper-large-v3-turbo" \
      -F "temperature=0" \
      -F "response_format=json")

    TEXT=$(echo "$RESPONSE" | jq -r '.text')

    if [ "$TEXT" != "null" ] && [ -n "$TEXT" ]; then
        # 5. Copy to Clipboard
        echo -n "$TEXT" | wl-copy
        sleep 0.2 # Wait for clipboard to settle
        
        # 6. AUTO-PASTE
        # Use our improved Python tool
        log "Triggering paste tool..."
        python3 "$SCRIPT_DIR/paste_direct.py" >> "$DEBUG_LOG" 2>&1 &
        
        notify-send -t 1500 "Dictate" "Pasted!"
    else
        notify-send "Dictate Failed" "Check logs"
    fi

else
    # --- START RECORDING ---
    arecord -D default -f S16_LE -c 1 -r 16000 -d 120 "$AUDIO_FILE" -q &
    echo $! > "$LOCK_FILE"
    
    nohup python3 "$SCRIPT_DIR/orb.py" >/dev/null 2>&1 &
    echo $! > "$GUI_FILE"
    
    log "Recording started"
fi
