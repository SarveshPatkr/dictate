import time
import os
import sys
import fcntl
from evdev import UInput, ecodes as e

# Path to the trigger pipe
PIPE_PATH = "/tmp/dictate_paste_trigger"

def main():
    print("Starting Paste Daemon...")
    
    # 1. Create Virtual Keyboard
    try:
        ui = UInput(name="Dictate Virtual Keyboard")
        print("Virtual Keyboard Created.")
    except PermissionError:
        print("Error: Permission denied. Run with sudo or add user to 'input' group.")
        return

    # 2. Create Named Pipe (FIFO)
    if not os.path.exists(PIPE_PATH):
        os.mkfifo(PIPE_PATH)
        # Allow anyone to write to it
        os.chmod(PIPE_PATH, 0o666)

    print("Listening for triggers...")
    
    while True:
        # Open pipe (blocking wait for writer)
        with open(PIPE_PATH, "r") as fifo:
            data = fifo.read()
            if "paste" in data:
                print("Trigger received! Pasting...")
                
                # Press Ctrl+V
                ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1) # Ctrl Down
                ui.write(e.EV_KEY, e.KEY_V, 1)        # V Down
                ui.syn()
                
                time.sleep(0.05)
                
                ui.write(e.EV_KEY, e.KEY_V, 0)        # V Up
                ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 0) # Ctrl Up
                ui.syn()
                print("Pasted.")

if __name__ == "__main__":
    main()
