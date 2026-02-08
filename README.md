# Dictate for Linux (Pro Version) 🎙️

A beautiful, Siri-inspired, system-wide dictation tool for Ubuntu (Wayland). 

## 🚀 Features
- **Pro Visuals:** A glassy white pearl with randomized, audio-reactive plasma whisps.
- **Organic Physics:** Everything pulses and flows smoothly to your voice.
- **Smart Transitions:** Morphs from a pulsing orb to a loading spinner instantly.
- **Space-to-Stop:** Tap the **Space** bar to finish talking (or press Super+T again).
- **Fast Transcription:** Powered by Groq Cloud (Whisper Large V3 Turbo).

## 🛠️ One-Time Setup

### 1. Install System Dependencies
```bash
sudo apt install wl-clipboard libnotify-bin alsa-utils curl jq python3-pyaudio python3-evdev
```

### 2. Set Up Permanent Permissions
This ensures the "Space to Stop" feature works even after you restart your laptop:
```bash
sudo bash -c 'echo "KERNEL==\"event*\", NAME=\"input/%k\", MODE=\"0666\", GROUP=\"input\"" > /etc/udev/rules.d/99-dictate-input.rules'
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### 3. Create Keyboard Shortcut
1.  Open **Settings** -> **Keyboard** -> **View and Customize Shortcuts**.
2.  Scroll to **Custom Shortcuts** -> **Add Shortcut**.
3.  **Name:** `Dictate Mode`
4.  **Command:** `/home/spatkar/Desktop/dictate/dictate.sh`
5.  **Shortcut:** `Super+T` (Windows Key + T).

## 📂 Usage
- **Start Recording:** Press `Super + T`.
- **Talk:** Watch the energy field react to your voice.
- **Stop & Transcribe:** Tap the **Space Bar**.
- **Paste:** Press `Ctrl + V` anywhere.

## ⚙️ Configuration
- The API key is stored in `.env`.
- To adjust visual sensitivity, edit `orb.py` and change the `vol < 0.45` threshold.
