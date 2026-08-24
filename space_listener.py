import sys
import os
import signal
import time
from evdev import InputDevice, categorize, ecodes

# This script listens for the SPACE key and triggers the stop sequence
LOCK_FILE = "/tmp/dictate_recording.pid"
DICTATE_SCRIPT = "/home/spatkar/Desktop/dictate/dictate.sh"
LOG_FILE = "/tmp/dictate_debug.log"

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.ctime()}: [SpaceListener] {msg}\n")

def main():
    log("Starting SpaceListener...")
    
    # Find the keyboard device
    input_dir = '/dev/input'
    devices = []
    for entry in os.listdir(input_dir):
        if entry.startswith('event'):
            full_path = os.path.join(input_dir, entry)
            try:
                devices.append(InputDevice(full_path))
            except Exception:
                continue

    kbds = []
    for dev in devices:
        try:
            caps = dev.capabilities()
            if ecodes.EV_KEY in caps:
                if ecodes.KEY_SPACE in caps[ecodes.EV_KEY]:
                    log(f"Found potential keyboard: {dev.path} ({dev.name})")
                    kbds.append(dev)
        except Exception:
            continue

    if not kbds:
        log("Error: No keyboard device found with a Space key.")
        sys.exit(1)

    log(f"Listening on {len(kbds)} devices...")
    
    def handle_event(dev):
        try:
            for event in dev.read_loop():
                if event.type == ecodes.EV_KEY:
                    key = categorize(event)
                    if key.keycode == 'KEY_SPACE' and key.keystate == key.key_down:
                        log(f"SPACE detected on {dev.path}! Triggering stop...")
                        # Run the script in the background to avoid blocking
                        os.system(f"bash {DICTATE_SCRIPT} &")
                        os._exit(0)
        except Exception as e:
            log(f"Error on {dev.path}: {e}")

    import threading
    for kbd in kbds:
        t = threading.Thread(target=handle_event, args=(kbd,), daemon=True)
        t.start()

    while True:
        time.sleep(1)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s, f: os._exit(0))
    try:
        main()
    except Exception as e:
        log(f"CRASHED: {e}")
        sys.exit(1)
