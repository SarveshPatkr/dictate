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
        
        self.state = 'recording'
        self.scale = 1.0
        
        # 1. Container
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.set_halign(Gtk.Align.CENTER)
        self.main_box.set_valign(Gtk.Align.CENTER)
        
        # 2. THE ORB / SPINNER Widget
        # We use a Stack to switch between them
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        
        # Red Orb
        self.orb = Gtk.Box()
        self.orb.add_css_class("orb")
        self.orb.set_size_request(50, 50)
        
        # Blue Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.add_css_class("spinner")
        self.spinner.set_size_request(50, 50)
        
        self.stack.add_named(self.orb, "orb")
        self.stack.add_named(self.spinner, "spinner")
        
        self.main_box.append(self.stack)
        self.set_child(self.main_box)

        # 3. APPLE STYLE CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window { 
                background-color: transparent; 
            }
            .orb {
                background: radial-gradient(circle at 30% 30%, #ff5e57, #ff3b30);
                border-radius: 50%;
                box-shadow: 0 0 20px rgba(255, 59, 48, 0.6), 
                            inset 0 0 10px rgba(255, 255, 255, 0.2);
                transition: min-width 0.1s ease-out, min-height 0.1s ease-out;
            }
            .spinner {
                color: #007aff;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.monitor = AudioMonitor()
        GLib.timeout_add(30, self.update_ui)

    def update_ui(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            # Noise Gate
            if vol < 0.48:
                target_scale = 1.0
            else:
                target_scale = 1.0 + (vol * 1.5)
            
            # Easing
            self.scale += (target_scale - self.scale) * 0.3
            size = int(50 * self.scale)
            self.orb.set_size_request(size, size)
        return True

    def start_loading(self):
        log("Transitioning to Spinner...")
        self.state = 'loading'
        self.monitor.stop()
        self.stack.set_visible_child_name("spinner")
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
