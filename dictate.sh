#!/bin/bash
# Dictate Pro
# A system-wide dictation tool for Ubuntu (Wayland).
# Control: Super+T to Start, Space to Stop.

# 1. Environment & Configuration
SCRIPT_DIR="$(dirname "$0")"
[ -f "$SCRIPT_DIR/.env" ] && export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)

# Constants
LOCK_FILE="/tmp/dictate_recording.pid"
GUI_FILE="/tmp/dictate_gui.pid"
LISTENER_FILE="/tmp/dictate_listener.pid"
AUDIO_FILE="/tmp/dictate_audio.wav"
DEBUG_LOG="/tmp/dictate_debug.log"

# Helper for logging
log() { echo "$(date): $1" >> "$DEBUG_LOG"; }

# 2. Dependency Check
for cmd in pw-record wl-copy curl jq python3; do
    if ! command -v $cmd &> /dev/null; then
        notify-send "Dictate Error" "Missing dependency: $cmd"
        exit 1
    fi
done

if [ -z "$GROQ_API_KEY" ]; then
    notify-send "Dictate Error" "GROQ_API_KEY not found in .env"
    exit 1
fi

# 3. Main Toggle Logic
if [ "$1" == "--cancel" ]; then
    log "Session cancelled by user."
    [ -f "$LOCK_FILE" ] && kill -TERM "$(cat "$LOCK_FILE")" 2>/dev/null && rm -f "$LOCK_FILE"
    [ -f "$LISTENER_FILE" ] && kill "$(cat "$LISTENER_FILE")" 2>/dev/null && rm -f "$LISTENER_FILE"
    [ -f "$GUI_FILE" ] && kill -TERM "$(cat "$GUI_FILE")" 2>/dev/null && rm -f "$GUI_FILE"
    rm -f "$AUDIO_FILE"
    exit 0
fi

if [ -f "$LOCK_FILE" ]; then
    # --- ACTION: STOP & TRANSCRIBE ---
    
    # Trigger loading state in UI
    if [ -f "$GUI_FILE" ]; then
        GUI_PID=$(cat "$GUI_FILE")
        kill -USR1 "$GUI_PID" 2>/dev/null
    fi

    # Stop recording
    REC_PID=$(cat "$LOCK_FILE")
    kill -TERM "$REC_PID" 2>/dev/null
    wait "$REC_PID" 2>/dev/null
    rm "$LOCK_FILE"
    
    # Stop Space Listener
    if [ -f "$LISTENER_FILE" ]; then
        L_PID=$(cat "$LISTENER_FILE")
        kill "$L_PID" 2>/dev/null
        rm "$LISTENER_FILE"
    fi

    # API Call to Groq Whisper
    log "Transcription started."
    RESPONSE=$(curl -s -X POST "https://api.groq.com/openai/v1/audio/transcriptions" \
      -H "Authorization: Bearer $GROQ_API_KEY" \
      -F "file=@$AUDIO_FILE" \
      -F "model=whisper-large-v3-turbo" \
      -F "temperature=0" \
      -F "response_format=json")

    TEXT=$(echo "$RESPONSE" | jq -r '.text')

    # Shutdown UI
    [ -f "$GUI_FILE" ] && kill -TERM "$(cat "$GUI_FILE")" 2>/dev/null && rm "$GUI_FILE"

    if [ "$TEXT" != "null" ] && [ -n "$TEXT" ]; then
        echo -n "$TEXT" | wl-copy
        notify-send -t 2000 "Dictate" "Copied to clipboard!"
        log "Success: Transcription complete."
    else
        log "Error: $RESPONSE"
        notify-send "Dictate Failed" "Check /tmp/dictate_debug.log"
    fi

else
    # --- ACTION: START RECORDING ---
    log "Session started."
    
    # Start PipeWire recording
    pw-record --format=s16 --rate=16000 --channels=1 "$AUDIO_FILE" >/dev/null 2>&1 &
    echo $! > "$LOCK_FILE"
    
    # Start Orb UI
    nohup python3 "$SCRIPT_DIR/orb.py" >> "$DEBUG_LOG" 2>&1 &
    echo $! > "$GUI_FILE"
    
    # Start Space Listener
    nohup python3 "$SCRIPT_DIR/space_listener.py" >> "$DEBUG_LOG" 2>&1 &
    echo $! > "$LISTENER_FILE"
fi
