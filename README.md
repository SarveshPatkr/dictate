# Dictate Pro for Linux 🎙️

A high-performance, system-wide dictation tool for Linux (Ubuntu/Wayland). **Dictate Pro** brings a professional, Siri-inspired voice-to-text experience to your desktop, powered by Groq's blazing-fast Whisper API.

---

## ✨ Features
- **Instant Processing**: Near-instant (Not real time) transcription (usually under 10 second) using Groq Cloud.
- **Global Control**: Start with a hotkey, stop with the **Space Bar**.
- **Privacy First**: Local control, no telemetry, and uses your own private API key.

---

## 🛠️ System Requirements
- **OS**: Ubuntu 22.04+ (Works best on Wayland)
- **Audio**: PipeWire or PulseAudio
- **Internet**: Required for the Groq API call

---

## 🚀 Installation & Setup

### 1. Install Dependencies
Run the following command to install the required system tools:
```bash
sudo apt update && sudo apt install -y wl-clipboard libnotify-bin alsa-utils curl jq python3-pyaudio python3-evdev
```

### 2. Set Up Persistent Permissions
For the "Stop on Space" feature to work every time you restart your computer, you must install this udev rule:
```bash
sudo bash -c 'echo "KERNEL==\"event*\", NAME=\"input/%k\", MODE=\"0666\", GROUP=\"input\"" > /etc/udev/rules.d/99-dictate-input.rules'
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 3. Configure your API Key
1. Get a free API key from [Groq Cloud Console](https://console.groq.com/).
2. In the project folder, create or edit the `.env` file:
```bash
GROQ_API_KEY=your_key_here
```

### 4. Create the Keyboard Shortcut
1. Open **Settings** -> **Keyboard** -> **View and Customize Shortcuts**.
2. Scroll to the bottom and select **Custom Shortcuts** -> **Add Shortcut**.
3. Fill in:
   - **Name**: `Dictate Pro`
   - **Command**: `/home/<username>/Desktop/dictate/dictate.sh`
   - **Shortcut**: Press **Super + T** (or your preferred key).

---

## 📂 Usage

1. **Start Recording**: Press `Super + T`.
2. **Talk**: Watch the beautiful energy pearl react to your voice.
3. **Stop & Transcribe**: Tap the **Space Bar** (or press Super+T again).
4. **Paste**: The text is instantly in your clipboard. Press `Ctrl + V` anywhere.

---

## 🧠 Technical Details

- **Backend**: Pure Bash logic for maximum speed and zero runtime overhead.
- **Frontend**: Python 3 + GTK4 + Cairo for high-performance, hardware-accelerated animations.
- **Audio Engine**: `pw-record` (PipeWire) for native, low-latency audio capture.
- **State Management**: Uses a PID-based lock system to toggle between recording and processing states.

---

## 🔒 Security & Privacy
Dictate Pro stores your API key locally in a `.env` file which is automatically ignored by Git to prevent accidental exposure. Audio is captured to a temporary file in `/tmp` and deleted immediately after transcription.

---

## 📄 License
This project is open-source. Feel free to fork, tweak, and make it your own!
