# Dictate Pro 🎙️

A lightweight, system-wide **Linux dictation tool** for Ubuntu and Linux desktop environments (Wayland & X11). Powered by **Groq Cloud Whisper** (`whisper-large-v3-turbo`) for ultra-fast, accurate voice-to-text with a sleek, distraction-free floating bottom-dock interface.

---

## 🚀 Features

- **System-Wide Voice-to-Text**: Dictate seamlessly into any application—browsers, code editors, chat clients, terminals, or documents.
- **Ultra-Fast Transcription**: Uses Groq Cloud Whisper API for near-instant transcription (typically 1–3 seconds).
- **Distraction-Free Bottom Dock**: Clean floating UI anchored at the bottom center of your screen with real-time waveform reactivity, cancel (`✕`), and confirm (`✓`) buttons.
- **Tap Space to Stop**: Global keyboard listener automatically detects a tap of the Spacebar to stop recording immediately.
- **Auto-Chunking & Compression**: Marathon recordings (>24MB) are automatically compressed via `ffmpeg` and chunked to stay within API limits without truncation.
- **Clipboard Ready**: Transcribed text is automatically copied to your clipboard (`wl-clipboard` / modern Wayland clipboard).
- **Private Local History**: Automatically archives transcription history locally in `history/` (excluded from git tracking).

---

## 🛠️ Prerequisites & Installation

### 1. Install System Dependencies

Run the following command on Ubuntu / Debian:

```bash
sudo apt update && sudo apt install -y \
  pipewire pipewire-audio-client-libraries \
  wl-clipboard libnotify-bin curl jq ffmpeg xdotool \
  python3 python3-gi gir1.2-gtk-4.0 python3-cairo \
  python3-numpy python3-pyaudio python3-evdev python3-requests
```

### 2. Make Scripts Executable

From inside the cloned repository directory:

```bash
chmod +x dictate.sh orb.py space_listener.py groq_transcribe.py ai_chat.sh ai_chat.py
```

### 3. Configure Input Permissions (for "Stop on Space")

The spacebar listener accesses input event devices (`/dev/input/event*`) to detect when Space is pressed globally. Set up the udev rule and add your user to the `input` group:

```bash
sudo bash -c 'echo "KERNEL==\"event*\", NAME=\"input/%k\", MODE=\"0666\", GROUP=\"input\"" > /etc/udev/rules.d/99-dictate-input.rules'
sudo udevadm control --reload-rules && sudo udevadm trigger
sudo usermod -aG input $USER
```
*(Note: If you were just added to the `input` group, log out and log back in, or run `newgrp input`.)*

### 4. Set Up Your Groq API Key

Get a free API key from [Groq Console](https://console.groq.com/keys) and save it in a `.env` file in the project directory:

```bash
echo "GROQ_API_KEY=gsk_your_api_key_here" > .env
```

---

## ⚙️ Configuration (Optional)

You can customize transcription settings in `dictate.config.json`:

```json
{
  "groq_model": "whisper-large-v3-turbo",
  "language": "auto",
  "temperature": 0.0
}
```

- **`groq_model`**: Whisper model to use on Groq (default: `whisper-large-v3-turbo`).
- **`language`**: ISO language code (e.g., `"en"`, `"es"`, `"fr"`, `"de"`, `"hi"`) or `"auto"` for automatic language detection.
- **`temperature`**: Sampling temperature between `0.0` (most deterministic and accurate) and `1.0`.

---

## ⌨️ Setting Up the Keyboard Shortcut

1. Open **GNOME Settings** -> **Keyboard**.
2. Scroll down and click **View and Customize Shortcuts** -> **Custom Shortcuts**.
3. Click **Add Shortcut** (`+`):
   - **Name**: `Dictate Pro`
   - **Command**: `/path/to/dictate/dictate.sh` *(replace with your absolute path, e.g., `/home/username/dictate/dictate.sh`)*
   - **Shortcut**: `Super + T` (or any hotkey you prefer)

---

## 🎙️ How to Use

1. **Start Recording**: Press your shortcut (`Super + T`).
2. **Speak**: A waveform pill appears at the bottom center of your screen reacting to your voice.
3. **Stop Recording**: 
   - Tap the **Spacebar**, or
   - Click the green checkmark button (`✓`) on the dock, or
   - Press `Super + T` again.
4. **Discard Recording**: Click the cancel button (`✕`) to discard the recording without transcribing.
5. **Paste**: Once completed, a desktop notification appears and the text is already copied to your clipboard. Simply press `Ctrl + V` to paste.

---

## 🔍 Troubleshooting & Logs

- **Check logs**: If something doesn't work, inspect the log file:
  ```bash
  cat /tmp/dictate_debug.log
  ```
- **Test manual run**: Test dictation directly from your terminal:
  ```bash
  ./dictate.sh
  ```
- **Space key detection**: If tapping Space does not stop recording, verify your user can read input devices:
  ```bash
  ls -l /dev/input/event*
  ```
  Ensure permissions show `crw-rw-rw-` or group `input`.
