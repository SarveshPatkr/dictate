#!/usr/bin/env python3
import sys
import signal
import gi
import math
import struct
import threading
import pyaudio
import time
import random

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
        except Exception:
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
                level = math.log(rms + 1, 10) / 4.5 if rms > 0 else 0
                self.current_volume = min(max(level, 0), 1.0)
            except Exception: pass
                
    def get_volume(self):
        return self.current_volume

    def stop(self):
        self.running = False
        if self.p:
            try:
                self.stream.stop_stream()
                self.stream.close()
                self.p.terminate()
            except: pass

class RecordingOrb(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Dictate Overlay")
        self.set_default_size(250, 250)
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.state = 'recording'
        self.vol_smooth = 0
        
        # Random speeds and directions for each layer
        self.angles = [random.randint(0,360) for _ in range(3)]
        self.base_speeds = [random.uniform(2, 5) * random.choice([-1, 1]) for _ in range(3)]
        
        self.overlay = Gtk.Overlay()
        
        # --- LAYER ORDER (Bottom to Top) ---
        
        # 1. White Core (The Canvas at the bottom)
        self.core = Gtk.Box()
        self.core.add_css_class("white-core")
        self.core_base_size = 85
        self.core.set_size_request(self.core_base_size, self.core_base_size)
        
        # 2. Blue Plasma (Smallest - Inside)
        self.red = Gtk.Box()
        self.red.add_css_class("plasma-red")
        
        # 3. Purple Plasma (Medium - Inside)
        self.purple = Gtk.Box()
        self.purple.add_css_class("plasma-purple")
        
        # 4. Red Plasma (Largest - Overflowing)
        self.blue = Gtk.Box()
        self.blue.add_css_class("plasma-blue")
        
        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(60, 60)
        self.spinner.set_visible(False)

        # Build stack
        # Core first (bottom)
        self.overlay.set_child(self.core)
        # Then the lights on TOP of the core
        self.overlay.add_overlay(self.red)
        self.overlay.add_overlay(self.purple)
        self.overlay.add_overlay(self.blue)
        self.overlay.add_overlay(self.spinner)
        
        self.set_child(self.overlay)

        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.monitor = AudioMonitor()
        GLib.timeout_add(30, self.update_ui)

    def update_ui(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            vol = vol if vol > 0.45 else 0
            self.vol_smooth += (vol - self.vol_smooth) * 0.2
            
            # 1. Random & Audio-Reactive Rotation
            speed_boost = 1.0 + (self.vol_smooth * 4.0) # Spin much faster when talking
            for i in range(3):
                self.angles[i] = (self.angles[i] + (self.base_speeds[i] * speed_boost)) % 360
            
            # 2. Size Logic (Tight on top of core)
            # Core is 85px. 
            # Blue (Topmost/Largest) should be ~92px (slight overflow)
            # Purple (Middle) should be ~75px (inside)
            # Red (Smallest) should be ~55px (deep inside)
            
            s_core = int(self.core_base_size + self.vol_smooth * 20)
            s_blue = int(s_core + 8 + self.vol_smooth * 15)
            s_purple = int(s_core - 10 + self.vol_smooth * 10)
            s_red = int(s_core - 30 + self.vol_smooth * 5)
            
            self.core.set_size_request(s_core, s_core)
            self.blue.set_size_request(s_blue, s_blue)
            self.purple.set_size_request(s_purple, s_purple)
            self.red.set_size_request(s_red, s_red)

            # 3. Update CSS with Patchy Gradients
            css = f"""
                window {{ background-color: transparent; }}
                .white-core {{
                    background: radial-gradient(circle at 30% 30%, #ffffff, #e5e5ea);
                    border-radius: 50%;
                    box-shadow: 0 0 20px rgba(255, 255, 255, 0.6);
                }}
                .plasma-blue {{
                    background: conic-gradient(from {self.angles[0]}deg, rgba(0, 122, 255, 0.7) 0%, transparent 40%, rgba(90, 200, 250, 0.5) 60%, transparent 90%);
                    border-radius: 50%;
                    filter: blur(2px);
                }}
                .plasma-purple {{
                    background: conic-gradient(from {self.angles[1]}deg, rgba(88, 86, 214, 0.6) 0%, transparent 25%, rgba(175, 82, 222, 0.4) 50%, transparent 75%);
                    border-radius: 50%;
                    filter: blur(3px);
                }}
                .plasma-red {{
                    background: conic-gradient(from {self.angles[2]}deg, rgba(255, 59, 48, 0.8) 0%, transparent 30%, rgba(255, 149, 0, 0.6) 50%, transparent 80%);
                    border-radius: 50%;
                    filter: blur(1px);
                }}
                .spinner {{ color: #007aff; }}
            """.encode()
            self.css_provider.load_from_data(css)
            
        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop()
        for w in [self.blue, self.purple, self.red, self.core]:
            w.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.plasma.v3.orb")
        self.win = None

    def do_activate(self):
        self.win = RecordingOrb(self)
        self.win.present()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.on_sigusr1)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.on_sigterm)

    def on_sigusr1(self):
        if self.win: GLib.idle_add(self.win.start_loading)
        return True

    def on_sigterm(self):
        if self.win: self.win.monitor.stop()
        self.quit()
        return False

if __name__ == "__main__":
    app = OrbApp()
    app.run(None)
