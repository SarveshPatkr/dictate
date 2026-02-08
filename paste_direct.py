import time
import sys
import os
from evdev import UInput, ecodes as e

# Log everything to the debug log
LOG_FILE = "/tmp/dictate_debug.log"

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.ctime()}: [PasteTool] {msg}\n")

try:
    log("Creating virtual keyboard...")
    # 1. Create the virtual keyboard with ALL necessary keys for a standard layout
    cap = {
        e.EV_KEY: [e.KEY_LEFTCTRL, e.KEY_V, e.KEY_C, e.KEY_A, e.KEY_X, e.KEY_ENTER]
    }
    
    with UInput(cap, name="Dictate Keyboard Overlay") as ui:
        log("Keyboard created. Waiting for OS registration...")
        # 2. INCREASE DELAY: Give the OS plenty of time to map the device to the seat
        time.sleep(2.0)
        
        log("Sending Ctrl+V sequence...")
        # 3. Press Ctrl+V with robust timing
        ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1)
        ui.syn()
        time.sleep(0.2)
        
        ui.write(e.EV_KEY, e.KEY_V, 1)
        ui.syn()
        time.sleep(0.2)
        
        ui.write(e.EV_KEY, e.KEY_V, 0)
        ui.syn()
        time.sleep(0.1)
        
        ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 0)
        ui.syn()
        
        log("Paste sequence finished.")
        
except PermissionError:
    log("CRITICAL: Permission Denied to /dev/uinput")
except Exception as err:
    log(f"ERROR: {err}")
