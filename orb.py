import sys
import signal
import gi
import math
import struct
import threading
import pyaudio

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib

class AudioMonitor:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        # Open stream
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=16000,
                                  input=True,
                                  frames_per_buffer=1024)
        self.current_volume = 0
        self.running = True
        
        # Start monitoring thread
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def _monitor_loop(self):
        while self.running:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                
                # Manual RMS calculation (since audioop is gone in Py3.13)
                # Unpack bytes to integers
                shorts = struct.unpack(f"{len(data)//2}h", data)
                sum_squares = sum(s*s for s in shorts)
                rms = math.sqrt(sum_squares / len(shorts))

                # Normalize reasonably (0-32768 -> 0.0-1.0 approx)
                if rms > 0:
                     # Log scale fits human hearing better
                     level = math.log(rms + 1, 10) / 4.5 
                else:
                    level = 0
                
                self.current_volume = min(max(level, 0), 1.0)
            except Exception as e:
                print(f"Error reading audio: {e}")
                
    def get_volume(self):
        return self.current_volume

    def stop(self):
        self.running = False
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

class RecordingOrb(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Dictate Overlay")
        
        self.set_default_size(100, 100)
        self.set_decorated(False)
        self.set_focusable(False)
        
        # Transparent background
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window {
                background-color: transparent;
            }
            .orb {
                background-color: #ff3b30;
                border-radius: 50%;
                box-shadow: 0 0 10px rgba(255, 59, 48, 0.4);
                transition: min-width 0.05s, min-height 0.05s;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Center layout
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        
        self.orb = Gtk.Box()
        self.orb.add_css_class("orb")
        
        # Base size
        self.base_size = 40
        self.orb.set_size_request(self.base_size, self.base_size)
        
        box.append(self.orb)
        self.set_child(box)

        # Audio Monitor
        self.monitor = AudioMonitor()
        
        # Update UI every 30ms (approx 30fps)
        GLib.timeout_add(30, self.update_orb)

    def update_orb(self):
        vol = self.monitor.get_volume()
        
        # Noise Gate / Thresholding
        # Ignore volume below 40% (0.4) to filter out fan noise/clicks
        if vol < 0.45:
            target_scale = 1.0
        else:
            # Map remaining range (0.45 - 1.0) to scale (1.0 - 2.0)
            # (vol - threshold) / (1 - threshold)
            normalized = (vol - 0.45) / 0.55
            target_scale = 1.0 + (normalized * 1.0) 
            
        target_size = int(self.base_size * target_scale)
        
        self.orb.set_size_request(target_size, target_size)
        
        return True

    def cleanup(self):
        self.monitor.stop()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.orb")
        self.win = None

    def do_activate(self):
        self.win = RecordingOrb(self)
        self.win.present()

if __name__ == "__main__":
    app = OrbApp()
    
    def signal_handler(signum, frame):
        if app.win:
            app.win.cleanup()
        sys.exit(0)
        
    signal.signal(signal.SIGTERM, signal_handler)
    
    app.run(None)
