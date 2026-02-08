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
        except Exception as e:
            log(f"Mic error: {e}")
            self.p = None
            
        self.current_volume = 0
        self.running = True
        
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def _monitor_loop(self):
        while self.running:
            if not self.p:
                time.sleep(1)
                continue
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
            try:
                self.stream.stop_stream()
                self.stream.close()
                self.p.terminate()
            except:
                pass

class RecordingOrb(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Dictate Overlay")
        self.set_default_size(250, 100)
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.state = 'recording'
        
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
        else:
            css = b"""
                window { background-color: transparent; }
                .orb {
                    background-color: #007aff;
                    border-radius: 5px;
                    min-width: 200px;
                    min-height: 10px;
                    box-shadow: 0 0 10px rgba(0, 122, 255, 0.4);
                    transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
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
            pulse = 200 + (math.sin(time.time() * 8) * 15)
            self.orb.set_size_request(int(pulse), 10)
        return True

    def start_loading(self):
        log("Transitioning to LOADING state...")
        self.state = 'loading'
        self.monitor.stop()
        self.apply_css()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.orb")
        self.win = None

    def do_activate(self):
        self.win = RecordingOrb(self)
        self.win.present()
        
        # Set up signal handlers within GLib loop
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.on_sigusr1)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.on_sigterm)

    def on_sigusr1(self):
        log("Received SIGUSR1")
        if self.win:
            self.win.start_loading()
        return True

    def on_sigterm(self):
        log("Received SIGTERM, shutting down.")
        if self.win:
            self.win.monitor.stop()
        self.quit()
        return False

if __name__ == "__main__":
    app = OrbApp()
    app.run(None)
