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
        self.set_default_size(80, 80)
        self.set_decorated(False)
        self.set_focusable(False)
        
        # UI Stack to switch between Orb and Spinner
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(300)
        
        # 1. THE RED ORB
        self.orb_box = Gtk.Box()
        self.orb_box.set_halign(Gtk.Align.CENTER)
        self.orb_box.set_valign(Gtk.Align.CENTER)
        self.orb = Gtk.Box()
        self.orb.add_css_class("red-orb")
        self.orb.set_size_request(40, 40)
        self.orb_box.append(self.orb)
        
        # 2. THE SPINNER
        self.spinner_box = Gtk.Box()
        self.spinner_box.set_halign(Gtk.Align.CENTER)
        self.spinner_box.set_valign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(40, 40)
        self.spinner_box.append(self.spinner)
        
        self.stack.add_named(self.orb_box, "orb")
        self.stack.add_named(self.spinner_box, "spinner")
        self.set_child(self.stack)

        # CSS for Red Orb
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
        GLib.timeout_add(30, self.update_orb)

    def update_orb(self):
        if self.stack.get_visible_child_name() == "orb":
            vol = self.monitor.get_volume()
            scale = 1.0 + (vol * 1.0) if vol > 0.45 else 1.0
            size = int(40 * scale)
            self.orb.set_size_request(size, size)
        return True

    def start_loading(self):
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
        if self.win: self.win.start_loading()
        return True

    def on_sigterm(self):
        if self.win: self.win.monitor.stop()
        self.quit()
        return False

if __name__ == "__main__":
    app = OrbApp()
    app.run(None)
