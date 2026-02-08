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
        self.set_default_size(300, 300)
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.state = 'recording'
        self.vol_smooth = 0
        
        # Consistent direction, random speeds
        self.angles = [0, 0, 0]
        self.base_speeds = [random.uniform(1.0, 3.0) for _ in range(3)]
        
        self.overlay = Gtk.Overlay()
        
        # --- LAYER ORDER (Bottom to Top) ---
        # 1. White Core
        self.core = Gtk.Box()
        self.core.add_css_class("white-core")
        self.core_base_size = 85
        
        # 2. Red Plasma (Matching Core Size)
        self.red = Gtk.Box()
        self.red.add_css_class("plasma-red")
        
        # 3. Purple Plasma (Matching Core Size)
        self.purple = Gtk.Box()
        self.purple.add_css_class("plasma-purple")
        
        # 4. Blue Plasma (Matching Core + 1px)
        self.blue = Gtk.Box()
        self.blue.add_css_class("plasma-blue")
        
        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(60, 60)
        self.spinner.set_visible(False)

        # Build stack: Core at bottom, then colored wisps on TOP
        self.overlay.set_child(self.core)
        self.overlay.add_overlay(self.red)
        self.overlay.add_overlay(self.purple)
        self.overlay.add_overlay(self.blue)
        self.overlay.add_overlay(self.spinner)
        
        for w in [self.blue, self.purple, self.red, self.core, self.spinner]:
            w.set_halign(Gtk.Align.CENTER)
            w.set_valign(Gtk.Align.CENTER)
            
        self.set_child(self.overlay)

        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.monitor = AudioMonitor()
        
        GLib.timeout_add(30, self.update_ui)
        GLib.timeout_add(1000, self.randomize_speeds)

    def randomize_speeds(self):
        # Update target speeds every second
        self.target_speeds = [random.uniform(1.0, 4.0) for _ in range(3)]
        return True

    def update_ui(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            vol = vol if vol > 0.45 else 0
            self.vol_smooth += (vol - self.vol_smooth) * 0.2
            
            # 1. Rotation Logic
            # Single direction, varying speeds
            speed_boost = 1.0 + (self.vol_smooth * 10.0)
            for i in range(3):
                # Smoothly interpolate to target speeds
                self.base_speeds[i] += (self.target_speeds[i] - self.base_speeds[i]) * 0.1
                self.angles[i] = (self.angles[i] + (self.base_speeds[i] * speed_boost)) % 360
            
            # 2. Size Logic
            # Core expands with voice. 
            # Red matches Core. 
            # Blue is Core + 1.
            s_core = int(85 + (self.vol_smooth * 50))
            s_red = s_core
            s_purple = s_core
            s_blue = s_core + 1
            
            self.core.set_size_request(s_core, s_core)
            self.red.set_size_request(s_red, s_red)
            self.purple.set_size_request(s_purple, s_purple)
            self.blue.set_size_request(s_blue, s_blue)

            # 3. CSS with High Transparency Linear Gradients
            # Part of the circle is colored, most is transparent so they don't hide each other
            css = f"""
                window {{ background-color: transparent; }}
                .white-core {{
                    background: radial-gradient(circle at 30% 30%, #ffffff, #f2f2f7);
                    border-radius: 50%;
                    box-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
                }}
                .plasma-red {{
                    background: linear-gradient({self.angles[0]}deg, rgba(255, 59, 48, 0.8) 0%, transparent 25%);
                    border-radius: 50%;
                }}
                .plasma-purple {{
                    background: linear-gradient({self.angles[1]}deg, rgba(175, 82, 222, 0.7) 0%, transparent 20%);
                    border-radius: 50%;
                }}
                .plasma-blue {{
                    background: linear-gradient({self.angles[2]}deg, rgba(0, 122, 255, 0.6) 0%, transparent 30%);
                    border-radius: 50%;
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
        super().__init__(application_id="com.openclaw.dictate.transparent.orb")
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
