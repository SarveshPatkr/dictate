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
        self.angle = 0
        self.vol_smooth = 0
        
        # We use three layers of blobs to create the "Wrapping Wave" effect
        self.overlay = Gtk.Overlay()
        
        # Layer 1: Blue Fluid Blob
        self.blob_blue = Gtk.Box()
        self.blob_blue.add_css_class("blob-blue")
        self.blob_blue.set_halign(Gtk.Align.CENTER)
        self.blob_blue.set_valign(Gtk.Align.CENTER)
        
        # Layer 2: Red Fluid Blob
        self.blob_red = Gtk.Box()
        self.blob_red.add_css_class("blob-red")
        self.blob_red.set_halign(Gtk.Align.CENTER)
        self.blob_red.set_valign(Gtk.Align.CENTER)
        
        # Layer 3: White Core
        self.core = Gtk.Box()
        self.core.add_css_class("white-core")
        self.core.set_halign(Gtk.Align.CENTER)
        self.core.set_valign(Gtk.Align.CENTER)
        self.core.set_size_request(50, 50)
        
        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(60, 60)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)

        self.overlay.set_child(self.blob_blue)
        self.overlay.add_overlay(self.blob_red)
        self.overlay.add_overlay(self.core)
        self.overlay.add_overlay(self.spinner)
        self.set_child(self.overlay)

        # CSS - Initial Setup
        self.css_provider = Gtk.CssProvider()
        self.update_css()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.monitor = AudioMonitor()
        GLib.timeout_add(40, self.update_ui)

    def update_css(self, br_blue=None, br_red=None):
        br_blue = br_blue or "50% 50% 50% 50% / 50% 50% 50% 50%"
        br_red = br_red or "50% 50% 50% 50% / 50% 50% 50% 50%"
        
        css = f"""
            window {{ background-color: transparent; }}
            .white-core {{
                background: radial-gradient(circle at 30% 30%, #ffffff, #f2f2f7);
                border-radius: 50%;
                box-shadow: 0 0 20px rgba(255, 255, 255, 0.8);
            }}
            .blob-blue {{
                background: linear-gradient(45deg, #007aff, #5856d6);
                opacity: 0.5;
                border-radius: {br_blue};
                transition: all 0.4s ease-in-out;
            }}
            .blob-red {{
                background: linear-gradient(-45deg, #ff3b30, #ff9500);
                opacity: 0.6;
                border-radius: {br_red};
                transition: all 0.3s ease-in-out;
            }}
            .spinner {{ color: #007aff; }}
        """.encode()
        self.css_provider.load_from_data(css)

    def update_ui(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            vol = vol if vol > 0.45 else 0
            self.vol_smooth += (vol - self.vol_smooth) * 0.2
            self.angle += 0.2
            
            # Create "Perimeter Waves" by randomizing border-radius
            # This makes the circle look like liquid wrapping around the center
            def gen_br():
                v = self.vol_smooth * 40
                r = lambda: random.randint(int(40-v), int(60+v))
                return f"{r()}% {r()}% {r()}% {r()}% / {r()}% {r()}% {r()}% {r()}%"

            # Dynamic Sizes
            core_size = int(50 + (self.vol_smooth * 30))
            red_size = int(110 + (self.vol_smooth * 80))
            blue_size = int(130 + (self.vol_smooth * 100))
            
            self.core.set_size_request(core_size, core_size)
            self.blob_red.set_size_request(red_size, red_size)
            self.blob_blue.set_size_request(blue_size, blue_size)
            
            # Update the perimeter waves (morphing)
            self.update_css(gen_br(), gen_br())
            
        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop()
        self.blob_blue.set_visible(False)
        self.blob_red.set_visible(False)
        self.core.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.blob.orb")
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
