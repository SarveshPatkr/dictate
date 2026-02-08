# Dictate for Linux 🎙️

A minimal, system-wide dictation tool for Linux. 

## 🚀 Features
- **Visual Orb:** A red ball pulses to your voice while recording.
- **Stop on Space:** Tap the **Space** key to stop recording instantly (or press Super+T again).
- **Fast Transcription:** Uses Groq Cloud (Whisper).
- **Wayland Ready:** Built to work natively with Ubuntu 22.04+.

## 🛠️ Setup

### 1. Install Requirements
```bash
sudo apt install wl-clipboard libnotify-bin alsa-utils curl jq python3-pyaudio python3-evdev
```

### 2. Configure API Key
Create a `.env` file in the `dictate` folder:
```bash
GROQ_API_KEY=your_key_here
```

### 3. Permissions (For Space to Stop)
```bash
sudo chmod 666 /dev/input/event*
```

### 4. Set Keyboard Shortcut
1.  Open **Settings** -> **Keyboard** -> **View and Customize Shortcuts**.
2.  **Name:** `Dictate Mode`
3.  **Command:** `/home/spatkar/Desktop/dictate/dictate.sh`
4.  **Shortcut:** `Super+T` (Windows Key + T).

## 📂 Usage
- **Start:** Press `Super+T`.
- **Stop:** Press `Super+T` again OR just tap the **Space** bar.
