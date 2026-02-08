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

LOG_FILE = "/tmp/dictate_debug.log"

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.ctime()}: [Orb] {msg}\n")

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
        self.set_default_size(150, 150)
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.set_halign(Gtk.Align.CENTER)
        self.main_box.set_valign(Gtk.Align.CENTER)
        
        # 1. THE RED ORB
        self.orb = Gtk.Box()
        self.orb.add_css_class("red-orb")
        self.orb.set_size_request(40, 40)
        
        # 2. THE SPINNER (hidden initially)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(40, 40)
        self.spinner.set_visible(False)
        
        self.main_box.append(self.orb)
        self.main_box.append(self.spinner)
        self.set_child(self.main_box)

        # CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window { background-color: transparent; }
            .red-orb {
                background-color: #ff3b30;
                border-radius: 50%;
                box-shadow: 0 0 15px rgba(255, 59, 48, 0.6);
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.monitor = AudioMonitor()
        self.loading = False
        GLib.timeout_add(30, self.update_ui)

    def update_ui(self):
        if not self.loading:
            vol = self.monitor.get_volume()
            # Lower threshold to 0.3 for better sensitivity
            scale = 1.0 + (vol * 2.0) if vol > 0.3 else 1.0
            size = int(40 * scale)
            self.orb.set_size_request(size, size)
        return True

    def start_loading(self):
        log("start_loading called")
        self.loading = True
        self.monitor.stop()
        self.orb.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.orb")
        self.win = None

    def do_activate(self):
        self.win = RecordingOrb(self)
        self.win.present()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.on_sigusr1)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.on_sigterm)

    def on_sigusr1(self):
        log("SIGUSR1 received in App")
        if self.win:
            GLib.idle_add(self.win.start_loading)
        return True

    def on_sigterm(self):
        if self.win: self.win.monitor.stop()
        self.quit()
        return False

if __name__ == "__main__":
    app = OrbApp()
    app.run(None)
