# Dictate for Linux 🎙️

A minimal, system-wide dictation tool for Linux. 
Press a hotkey to record, press again to transcribe (via Groq Whisper) and copy to clipboard.

## 🚀 Features
- **Visual Orb:** A red ball appears in the top-left and pulses to your voice while recording.
- **Fast Transcription:** Uses Groq Cloud (Whisper) for near-instant results.
- **Wayland Ready:** Built to work natively with Ubuntu 22.04+.

## 🛠️ Setup

### 1. Install Requirements
```bash
sudo apt install wl-clipboard libnotify-bin alsa-utils curl jq python3-pyaudio
```

### 2. Configure API Key
Create a `.env` file in the `dictate` folder:
```bash
GROQ_API_KEY=your_key_here
```

### 3. Set Keyboard Shortcut
1.  Open **Settings** -> **Keyboard** -> **Custom Shortcuts**.
2.  **Name:** `Dictate Mode`
3.  **Command:** `/home/spatkar/Desktop/dictate/dictate.sh`
4.  **Shortcut:** `Super+T` (Windows Key + T).

## 📂 Project Structure
- `dictate.sh`: Main logic for recording and API calls.
- `orb.py`: The audio-reactive visual indicator.
- `.env`: Your secret API key.
