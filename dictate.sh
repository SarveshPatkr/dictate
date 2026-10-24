#!/bin/bash
# Dictate Pro - Groq Cloud Whisper Dictation
# Control: Super+T to Start, Space or Confirm [✓] to Stop.

# 1. Environment & Configuration
SCRIPT_DIR="$(dirname "$0")"
[ -f "$SCRIPT_DIR/.env" ] && export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
HISTORY_DIR="$SCRIPT_DIR/history"
mkdir -p "$HISTORY_DIR"

# Constants
LOCK_FILE="/tmp/dictate_recording.pid"
GUI_FILE="/tmp/dictate_gui.pid"
LISTENER_FILE="/tmp/dictate_listener.pid"
AUDIO_FILE="/tmp/dictate_audio.wav"
DEBUG_LOG="/tmp/dictate_debug.log"
ERR_LOG="/tmp/dictate_groq_err.log"

# Helper for logging
log() { echo "$(date): $1" >> "$DEBUG_LOG"; }

# 2. Dependency & Key Check
for cmd in pw-record wl-copy python3; do
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
    # --- ACTION: STOP & TRANSCRIBE (GROQ CLOUD WHISPER) ---
    
    # Trigger loading state in UI
    if [ -f "$GUI_FILE" ]; then
        GUI_PID=$(cat "$GUI_FILE")
        kill -USR1 "$GUI_PID" 2>/dev/null
    fi

    # Stop recording
    REC_PID=$(cat "$LOCK_FILE")
    kill -TERM "$REC_PID" 2>/dev/null
    wait "$REC_PID" 2>/dev/null
    sync
    rm -f "$LOCK_FILE"
    
    # Stop Space Listener
    if [ -f "$LISTENER_FILE" ]; then
        L_PID=$(cat "$LISTENER_FILE")
        kill "$L_PID" 2>/dev/null
        rm -f "$LISTENER_FILE"
    fi

    # Send whole audio to Groq Whisper at end (auto-compresses/chunks if exceeding API limits)
    log "Groq Whisper transcription started."
    rm -f "$ERR_LOG"
    TEXT=$(python3 "$SCRIPT_DIR/groq_transcribe.py" "$AUDIO_FILE" 2> "$ERR_LOG")

    # Shutdown UI
    [ -f "$GUI_FILE" ] && kill -TERM "$(cat "$GUI_FILE")" 2>/dev/null && rm -f "$GUI_FILE"

    if [ -n "$TEXT" ]; then
        # Copy to system clipboard
        echo -n "$TEXT" | wl-copy
        
        # Save to history archive
        TIMESTAMP=$(date +'%Y-%m-%d_%H-%M-%S')
        echo "$TEXT" > "$HISTORY_DIR/latest.txt"
        echo "$TEXT" > "$HISTORY_DIR/${TIMESTAMP}.txt"
        
        notify-send -t 2500 "Dictate Complete" "Copied to clipboard!"
        log "Success: Groq transcription complete ($TEXT)."
    else
        if [ -s "$ERR_LOG" ]; then
            ERR_MSG=$(cat "$ERR_LOG" | head -n 1)
            log "Groq transcription failed: $ERR_MSG"
            notify-send -u critical "Dictate Error" "$ERR_MSG"
        else
            log "Notice: No speech detected in audio."
            notify-send -t 2000 "Dictate" "No speech detected."
        fi
    fi
    rm -f "$ERR_LOG"

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
