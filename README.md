# Dictate for Linux 🎙️

A blazing fast, system-wide dictation tool for Linux. 
Press a hotkey to record, press again to transcribe (via Groq Whisper) and copy to clipboard.

## ⚡ Tech Stack
*   **Language:** Bash (Shell Scripting)
*   **Audio Engine:** `arecord` (ALSA) - Native Linux audio recording.
*   **API:** Groq Cloud (Whisper Large V3 Turbo) - Extremely fast inference.
*   **Clipboard:** `wl-clipboard` (Wayland) - For modern Linux desktop integration.
*   **Utils:** `curl` (Network), `jq` (JSON parsing), `libnotify` (Desktop notifications).

## 🛠️ How It Works (The "Tricks")
1.  **State Management (The Toggle):**
    The script checks for a "lock file" (`/tmp/dictate_recording.pid`).
    *   *File exists?* -> We are recording. **Stop** the process.
    *   *File missing?* -> We are idle. **Start** recording.

2.  **Visual Feedback (The "Orb"):**
    When recording starts, we launch a `zenity` dialog (a small floating window with a pulsating bar) to indicate the "Listening" state. This provides clear visual confirmation on screen.
    
3.  **Graceful Audio Handling:**
    Instead of abruptly killing the recording (which corrupts WAV files), we send a `SIGTERM` signal. This tells `arecord` to finish writing the file headers properly before quitting, preventing "Unexpected EOF" errors.

3.  **Wayland Integration:**
    Modern Linux (Ubuntu 22.04+) uses Wayland, which blocks apps from stealing clipboard focus. We use `wl-copy` to explicitly ask the compositor to accept our text.

## 🚀 Setup

### 1. Install Requirements
```bash
sudo apt install wl-clipboard libnotify-bin alsa-utils curl jq
```

### 2. Configure API Key
Create a `.env` file in the `dictate` folder:
```bash
GROQ_API_KEY=gsk_your_key_here
```
*(Get a key from [console.groq.com](https://console.groq.com))*

### 3. Create Keyboard Shortcut
1.  Open **Settings** -> **Keyboard** -> **View and Customize Shortcuts**.
2.  Select **Custom Shortcuts** -> **Add Shortcut**.
3.  **Name:** `Dictate Mode`
4.  **Command:** `/home/spatkar/Desktop/dictate/dictate.sh`
5.  **Shortcut:** `Super+T` (Windows Key + T) or `F4`.

## 📱 Compatibility
*   **OS:** Ubuntu, Fedora, Arch, Debian.
*   **Display Server:** Optimized for **Wayland** (default on Ubuntu 22.04+).
    *   *For X11/Old Linux:* Replace `wl-copy` with `xclip -selection clipboard` in the script.
*   **Hardware:** Works on any laptop/PC with a microphone.

## 📂 Project Structure
*   `dictate.sh`: The brain. Handles logic, recording, and API calls.
*   `.env`: Stores your secret API key (ignored by Git).
*   `.gitignore`: Keeps secrets and temp files out of version control.
