# Dictate for Linux

A minimal, system-wide dictation tool for Linux (Wayland/X11). 
Press a hotkey to record, press again to transcribe (via Groq Whisper) and copy to clipboard.

## Setup

1. **Install Dependencies**
   ```bash
   sudo apt install wl-clipboard libnotify-bin alsa-utils curl jq
   ```

2. **Configure API Key**
   Create a `.env` file in this folder:
   ```bash
   GROQ_API_KEY=your_key_here
   ```

3. **Set Keyboard Shortcut**
   - Go to Settings -> Keyboard -> Custom Shortcuts.
   - Command: `/path/to/dictate.sh`
   - Key: `Super+T` (or your choice).

## Usage
- **Start:** Press `Super+T`. (Notification: "Listening... 🎙️")
- **Stop:** Press `Super+T` again. (Notification: "Copied!")
- **Paste:** `Ctrl+V`.
