#!/usr/bin/env python3
"""
Dictate Pro Overlay - Gaussian Plasma Edition v3
- All layers 80px fixed size.
- EXTREME Gaussian Blur for ultra-soft glow.
- Randomized Voice Reactivity.
- Enhanced White Sparkles (more frequent/brighter).
- 15% Fringe Zone.
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
    """Log messages to a debug file for easier troubleshooting."""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.ctime()}: [Orb] {msg}\n")
    except Exception:
        pass

class AudioMonitor:
    """Analyzes microphone input in a background thread to provide real-time volume levels."""
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
        """Calculates RMS volume from raw audio buffers."""
        while self.running and self.stream:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                shorts = struct.unpack(f"{len(data)//2}h", data)
                sum_squares = sum(s*s for s in shorts)
                rms = math.sqrt(sum_squares / (len(shorts) or 1))
                level = math.log(rms + 1, 10) / 4.5 if rms > 0 else 0
                self.current_volume = min(max(level, 0), 1.0)
            except Exception:
                pass
                
    def stop(self):
        """Cleanly releases audio resources."""
        self.running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
        if self.p:
            self.p.terminate()

class RecordingOrb(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Dictate Pro")
        self.set_default_size(80, 80)
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.state = 'recording'
        self.vol_smooth = 0
        self.entrance_scale = 0.0
        self.layer_smooth = [0.0, 0.0, 0.0]
        # Randomized lags for voice reactivity
        self.lags = [0.25, 0.12, 0.07]
        self.angles = [random.randint(0, 360) for _ in range(3)]
        self.base_speeds = [0.0] * 3
        self.target_speeds = [0.0] * 3
        self.gradient_stops = [10.0] * 3
        
        # Sparkle state
        self.sparkle_chance = [0.0, 0.0, 0.0]
        
        self.setup_ui()
        self.monitor = AudioMonitor()
        self.randomize_parameters()
        
        GLib.timeout_add(30, self.update_ui)
        GLib.timeout_add(800, self.randomize_parameters) 

    def setup_ui(self):
        self.overlay = Gtk.Overlay()
        self.core = Gtk.Box(name="white-core")
        self.red = Gtk.Box(name="plasma-red")
        self.purple = Gtk.Box(name="plasma-purple")
        self.blue = Gtk.Box(name="plasma-blue")
        self.spinner = Gtk.Spinner(name="loading-spinner")
        self.spinner.set_size_request(40, 40)
        self.spinner.set_visible(False)

        BALL_SIZE = 80
        for w in [self.core, self.red, self.purple, self.blue, self.spinner]:
            w.set_size_request(BALL_SIZE, BALL_SIZE)
            w.set_halign(Gtk.Align.CENTER)
            w.set_valign(Gtk.Align.CENTER)

        # Stacking order changed: Blue -> Red -> Purple
        self.overlay.set_child(self.core)
        self.overlay.add_overlay(self.blue)
        self.overlay.add_overlay(self.red)
        self.overlay.add_overlay(self.purple)
        self.overlay.add_overlay(self.spinner)
        
        self.set_child(self.overlay)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window { background-color: transparent; }
            #white-core {
                background-color: #ffffff;
                border-radius: 50%;
                box-shadow: 0 0 5px rgba(0,0,0,0.05);
            }
            #loading-spinner { color: #007aff; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.dynamic_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.dynamic_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def randomize_parameters(self):
        # Random speeds
        self.target_speeds = [random.uniform(0.2, 1.0) * random.choice([-1, 1]) for _ in range(3)]
        # Randomize which color is most reactive
        random.shuffle(self.lags)
        # Higher chance for white sparkles (shimmer)
        self.sparkle_chance = [random.uniform(0.4, 1.0) for _ in range(3)]
        return True

    def update_ui(self):
        if self.entrance_scale < 1.0:
            self.entrance_scale += (1.0 - self.entrance_scale) * 0.15
            if self.entrance_scale > 0.99: self.entrance_scale = 1.0

        BALL_SIZE = int(80 * self.entrance_scale)
        
        if self.state == 'recording':
            vol = self.monitor.current_volume
            vol_active = vol if vol > 0.45 else 0
            self.vol_smooth += (vol_active - self.vol_smooth) * 0.2
            speed_boost = 1.0 + (self.vol_smooth * 10.0)
            
            for i in range(3):
                self.layer_smooth[i] += (vol_active - self.layer_smooth[i]) * self.lags[i]
                self.base_speeds[i] += (self.target_speeds[i] - self.base_speeds[i]) * 0.1
                self.angles[i] = (self.angles[i] + (self.base_speeds[i] * speed_boost)) % 360
                
                # Reduce orange (index 0) reactivity
                reactivity = 25.0 if i == 0 else 35.0
                target_stop = 10.0 + (self.layer_smooth[i] * reactivity)
                self.gradient_stops[i] += (target_stop - self.gradient_stops[i]) * 0.2

            for w in [self.core, self.red, self.purple, self.blue]:
                w.set_size_request(BALL_SIZE, BALL_SIZE)

            def get_grad(angle, color_rgba, stop, idx):
                fringe_color = color_rgba.replace(', 0.7', ', 0.1').replace(', 0.6', ', 0.1').replace(', 0.5', ', 0.05').replace('0.8', '0.1')
                fringe_stop = stop + 15.0
                
                sparkle = ""
                if self.sparkle_chance[idx] > 0.55:
                    sparkle = "rgba(255,255,255,1.0) 0%, rgba(255,255,255,0.5) 10%, rgba(255,255,255,0) 20%,"

                return f"linear-gradient({angle}deg, {sparkle} {color_rgba} 0%, {color_rgba} {stop}%, {fringe_color} {stop}%, {fringe_color} {fringe_stop}%, transparent {fringe_stop}%)"

            css = f"""
                window {{ background-color: transparent; }}
                #plasma-red {{ background: {get_grad(self.angles[0], 'rgba(255, 59, 48, 0.8)', self.gradient_stops[0], 0)}; border-radius: 50%; filter: blur(6px); }}
                #plasma-purple {{ background: {get_grad(self.angles[1], 'rgba(175, 82, 222, 0.7)', self.gradient_stops[1], 1)}; border-radius: 50%; filter: blur(10px); }}
                #plasma-blue {{ background: {get_grad(self.angles[2], 'rgba(0, 122, 255, 0.6)', self.gradient_stops[2], 2)}; border-radius: 50%; filter: blur(14px); }}
            """.encode()
            self.dynamic_css.load_from_data(css)
            
        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop()
        for w in [self.red, self.purple, self.blue, self.core]: w.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.gaussian.v3.zindex.orb")
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
