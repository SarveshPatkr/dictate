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
        self.angles = [0, 0, 0] # Red, Purple, Blue
        
        self.overlay = Gtk.Overlay()
        
        # Layer 1: Blue Aura (Largest)
        self.blue = Gtk.Box()
        self.blue.add_css_class("plasma-blue")
        
        # Layer 2: Purple Plasma (Middle)
        self.purple = Gtk.Box()
        self.purple.add_css_class("plasma-purple")
        
        # Layer 3: Red Plasma (Innermost)
        self.red = Gtk.Box()
        self.red.add_css_class("plasma-red")
        
        # Layer 4: White Core (Center)
        self.core = Gtk.Box()
        self.core.add_css_class("white-core")
        self.core.set_size_request(65, 65) # Bigger core
        
        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(60, 60)
        self.spinner.set_visible(False)

        # Build stack
        for w in [self.blue, self.purple, self.red, self.core, self.spinner]:
            w.set_halign(Gtk.Align.CENTER)
            w.set_valign(Gtk.Align.CENTER)
            if w == self.blue: self.overlay.set_child(w)
            else: self.overlay.add_overlay(w)
        
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
            
            # Rotate angles
            self.angles[0] = (self.angles[0] + 8) % 360  # Red (Fast)
            self.angles[1] = (self.angles[1] + 5) % 360  # Purple (Medium)
            self.angles[2] = (self.angles[2] + 3) % 360  # Blue (Slow)
            
            # Radii logic (Tight gaps)
            # Core: 65, Red: 75, Purple: 90, Blue: 110
            s_red = int(75 + self.vol_smooth * 50)
            s_purple = int(90 + self.vol_smooth * 70)
            s_blue = int(110 + self.vol_smooth * 90)
            
            self.red.set_size_request(s_red, s_red)
            self.purple.set_size_request(s_purple, s_purple)
            self.blue.set_size_request(s_blue, s_blue)
            self.core.set_size_request(int(65 + self.vol_smooth*20), int(65 + self.vol_smooth*20))

            # Update CSS with "Patchy" conic gradients and rotations
            css = f"""
                window {{ background-color: transparent; }}
                .white-core {{
                    background: radial-gradient(circle at 30% 30%, #ffffff, #e5e5ea);
                    border-radius: 50%;
                    box-shadow: 0 0 25px rgba(255, 255, 255, 0.9);
                }}
                .plasma-red {{
                    background: conic-gradient(from {self.angles[0]}deg, #ff3b30 0%, transparent 30%, #ff9500 50%, transparent 80%, #ff3b30 100%);
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
                    background: conic-gradient(from {self.angles[2]}deg, #007aff 0%, transparent 40%, #5ac8fa 60%, transparent 90%, #007aff 100%);
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
        super().__init__(application_id="com.openclaw.dictate.plasma.v2.orb")
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
