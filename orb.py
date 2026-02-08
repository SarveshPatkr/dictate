#!/usr/bin/env python3
import sys
import signal
import gi
import math
import struct
import threading
import pyaudio
import time

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
        self.angle = 0
        self.vol_smooth = 0
        
        # Overlay for stacking layers
        self.overlay = Gtk.Overlay()
        
        # Layer 1: The Blue Wave (Bottom)
        self.wave_blue = Gtk.Box()
        self.wave_blue.add_css_class("wave-blue")
        self.wave_blue.set_halign(Gtk.Align.CENTER)
        self.wave_blue.set_valign(Gtk.Align.CENTER)
        
        # Layer 2: The Red Wave (Middle)
        self.wave_red = Gtk.Box()
        self.wave_red.add_css_class("wave-red")
        self.wave_red.set_halign(Gtk.Align.CENTER)
        self.wave_red.set_valign(Gtk.Align.CENTER)
        
        # Layer 3: The White Core (Top)
        self.core = Gtk.Box()
        self.core.add_css_class("core-white")
        self.core.set_halign(Gtk.Align.CENTER)
        self.core.set_valign(Gtk.Align.CENTER)
        
        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.add_css_class("spinner")
        self.spinner.set_size_request(60, 60)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)

        self.overlay.set_child(self.wave_blue)
        self.overlay.add_overlay(self.wave_red)
        self.overlay.add_overlay(self.core)
        self.overlay.add_overlay(self.spinner)
        self.set_child(self.overlay)

        # CSS for the "Fluid Blob" effect
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window { background-color: transparent; }
            .wave-blue {
                background: radial-gradient(circle, #007aff 0%, rgba(0, 122, 255, 0) 70%);
                border-radius: 40% 60% 70% 30% / 40% 50% 60% 50%;
                min-width: 140px; min-height: 140px;
                opacity: 0.6;
                transition: all 0.3s ease-out;
            }
            .wave-red {
                background: radial-gradient(circle, #ff3b30 0%, rgba(255, 59, 48, 0) 70%);
                border-radius: 60% 40% 30% 70% / 50% 60% 40% 60%;
                min-width: 120px; min-height: 120px;
                opacity: 0.7;
                transition: all 0.2s ease-out;
            }
            .core-white {
                background: radial-gradient(circle at 30% 30%, #ffffff 0%, #f2f2f7 100%);
                border-radius: 50%;
                min-width: 40px; min-height: 40px;
                box-shadow: 0 0 20px rgba(255, 255, 255, 0.8),
                            inset 0 0 10px rgba(0, 0, 0, 0.1);
                transition: all 0.1s ease-out;
            }
            .spinner { color: #007aff; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.monitor = AudioMonitor()
        GLib.timeout_add(30, self.update_ui)

    def update_ui(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            # Noise gate
            vol = vol if vol > 0.48 else 0
            # Smoothing
            self.vol_smooth += (vol - self.vol_smooth) * 0.3
            
            # Animation Logic
            self.angle += 0.1
            
            # 1. Update Core (White)
            core_size = int(40 + (self.vol_smooth * 30))
            self.core.set_size_request(core_size, core_size)
            
            # 2. Update Waves (Fluid morphing)
            # We change the border-radius dynamically to simulate "waves"
            r1 = int(40 + math.sin(self.angle) * 10)
            r2 = int(60 + math.cos(self.angle) * 15)
            r3 = int(50 + math.sin(self.angle * 0.5) * 20)
            
            # Use size to simulate growth
            red_size = int(120 + (self.vol_smooth * 100))
            blue_size = int(140 + (self.vol_smooth * 120))
            
            self.wave_red.set_size_request(red_size, red_size)
            self.wave_blue.set_size_request(blue_size, blue_size)
            
            # Apply dynamic rotation/wobble via CSS (minimal impact)
            # Since updating CSS data every frame is heavy, we'll stick to size/scaling
            # and let the cubic-bezier transitions handle the rest.
            
        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop()
        self.wave_blue.set_visible(False)
        self.wave_red.set_visible(False)
        self.core.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.pro.orb")
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
