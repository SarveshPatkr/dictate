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
        try:
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(format=pyaudio.paInt16,
                                      channels=1,
                                      rate=16000,
                                      input=True,
                                      frames_per_buffer=1024)
        except Exception as e:
            print(f"Mic error: {e}")
            self.p = None
            
        self.current_volume = 0
        self.running = True
        
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def _monitor_loop(self):
        while self.running and self.p:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                shorts = struct.unpack(f"{len(data)//2}h", data)
                sum_squares = sum(s*s for s in shorts)
                rms = math.sqrt(sum_squares / (len(shorts) or 1))
                if rms > 0:
                     level = math.log(rms + 1, 10) / 4.5 
                else:
                    level = 0
                self.current_volume = min(max(level, 0), 1.0)
            except Exception:
                pass
                
    def get_volume(self):
        return self.current_volume

    def stop(self):
        self.running = False
        if self.p:
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()

class RecordingOrb(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Dictate Overlay")
        self.set_default_size(250, 100)
        self.set_decorated(False)
        self.set_focusable(False)
        
        # State: 'recording' or 'loading'
        self.state = 'recording'
        
        # CSS Styles
        self.css_provider = Gtk.CssProvider()
        self.apply_css()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.set_halign(Gtk.Align.CENTER)
        self.main_box.set_valign(Gtk.Align.CENTER)
        
        self.orb = Gtk.Box()
        self.orb.add_css_class("orb")
        self.base_size = 40
        self.orb.set_size_request(self.base_size, self.base_size)
        
        self.main_box.append(self.orb)
        self.set_child(self.main_box)

        self.monitor = AudioMonitor()
        GLib.timeout_add(30, self.update_ui)

    def apply_css(self):
        if self.state == 'recording':
            css = b"""
                window { background-color: transparent; }
                .orb {
                    background-color: #ff3b30;
                    border-radius: 50%;
                    box-shadow: 0 0 10px rgba(255, 59, 48, 0.4);
                    transition: all 0.2s ease;
                }
            """
        else: # Loading bar state
            css = b"""
                window { background-color: transparent; }
                .orb {
                    background-color: #007aff;
                    border-radius: 5px;
                    min-width: 200px;
                    min-height: 8px;
                    box-shadow: 0 0 10px rgba(0, 122, 255, 0.4);
                    transition: all 0.4s ease;
                }
            """
        self.css_provider.load_from_data(css)

    def update_ui(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            scale = 1.0 + (vol * 1.0) if vol > 0.45 else 1.0
            size = int(self.base_size * scale)
            self.orb.set_size_request(size, size)
        else:
            # Pulsate the loading bar width slightly
            pulse = 200 + (math.sin(time.time() * 10) * 20)
            self.orb.set_size_request(int(pulse), 8)
        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop() # Stop mic while loading
        self.apply_css()

    def cleanup(self):
        self.monitor.stop()

import time
class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.orb")
        self.win = None

    def do_activate(self):
        self.win = RecordingOrb(self)
        self.win.present()
        
    def trigger_loading(self):
        if self.win:
            GLib.idle_add(self.win.start_loading)

if __name__ == "__main__":
    app = OrbApp()
    
    # SIGUSR1 will trigger the loading state
    def sigusr1_handler(signum, frame):
        app.trigger_loading()
        
    def sigterm_handler(signum, frame):
        if app.win: app.win.cleanup()
        sys.exit(0)
        
    signal.signal(signal.SIGUSR1, sigusr1_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)
    
    app.run(None)
