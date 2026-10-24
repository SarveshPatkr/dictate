# AGENTS.md - Developer & Agent Guide for Dictate Pro

This document provides operational context, architectural breakdown, and development guidelines for AI agents working in this repository.

---

## 1. Project Overview & Philosophy

**Dictate Pro** is a lightweight, system-wide speech-to-text (STT) utility designed for Linux desktops (Ubuntu, GNOME, Wayland & X11).

Key tenets:
- **Zero Local Model Overhead**: All transcription is offloaded to remote Groq Cloud Whisper (`whisper-large-v3-turbo`) for near-instant response times without heating up the GPU/CPU.
- **Distraction-Free UI**: An unobtrusive floating triad pill docked at the bottom center of the screen during recording.
- **Seamless User Flow**: Trigger with a global hotkey (e.g., `Super + T`), speak, and tap the **Spacebar** to finish. The transcribed text is automatically placed on the system clipboard (`wl-clipboard`) ready to paste (`Ctrl + V`).
- **Privacy & History**: Audio recordings are temporary (`/tmp/dictate_audio.wav`), and transcription text history is archived strictly locally in `history/`.

---

## 2. Architecture & File Structure

```
dictate/
├── dictate.sh            # Main control bash script (toggle recording / transcription)
├── orb.py                # GTK4 + Cairo floating UI (waveform pill + buttons)
├── space_listener.py     # evdev background listener for global Spacebar tap
├── groq_transcribe.py    # Remote Groq Whisper API client (with auto compression & chunking)
├── dictate.config.json   # Model, language, and temperature config
├── ai_chat.sh            # Launcher for experimental voice AI chat client
├── ai_chat.py            # GTK4 voice AI chat client with Groq LLM integration
├── README.md             # End-user setup and installation documentation
├── AGENTS.md             # Agent and contributor technical reference
├── .gitignore            # Ignores .env, *.log, *.wav, *.pid, models/, bin/, history/
└── history/              # Local storage for transcription history (ignored in git)
```

---

## 3. Execution & Workflow Lifecycle

### A. Start Recording (`dictate.sh` branch 1)
1. Checks for required binaries (`pw-record`, `wl-copy`, `python3`) and `GROQ_API_KEY`.
2. Starts PipeWire audio recording:
   ```bash
   pw-record --format=s16 --rate=16000 --channels=1 /tmp/dictate_audio.wav
   ```
3. Records PID in `/tmp/dictate_recording.pid`.
4. Spawns `orb.py` in the background (PID in `/tmp/dictate_gui.pid`).
5. Spawns `space_listener.py` in the background (PID in `/tmp/dictate_listener.pid`).

### B. While Recording
- `orb.py` reads audio input via PyAudio, computes FFT frequency spectrum across 19 bands, and renders a live, smooth Cairo waveform pill docked at the bottom center.
- `space_listener.py` listens to `/dev/input/event*` devices for a `KEY_SPACE` press.

### C. Stop & Transcription (`dictate.sh` branch 2)
1. Sends `SIGUSR1` to `orb.py` to switch UI into the loading animation state.
2. Stops `pw-record` cleanly and removes the lock file.
3. Kills `space_listener.py`.
4. Executes `groq_transcribe.py /tmp/dictate_audio.wav`:
   - Checks file size: if $\le$ 24 MB, sends directly to Groq API.
   - If $>$ 24 MB, converts/compresses audio to MP3 using `ffmpeg`.
   - If still $>$ 24 MB (long marathon recordings), splits into 10-minute segments and stitches results.
5. Terminates `orb.py` (`SIGTERM`).
6. Copies output text to Wayland clipboard using `wl-copy`.
7. Appends output text to local history:
   - `history/latest.txt`
   - `history/<timestamp>.txt`
8. Dispatches desktop notification (`notify-send`).

---

## 4. Critical Guidelines for AI Agents

1. **Remote AI Exclusively**:
   - Do NOT commit or reintroduce local AI weights, whisper.cpp binaries, ggml shared objects, or heavy local speech-to-text models.
   - Keep transcription lightweight and remote via `groq_transcribe.py`.

2. **Absolute Privacy of User History**:
   - `history/` stores the user's personal dictation transcripts.
   - **NEVER** stage, commit, or push any files under `history/` or `.env`.
   - Always ensure `.gitignore` contains `history/` and `.env`.

3. **Portability & Pathing**:
   - Avoid hardcoding specific user directories (e.g., `/home/username/`).
   - Use dynamic relative resolution in Python:
     ```python
     SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
     ```
   - In shell scripts, use:
     ```bash
     SCRIPT_DIR="$(dirname "$0")"
     ```

4. **UI Placement**:
   - The floating recording popup in `orb.py` must stay positioned at the bottom center of the display to prevent obstructing user content.
   - It relies on `GDK_BACKEND=x11` + `xdotool windowmove` to position reliably on GNOME Wayland/XWayland.

5. **Audio Capture**:
   - `pw-record` expects 16kHz mono 16-bit PCM WAV (`--format=s16 --rate=16000 --channels=1`), which is the optimal format for Whisper transcription.
