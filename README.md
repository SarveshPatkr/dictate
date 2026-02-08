# Speech-to-Text Ubuntu / Linux (Groq AI Whisper) 🎙️

A lightweight, system-wide **Linux dictation tool** for Ubuntu and other distributions. This tool provides near-instant **voice-to-text** (STT) capabilities in every application using the high-speed **Groq API**.

---

## 🚀 Key Features

- **Voice to Text for Ubuntu**: Works system-wide—use your voice to type in any app (Browser, WhatsApp, IDE, Terminal).
- **Fastest Speech to Text Linux**: Leverages Groq Cloud (Whisper Large V3 Turbo) for sub-second transcription speeds.
- **Linux Voice Typing Shortcut**: Trigger recording with a hotkey and stop with the space bar for a seamless workflow.
- **Wayland & X11 Compatible**: Native support for modern Ubuntu (Wayland) using `wl-clipboard`.
- **Free Linux STT**: A powerful, open-source alternative to proprietary dictation software.

---

## 🛠️ Installation & Setup

### 1. Install Dependencies
```bash
sudo apt update && sudo apt install -y wl-clipboard libnotify-bin alsa-utils curl jq python3-pyaudio python3-evdev
```

### 2. Set Up Permanent Permissions
Ensures the "Stop on Space" feature works after a restart:
```bash
sudo bash -c 'echo "KERNEL==\"event*\", NAME=\"input/%k\", MODE=\"0666\", GROUP=\"input\"" > /etc/udev/rules.d/99-dictate-input.rules'
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 3. Configure API Key
Create a `.env` file in the project folder:
```bash
GROQ_API_KEY=your_key_here
```

### 4. Create Keyboard Shortcut
1. Open **Settings** -> **Keyboard** -> **View and Customize Shortcuts**.
2. Scroll to **Custom Shortcuts** -> **Add Shortcut**.
   - **Name**: `Linux Speech-to-Text`
   - **Command**: `/home/spatkar/Desktop/dictate/dictate.sh`
   - **Shortcut**: `Super + T`

---

## 📂 How to Use

1. **Start**: Press `Super + T`.
2. **Talk**: A visual energy orb appears while you speak.
3. **Stop**: Tap the **Space Bar** (or Super+T again).
4. **Paste**: The text is copied to your clipboard instantly. Press `Ctrl + V`.

---

## 🧠 Technical Overview
Built using **Bash** and **Python 3**. It uses **PipeWire (`pw-record`)** for audio capture and the **Groq API** for high-performance AI inference. Designed specifically for **Ubuntu Linux** users who need a fast, reliable dictation tool.
