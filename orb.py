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
        self.set_default_size(200, 200)
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.state = 'recording'
        
        self.overlay = Gtk.Overlay()
        
        # We'll use 4 "Wave" layers
        self.waves = []
        for i in range(4):
            w = Gtk.Box()
            w.add_css_class(f"wave-{i}")
            w.set_halign(Gtk.Align.CENTER)
            w.set_valign(Gtk.Align.CENTER)
            self.overlay.add_overlay(w)
            self.waves.append({"widget": w, "size": 0, "active": False, "color": "blue"})

        # The White Core
        self.core = Gtk.Box()
        self.core.add_css_class("white-core")
        self.core.set_halign(Gtk.Align.CENTER)
        self.core.set_valign(Gtk.Align.CENTER)
        self.core.set_size_request(40, 40)
        self.overlay.set_child(self.core)
        
        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(50, 50)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)
        self.overlay.add_overlay(self.spinner)

        self.set_child(self.overlay)

        # CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window { background-color: transparent; }
            .white-core {
                background: radial-gradient(circle at 30% 30%, #ffffff, #e5e5ea);
                border-radius: 50%;
                box-shadow: 0 0 15px rgba(255, 255, 255, 0.8);
            }
            .wave-0, .wave-1, .wave-2, .wave-3 {
                border-radius: 50%;
                border: 2px solid transparent;
            }
            .blue-wave { border-color: rgba(0, 122, 255, 0.6); }
            .red-wave { border-color: rgba(255, 59, 48, 0.6); }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.monitor = AudioMonitor()
        self.last_spawn = 0
        GLib.timeout_add(30, self.update_ui)

    def update_ui(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            # Noise gate
            vol = vol if vol > 0.45 else 0
            
            # 1. Update Core
            core_size = int(40 + (vol * 30))
            self.core.set_size_request(core_size, core_size)
            
            # 2. Spawn Waves
            now = time.time()
            if vol > 0.5 and (now - self.last_spawn) > 0.2:
                # Find an inactive wave
                for w in self.waves:
                    if not w["active"]:
                        w["active"] = True
                        w["size"] = 40
                        w["color"] = "red" if vol > 0.7 else "blue"
                        w["widget"].set_visible(True)
                        w["widget"].set_css_classes([f"wave-{self.waves.index(w)}", f"{w['color']}-wave"])
                        self.last_spawn = now
                        break
            
            # 3. Animate Waves
            for w in self.waves:
                if w["active"]:
                    w["size"] += 5
                    opacity = max(0, 1.0 - (w["size"] / 180.0))
                    w["widget"].set_size_request(int(w["size"]), int(w["size"]))
                    w["widget"].set_opacity(opacity)
                    if opacity <= 0:
                        w["active"] = False
                        w["widget"].set_visible(False)
                        
        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop()
        self.core.set_visible(False)
        for w in self.waves: w["widget"].set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.waves.orb")
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
