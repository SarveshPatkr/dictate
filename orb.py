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
        self.scale1 = 1.0
        self.scale2 = 1.0
        self.scale3 = 1.0
        
        # Overlay allows us to stack multiple layers for the "Fluid" look
        self.overlay = Gtk.Overlay()
        
        # Layer 1: Outer Blue/Purple Glow
        self.orb_outer = Gtk.Box()
        self.orb_outer.add_css_class("orb-outer")
        self.orb_outer.set_halign(Gtk.Align.CENTER)
        self.orb_outer.set_valign(Gtk.Align.CENTER)
        
        # Layer 2: Mid Pink/Red Glow
        self.orb_mid = Gtk.Box()
        self.orb_mid.add_css_class("orb-mid")
        self.orb_mid.set_halign(Gtk.Align.CENTER)
        self.orb_mid.set_valign(Gtk.Align.CENTER)
        
        # Layer 3: Core Red
        self.orb_core = Gtk.Box()
        self.orb_core.add_css_class("orb-core")
        self.orb_core.set_halign(Gtk.Align.CENTER)
        self.orb_core.set_valign(Gtk.Align.CENTER)
        
        # Spinner Layer
        self.spinner = Gtk.Spinner()
        self.spinner.add_css_class("spinner")
        self.spinner.set_size_request(60, 60)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_visible(False)

        self.overlay.set_child(self.orb_outer)
        self.overlay.add_overlay(self.orb_mid)
        self.overlay.add_overlay(self.orb_core)
        self.overlay.add_overlay(self.spinner)
        
        self.set_child(self.overlay)

        # CSS for Layered Siri Look
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window { background-color: transparent; }
            .orb-outer {
                background: radial-gradient(circle, rgba(0, 122, 255, 0.4) 0%, rgba(0, 122, 255, 0) 70%);
                border-radius: 50%;
                min-width: 120px; min-height: 120px;
                transition: all 0.2s cubic-bezier(0.1, 0.7, 0.1, 1);
            }
            .orb-mid {
                background: radial-gradient(circle, rgba(255, 45, 85, 0.6) 0%, rgba(255, 45, 85, 0) 70%);
                border-radius: 50%;
                min-width: 90px; min-height: 90px;
                transition: all 0.15s cubic-bezier(0.1, 0.7, 0.1, 1);
            }
            .orb-core {
                background: radial-gradient(circle at 30% 30%, #ff5e57, #ff3b30);
                border-radius: 50%;
                min-width: 50px; min-height: 50px;
                box-shadow: inset 0 0 10px rgba(255, 255, 255, 0.3);
                transition: all 0.1s cubic-bezier(0.1, 0.7, 0.1, 1);
            }
            .spinner { color: #007aff; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.monitor = AudioMonitor()
        GLib.timeout_add(30, self.update_ui)

    def update_ui(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            
            # Independent scaling for "Fluid" effect
            # Threshold 0.45
            if vol < 0.45:
                t1, t2, t3 = 1.0, 1.0, 1.0
            else:
                # Core reacts most
                t3 = 1.0 + (vol * 1.8)
                # Mid reacts with lag
                t2 = 1.0 + (vol * 1.4)
                # Outer reacts least
                t1 = 1.0 + (vol * 1.0)
            
            # Easing
            self.scale1 += (t1 - self.scale1) * 0.2
            self.scale2 += (t2 - self.scale2) * 0.3
            self.scale3 += (t3 - self.scale3) * 0.4
            
            self.orb_outer.set_size_request(int(120 * self.scale1), int(120 * self.scale1))
            self.orb_mid.set_size_request(int(90 * self.scale2), int(90 * self.scale2))
            self.orb_core.set_size_request(int(50 * self.scale3), int(50 * self.scale3))
            
        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop()
        self.orb_outer.set_visible(False)
        self.orb_mid.set_visible(False)
        self.orb_core.set_visible(False)
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
        if self.win: GLib.idle_add(self.win.start_loading)
        return True

    def on_sigterm(self):
        if self.win: self.win.monitor.stop()
        self.quit()
        return False

if __name__ == "__main__":
    app = OrbApp()
    app.run(None)
