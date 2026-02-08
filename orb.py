#!/usr/bin/env python3
"""
Dictate Pro Overlay - Strict Uniform Design
- ALL layers (Core, Colors, Patches) are forced to the EXACT same pixel size.
- Core is moved to a peer layer to ensure identical rendering.
- Central White Patches: Constrained to 40-60% area.
"""

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

LOG_FILE = "/tmp/dictate_debug.log"

def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.ctime()}: [Orb] {msg}\n")
    except Exception: pass

class AudioMonitor:
    def __init__(self):
        self.current_volume = 0
        self.running = True
        self.p = None
        self.stream = None
        try:
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(format=pyaudio.paInt16,
                                      channels=1,
                                      rate=16000,
                                      input=True,
                                      frames_per_buffer=1024)
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
        except Exception as e:
            log(f"Mic error: {e}")

    def _monitor_loop(self):
        while self.running and self.stream:
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
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception: pass
        if self.p: self.p.terminate()

class RecordingOrb(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Dictate Pro")
        self.set_default_size(120, 120)
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.state = 'recording'
        self.vol_smooth = 0
        self.entrance_scale = 0.0
        self.layer_smooth = [0.0, 0.0, 0.0]
        self.angles = [random.randint(0, 360) for _ in range(6)]
        self.base_speeds = [0.0] * 6
        self.target_speeds = [0.0] * 6
        self.gradient_stops = [10.0] * 3
        
        self.setup_ui()
        self.monitor = AudioMonitor()
        self.randomize_parameters()
        
        GLib.timeout_add(20, self.update_ui)
        GLib.timeout_add(800, self.randomize_parameters) 

    def setup_ui(self):
        self.overlay = Gtk.Overlay()
        
        # Transparent base to hold everything
        self.base = Gtk.Box()
        self.base.set_size_request(120, 120)
        self.overlay.set_child(self.base)

        # All layers as Peer Overlays for identical centering and sizing
        self.core = Gtk.Box(name="white-core")
        self.border_glow = Gtk.Box(name="border-glow")
        self.red = Gtk.Box(name="plasma-red")
        self.purple = Gtk.Box(name="plasma-purple")
        self.blue = Gtk.Box(name="plasma-blue")
        self.white_patch1 = Gtk.Box(name="white-patch-1")
        self.white_patch2 = Gtk.Box(name="white-patch-2")
        self.spinner_ring = Gtk.Box(name="spinner-ring")
        self.spinner_ring.set_visible(False)

        for w in [self.core, self.border_glow, self.red, self.purple, self.blue, self.white_patch1, self.white_patch2, self.spinner_ring]:
            w.set_halign(Gtk.Align.CENTER)
            w.set_valign(Gtk.Align.CENTER)
            # Ensure no margins/padding interfere with size
            w.set_margin_start(0)
            w.set_margin_end(0)
            w.set_margin_top(0)
            w.set_margin_bottom(0)
            self.overlay.add_overlay(w)
        
        self.set_child(self.overlay)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window { background-color: transparent; }
            #white-core {
                background: radial-gradient(circle, #ffffff 30%, #f2f2f7 100%);
                border-radius: 50%;
                box-shadow: inset 0 0 10px rgba(0,0,0,0.02);
            }
            #border-glow {
                border-radius: 50%;
                filter: blur(10px);
                opacity: 0.3;
            }
            #spinner-ring {
                border-radius: 50%;
                border: 4px solid transparent;
                border-top: 4px solid #007aff;
                filter: blur(1px);
            }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.dynamic_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.dynamic_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def randomize_parameters(self):
        self.target_speeds = [random.uniform(0.3, 1.5) * random.choice([-1, 1]) for _ in range(6)]
        return True

    def update_ui(self):
        if self.entrance_scale < 1.0:
            self.entrance_scale += (1.0 - self.entrance_scale) * 0.15
            if self.entrance_scale > 0.99: self.entrance_scale = 1.0

        # FORCE STRICT IDENTICAL SIZE
        STRICT_SIZE = int(80 * self.entrance_scale)
        
        if self.state == 'recording':
            vol = self.monitor.current_volume
            vol_active = vol if vol > 0.45 else 0
            self.vol_smooth += (vol_active - self.vol_smooth) * 0.2
            speed_boost = 1.0 + (self.vol_smooth * 8.0)
            
            for i in range(6):
                self.base_speeds[i] += (self.target_speeds[i] - self.base_speeds[i]) * 0.1
                self.angles[i] = (self.angles[i] + (self.base_speeds[i] * speed_boost)) % 360
                if i < 3:
                    self.gradient_stops[i] += ( (10.0 + (vol_active if i==0 else self.vol_smooth) * 40.0) - self.gradient_stops[i] ) * 0.2

            # Apply EXACTLY THE SAME SIZE to all widgets
            for w in [self.core, self.border_glow, self.red, self.purple, self.blue, self.white_patch1, self.white_patch2]:
                w.set_size_request(STRICT_SIZE, STRICT_SIZE)

            def get_grad(angle, color_rgba, stop):
                mid = stop * 0.6
                return f"linear-gradient({angle}deg, {color_rgba} 0%, {color_rgba.replace('0.8', '0.2')} {mid}%, transparent {stop}%)"

            css = f"""
                #border-glow {{ background: conic-gradient(from {self.angles[3]}deg, #ff3b30, #5856d6, #007aff, #ff3b30); }}
                #plasma-red {{ background: {get_grad(self.angles[0], 'rgba(255, 59, 48, 0.7)', self.gradient_stops[0])}; border-radius: 50%; filter: blur(1px); }}
                #plasma-purple {{ background: {get_grad(self.angles[1], 'rgba(175, 82, 222, 0.6)', self.gradient_stops[1])}; border-radius: 50%; filter: blur(2px); }}
                #plasma-blue {{ background: {get_grad(self.angles[2], 'rgba(0, 122, 255, 0.5)', self.gradient_stops[2])}; border-radius: 50%; filter: blur(3px); }}
                #white-patch-1 {{ background: radial-gradient(circle at center, rgba(255,255,255,0.8) 0%, transparent 25%); border-radius: 50%; }}
                #white-patch-2 {{ background: radial-gradient(circle at {40 + math.sin(self.angles[4])*10}% {50 + math.cos(self.angles[5])*10}%, rgba(255,255,255,0.6) 0%, transparent 20%); border-radius: 50%; }}
            """.encode()
            self.dynamic_css.load_from_data(css)
            
        elif self.state == 'loading':
            self.angles[3] = (self.angles[3] + 15) % 360
            # Even in loading, keep the ring size consistent with the STRICT_SIZE logic
            self.spinner_ring.set_size_request(STRICT_SIZE, STRICT_SIZE)
            css = f"#spinner-ring {{ transform: rotate({self.angles[3]}deg); }}".encode()
            self.dynamic_css.load_from_data(css)

        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop()
        for w in [self.red, self.purple, self.blue, self.border_glow, self.white_patch1, self.white_patch2]: w.set_visible(False)
        self.spinner_ring.set_visible(True)

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.master.v5.orb")
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
