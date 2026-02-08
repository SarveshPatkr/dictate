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
    
    # 1. Kill the recording process nicely (SIGTERM allows arecord to fix WAV header)
    PID=$(cat "$LOCK_FILE")
    if ps -p $PID > /dev/null; then
        kill -TERM $PID
        # Wait for process to actually exit so file is flushed
        wait $PID 2>/dev/null
    fi
    rm "$LOCK_FILE"
    
    # Small safety buffer to ensure FS flush
    sleep 0.1
    
    notify-send -t 2000 "Dictate" "Transcribing..."

    # Check if audio file exists and has size
    if [ ! -s "$AUDIO_FILE" ]; then
        notify-send "Dictate Error" "Audio file is empty. Check microphone."
        log "Error: Audio file empty or missing."
        exit 1
    fi

    log "Sending audio to Groq (Size: $(du -h $AUDIO_FILE))"

    # 2. Send to Groq API (Whisper)
    # Note: Groq Whisper accepts m4a/mp3/wav. We send wav directly.
    RESPONSE=$(curl -s -X POST "https://api.groq.com/openai/v1/audio/transcriptions" \
      -H "Authorization: Bearer $API_KEY" \
      -F "file=@$AUDIO_FILE" \
      -F "model=whisper-large-v3-turbo" \
      -F "temperature=0" \
      -F "response_format=json")
    
    log "Response: $RESPONSE"

    # 3. Extract text
    TEXT=$(echo "$RESPONSE" | jq -r '.text')

    # 4. Handle result
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
    
    # Record raw WAV (CD quality is overkill but safe, 16kHz mono is fine for speech)
    # -d 60: Auto-stop after 60s to prevent infinite recording if you forget
    # We use -D default to pick default mic
    arecord -D default -f S16_LE -c 1 -r 16000 -d 120 "$AUDIO_FILE" -q &
    echo $! > "$LOCK_FILE"
    
    notify-send -t 0 "Dictate" "🎙️ Listening... (Press again to stop)"
    log "Started recording to $AUDIO_FILE"
fi
