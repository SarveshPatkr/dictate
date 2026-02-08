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
        
        # Random speeds and directions
        self.angles = [random.randint(0,360) for _ in range(3)]
        self.base_speeds = [random.uniform(2, 6) * random.choice([-1, 1]) for _ in range(3)]
        
        self.overlay = Gtk.Overlay()
        
        # --- LAYER ORDER (Back to Front) ---
        
        # 1. Blue Plasma (Largest - Bottom)
        self.blue = Gtk.Box()
        self.blue.add_css_class("plasma-blue")
        
        # 2. Purple Plasma (Middle)
        self.purple = Gtk.Box()
        self.purple.add_css_class("plasma-purple")
        
        # 3. Red Plasma (Innermost - closest to core)
        self.red = Gtk.Box()
        self.red.add_css_class("plasma-red")
        
        # 4. White Core (TOP - Front)
        self.core = Gtk.Box()
        self.core.add_css_class("white-core")
        self.core_base_size = 70
        self.core.set_size_request(self.core_base_size, self.core_base_size)
        
        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(60, 60)
        self.spinner.set_visible(False)

        # Assemble: Blue first (bottom), then Purple, then Red, then Core (top)
        self.overlay.set_child(self.blue)
        self.overlay.add_overlay(self.purple)
        self.overlay.add_overlay(self.red)
        self.overlay.add_overlay(self.core)
        self.overlay.add_overlay(self.spinner)
        
        for w in [self.blue, self.purple, self.red, self.core, self.spinner]:
            w.set_halign(Gtk.Align.CENTER)
            w.set_valign(Gtk.Align.CENTER)
            
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
            
            # 1. Randomized & Audio-Reactive Rotation
            speed_boost = 1.0 + (self.vol_smooth * 5.0)
            for i in range(3):
                self.angles[i] = (self.angles[i] + (self.base_speeds[i] * speed_boost)) % 360
            
            # 2. Tight radius gaps (Core at 70px)
            # Blue (Largest): ~105px
            # Purple (Middle): ~90px
            # Red (Innermost): ~80px
            s_core = int(self.core_base_size + self.vol_smooth * 20)
            s_blue = int(s_core + 30 + self.vol_smooth * 40)
            s_purple = int(s_core + 15 + self.vol_smooth * 25)
            s_red = int(s_core + 5 + self.vol_smooth * 15)
            
            self.core.set_size_request(s_core, s_core)
            self.blue.set_size_request(s_blue, s_blue)
            self.purple.set_size_request(s_purple, s_purple)
            self.red.set_size_request(s_red, s_red)

            # 3. CSS with Patchy Conic Gradients
            css = f"""
                window {{ background-color: transparent; }}
                .white-core {{
                    background: radial-gradient(circle at 30% 30%, #ffffff, #f2f2f7);
                    border-radius: 50%;
                    box-shadow: 0 0 20px rgba(255, 255, 255, 0.8), inset 0 0 10px rgba(0,0,0,0.05);
                }}
                .plasma-red {{
                    background: conic-gradient(from {self.angles[0]}deg, #ff3b30 0%, transparent 20%, #ff9500 40%, transparent 70%, #ff3b30 100%);
                    border-radius: 50%;
                    opacity: 0.8;
                    filter: blur(2px);
                }}
                .plasma-purple {{
                    background: conic-gradient(from {self.angles[1]}deg, #5856d6 0%, transparent 25%, #af52de 50%, transparent 75%, #5856d6 100%);
                    border-radius: 50%;
                    opacity: 0.6;
                    filter: blur(4px);
                }}
                .plasma-blue {{
                    background: conic-gradient(from {self.angles[2]}deg, #007aff 0%, transparent 35%, #5ac8fa 65%, transparent 90%, #007aff 100%);
                    border-radius: 50%;
                    opacity: 0.4;
                    filter: blur(6px);
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
        super().__init__(application_id="com.openclaw.dictate.plasma.v4.orb")
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
