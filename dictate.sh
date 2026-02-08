#!/bin/bash

# Configuration
# Load API key from .env file relative to script location
SCRIPT_DIR="$(dirname "$0")"
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Fallback if not set (User should set in .env)
if [ -z "$GROQ_API_KEY" ]; then
    notify-send "Dictate Error" "GROQ_API_KEY not found in .env"
    exit 1
fi

API_KEY="$GROQ_API_KEY"
LOCK_FILE="/tmp/dictate_recording.pid"
GUI_FILE="/tmp/dictate_gui.pid"
AUDIO_FILE="/tmp/dictate_audio.wav"
DEBUG_LOG="/tmp/dictate_debug.log"

# Function for logging
log() {
    echo "$(date): $1" >> "$DEBUG_LOG"
}

# Dependencies check
if ! command -v wl-copy &> /dev/null; then
    notify-send "Dictate Error" "Please install wl-clipboard: sudo apt install wl-clipboard"
    exit 1
fi

if [ -f "$LOCK_FILE" ]; then
    # --- STOP RECORDING & TRANSCRIBE ---
    
    # 1. Kill the GUI indicator (Orb)
    if [ -f "$GUI_FILE" ]; then
        GUI_PID=$(cat "$GUI_FILE")
        kill "$GUI_PID" 2>/dev/null
        rm "$GUI_FILE"
    fi

    # 2. Kill the recording process nicely (SIGTERM allows arecord to fix WAV header)
    PID=$(cat "$LOCK_FILE")
    if ps -p $PID > /dev/null; then
        kill -TERM $PID
        wait $PID 2>/dev/null
    fi
    rm "$LOCK_FILE"
    
    sleep 0.1
    notify-send -t 2000 "Dictate" "Transcribing..."

    # 3. Send to Groq API (Whisper)
    RESPONSE=$(curl -s -X POST "https://api.groq.com/openai/v1/audio/transcriptions" \
      -H "Authorization: Bearer $API_KEY" \
      -F "file=@$AUDIO_FILE" \
      -F "model=whisper-large-v3-turbo" \
      -F "temperature=0" \
      -F "response_format=json")
    
    # 4. Extract text
    TEXT=$(echo "$RESPONSE" | jq -r '.text')

    # 5. Handle result
    if [ "$TEXT" != "null" ] && [ -n "$TEXT" ]; then
        # Copy to clipboard (Wayland)
        echo -n "$TEXT" | wl-copy
        
        # Notify
        notify-send -t 3000 "Dictate" "Copied to clipboard!"
        log "Success: $TEXT"
    else
        ERROR=$(echo "$RESPONSE" | jq -r '.error.message // "Unknown error"')
        notify-send "Dictate Failed" "$ERROR"
        log "Failed: $ERROR"
    fi

else
    # --- START RECORDING ---
    
    # Record audio
    arecord -D default -f S16_LE -c 1 -r 16000 -d 120 "$AUDIO_FILE" -q &
    echo $! > "$LOCK_FILE"
    
    # Launch Visual Orb
    if [ -f "$SCRIPT_DIR/orb.py" ]; then
        nohup python3 "$SCRIPT_DIR/orb.py" >/dev/null 2>&1 &
        echo $! > "$GUI_FILE"
    fi
    
    log "Started recording"
fi
