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
                shorts = struct.unpack(f\"{len(data)//2}h\", data)
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
        self.set_title(\"Dictate Overlay\")
        self.set_default_size(300, 300)
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.state = 'recording'
        self.vol_smooth = 0
        self.angle = 0
        
        # We'll use 5 layers to create the \"Plasma Wave\" look from your screenshot
        self.overlay = Gtk.Overlay()
        
        # Layer 1: Deep Blue Aura
        self.aura = Gtk.Box()
        self.aura.add_css_class(\"plasma-aura\")
        
        # Layer 2: Purple Wave
        self.wave_purple = Gtk.Box()
        self.wave_purple.add_css_class(\"wave-purple\")
        
        # Layer 3: Cyan/Blue Wave
        self.wave_cyan = Gtk.Box()
        self.wave_cyan.add_css_class(\"wave-cyan\")
        
        # Layer 4: Red/Magenta Wave
        self.wave_red = Gtk.Box()
        self.wave_red.add_css_class(\"wave-red\")
        
        # Layer 5: The White Pearl Core
        self.core = Gtk.Box()
        self.core.add_css_class(\"core-white\")
        self.core.set_size_request(45, 45)
        
        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(60, 60)
        self.spinner.set_visible(False)

        # Build the stack
        for w in [self.aura, self.wave_purple, self.wave_cyan, self.wave_red, self.core, self.spinner]:
            w.set_halign(Gtk.Align.CENTER)
            w.set_valign(Gtk.Align.CENTER)
            if w == self.aura:
                self.overlay.set_child(w)
            else:
                self.overlay.add_overlay(w)
        
        self.set_child(self.overlay)

        # --- THE PLASMA CSS ENGINE ---
        self.css_provider = Gtk.CssProvider()
        self.apply_plasma_css()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.monitor = AudioMonitor()
        GLib.timeout_add(30, self.update_ui)

    def apply_plasma_css(self, brs=None):
        brs = brs or [\"50% \"] * 4
        css = f\"\"\"
            window {{ background-color: transparent; }}
            .plasma-aura {{
                background: radial-gradient(circle, rgba(0, 122, 255, 0.3), transparent 70%);
                min-width: 220px; min-height: 220px;
                border-radius: 50%;
            }}
            .wave-purple {{
                background: linear-gradient(45deg, rgba(88, 86, 214, 0.6), rgba(175, 82, 222, 0.4));
                min-width: 160px; min-height: 160px;
                border-radius: {brs[0]};
                filter: blur(8px);
            }}
            .wave-cyan {{
                background: linear-gradient(-45deg, rgba(90, 200, 250, 0.7), rgba(0, 122, 255, 0.3));
                min-width: 140px; min-height: 140px;
                border-radius: {brs[1]};
                filter: blur(5px);
            }}
            .wave-red {{
                background: linear-gradient(180deg, rgba(255, 59, 48, 0.8), rgba(255, 149, 0, 0.4));
                min-width: 110px; min-height: 110px;
                border-radius: {brs[2]};
                filter: blur(3px);
            }}
            .core-white {{
                background: radial-gradient(circle at 30% 30%, #ffffff, #f2f2f7);
                border-radius: 50%;
                box-shadow: 0 0 20px rgba(255, 255, 255, 0.9), inset 0 0 5px rgba(0,0,0,0.1);
            }}
            .spinner {{ color: #007aff; }}
        \"\"\".encode()
        self.css_provider.load_from_data(css)

    def update_ui(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            vol = vol if vol > 0.45 else 0
            self.vol_smooth += (vol - self.vol_smooth) * 0.2
            self.angle += 0.15
            
            # Generate random \"Wavy\" border radii for that plasma texture
            def get_br(seed_offset):
                a = self.angle + seed_offset
                v = self.vol_smooth * 30
                r1 = int(40 + v + math.sin(a) * 15)
                r2 = int(60 + v + math.cos(a*1.2) * 15)
                r3 = int(50 + v + math.sin(a*0.8) * 20)
                r4 = int(45 + v + math.cos(a*1.5) * 10)
                return f\"{r1}% {r2}% {r3}% {r4}% / {r4}% {r3}% {r2}% {r1}%\"

            # Update the waves morphing
            self.apply_plasma_css([get_br(0), get_br(2), get_br(4)])
            
            # Scale Core
            c_size = int(45 + (self.vol_smooth * 25))
            self.core.set_size_request(c_size, c_size)
            
            # Scale Waves
            self.wave_purple.set_size_request(int(160 + vol*100), int(160 + vol*100))
            self.wave_cyan.set_size_request(int(140 + vol*80), int(140 + vol*80))
            self.wave_red.set_size_request(int(110 + vol*60), int(110 + vol*60))
            
        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop()
        for w in [self.aura, self.wave_purple, self.wave_cyan, self.wave_red, self.core]:
            w.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=\"com.openclaw.dictate.plasma.orb\")
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

if __name__ == \"__main__\":
    app = OrbApp()
    app.run(None)
