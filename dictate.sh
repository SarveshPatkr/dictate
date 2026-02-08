#!/bin/bash

# Configuration
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
LISTENER_FILE="/tmp/dictate_listener.pid"
AUDIO_FILE="/tmp/dictate_audio.wav"
DEBUG_LOG="/tmp/dictate_debug.log"

log() { echo "$(date): $1" >> "$DEBUG_LOG"; }

if [ -f "$LOCK_FILE" ]; then
    # --- STOP & TRANSCRIBE ---
    
    # 1. Switch Orb to LOADING state (Blue bar)
    if [ -f "$GUI_FILE" ]; then
        GUI_PID=$(cat "$GUI_FILE")
        kill -USR1 "$GUI_PID" 2>/dev/null
    fi

    # 2. Stop recording cleanly
    PID=$(cat "$LOCK_FILE")
    kill -TERM $PID 2>/dev/null
    wait $PID 2>/dev/null
    rm "$LOCK_FILE"
    
    # 2b. Stop Space Listener
    if [ -f "$LISTENER_FILE" ]; then
        L_PID=$(cat "$LISTENER_FILE")
        kill "$L_PID" 2>/dev/null
        rm "$LISTENER_FILE"
    fi

    # 3. Transcribe (No notification anymore!)
    RESPONSE=$(curl -s -X POST "https://api.groq.com/openai/v1/audio/transcriptions" \
      -H "Authorization: Bearer $API_KEY" \
      -F "file=@$AUDIO_FILE" \
      -F "model=whisper-large-v3-turbo" \
      -F "temperature=0" \
      -F "response_format=json")

    TEXT=$(echo "$RESPONSE" | jq -r '.text')

    # 4. Cleanup UI (Kill Orb now)
    if [ -f "$GUI_FILE" ]; then
        kill $(cat "$GUI_FILE") 2>/dev/null
        rm "$GUI_FILE"
    fi

    if [ "$TEXT" != "null" ] && [ -n "$TEXT" ]; then
        echo -n "$TEXT" | wl-copy
        notify-send -t 2000 "Dictate" "Copied to clipboard!"
        log "Success: $TEXT"
    else
        notify-send "Dictate Failed" "Check logs"
    fi

else
    # --- START RECORDING ---
    arecord -D default -f S16_LE -c 1 -r 16000 -d 120 "$AUDIO_FILE" -q &
    echo $! > "$LOCK_FILE"
    
    nohup python3 "$SCRIPT_DIR/orb.py" >/dev/null 2>&1 &
    echo $! > "$GUI_FILE"
    
    # Start Space Listener
    if [ -f "$SCRIPT_DIR/space_listener.py" ]; then
        nohup python3 "$SCRIPT_DIR/space_listener.py" >/dev/null 2>&1 &
        echo $! > "$LISTENER_FILE"
    fi
    
    log "Recording started"
fi
