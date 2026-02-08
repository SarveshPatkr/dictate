import sys
import os
import signal
from evdev import InputDevice, categorize, ecodes

# This script listens for the SPACE key and triggers the stop sequence
LOCK_FILE = "/tmp/dictate_recording.pid"
DICTATE_SCRIPT = "/home/spatkar/Desktop/dictate/dictate.sh"

def main():
    # Find the keyboard device
    # We look for devices that have a 'SPACE' key
    devices = [InputDevice(path) for path in os.listdir('/dev/input') if 'event' in path]
    kbd = None
    for dev in devices:
        if ecodes.KEY_SPACE in dev.capabilities().get(ecodes.EV_KEY, []):
            kbd = dev
            break

    if not kbd:
        sys.exit(1)

    # Listen for keys
    for event in kbd.read_loop():
        if event.type == ecodes.EV_KEY:
            key = categorize(event)
            if key.keycode == 'KEY_SPACE' and key.keystate == key.key_down:
                # Trigger the dictate script (which will stop the recording)
                os.system(f"bash {DICTATE_SCRIPT}")
                sys.exit(0)

if __name__ == "__main__":
    # Handle cleanup
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    try:
        main()
    except Exception:
        sys.exit(1)
