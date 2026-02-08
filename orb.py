#!/usr/bin/env python3
"""
Dictate Pro Overlay
An audio-reactive visualizer for the Dictate Linux tool.
Uses GTK4 for the UI and PyAudio for real-time volume analysis.
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
            log(f"Mic initialization error: {e}")

    def _monitor_loop(self):
        """Calculates RMS volume from raw audio buffers."""
        while self.running and self.stream:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                # Manually calculate RMS volume from 16-bit PCM data
                shorts = struct.unpack(f"{len(data)//2}h", data)
                sum_squares = sum(s*s for s in shorts)
                rms = math.sqrt(sum_squares / (len(shorts) or 1))
                # Map to a logarithmic level (0.0 to 1.0)
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
    """Main UI window featuring a pulsing orb and transition to a loading spinner."""
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Dictate Pro")
        self.set_default_size(100, 100)
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.state = 'recording'
        self.vol_smooth = 0
        self.angles = [random.randint(0, 360) for _ in range(3)]
        self.base_speeds = [0.0] * 3
        self.target_speeds = [0.0] * 3
        self.gradient_stops = [30.0] * 3
        self.target_stops = [30.0] * 3
        
        # Randomized expansion multipliers for each layer
        self.exp_multipliers = [1.0, 1.0, 1.0]
        self.target_multipliers = [1.0, 1.0, 1.0]

        self.setup_ui()
        self.monitor = AudioMonitor()
        
        # Initialize randomization and begin animation loops
        self.randomize_parameters()
        GLib.timeout_add(30, self.update_ui)
        GLib.timeout_add(500, self.randomize_parameters) 

    def setup_ui(self):
        """Builds the visual layers using GTK Overlay."""
        self.overlay = Gtk.Overlay()
        self.core = Gtk.Box(name="white-core")
        self.red = Gtk.Box(name="plasma-red")
        self.purple = Gtk.Box(name="plasma-purple")
        self.blue = Gtk.Box(name="plasma-blue")
        self.spinner = Gtk.Spinner(name="loading-spinner")
        self.spinner.set_size_request(40, 40)
        self.spinner.set_visible(False)

        # Stack layers: Core (bottom) -> Colors -> Spinner (top)
        self.overlay.set_child(self.core)
        for layer in [self.red, self.purple, self.blue, self.spinner]:
            layer.set_halign(Gtk.Align.CENTER)
            layer.set_valign(Gtk.Align.CENTER)
            self.overlay.add_overlay(layer)
        
        self.set_child(self.overlay)

        # Style with CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window { background-color: transparent; }
            #white-core {
                background: radial-gradient(circle at 30% 30%, #ffffff, #f2f2f7);
                border-radius: 50%;
                box-shadow: 0 0 10px rgba(255, 255, 255, 0.4);
            }
            #loading-spinner { color: #007aff; }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        # Dedicated provider for dynamic gradient layers
        self.dynamic_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.dynamic_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def randomize_parameters(self):
        """Periodically updates target speeds, gradient lengths, and expansion intensities."""
        self.target_speeds = [random.uniform(0.3, 1.5) * random.choice([-1, 1]) for _ in range(3)]
        self.target_stops = [random.uniform(10.0, 50.0) for _ in range(3)]
        # Randomize how much each layer reacts to voice (from 0.5x to 2.0x intensity)
        self.target_multipliers = [random.uniform(0.5, 2.0) for _ in range(3)]
        return True

    def update_ui(self):
        """Drives the animation frame by frame."""
        if self.state != 'recording':
            return True

        vol = self.monitor.current_volume
        vol_active = vol if vol > 0.45 else 0
        self.vol_smooth += (vol_active - self.vol_smooth) * 0.2
        
        # Calculate physics: Speed boost and interpolation
        speed_boost = 1.0 + (self.vol_smooth * 10.0)
        for i in range(3):
            self.base_speeds[i] += (self.target_speeds[i] - self.base_speeds[i]) * 0.15
            self.angles[i] = (self.angles[i] + (self.base_speeds[i] * speed_boost)) % 360
            self.gradient_stops[i] += (self.target_stops[i] - self.gradient_stops[i]) * 0.15
            self.exp_multipliers[i] += (self.target_multipliers[i] - self.exp_multipliers[i]) * 0.1
        
        # Update sizes: Pearl is base, colors have randomized expansion intensity
        base_size = int(45 + (self.vol_smooth * 40))
        self.core.set_size_request(base_size, base_size)
        
        # Individual layer expansion (Base + Randomized Voice Reaction)
        s_red = int(45 + (self.vol_smooth * 40 * self.exp_multipliers[0]))
        s_purple = int(45 + (self.vol_smooth * 40 * self.exp_multipliers[1]))
        s_blue = int(45 + (self.vol_smooth * 40 * self.exp_multipliers[2])) + 1
        
        self.red.set_size_request(s_red, s_red)
        self.purple.set_size_request(s_purple, s_purple)
        self.blue.set_size_request(s_blue, s_blue)

        # Update dynamic gradients
        css = f"""
            #plasma-red {{ background: linear-gradient({self.angles[0]}deg, rgba(255, 59, 48, 0.8) 0%, rgba(255, 59, 48, 0.3) {self.gradient_stops[0]/2}%, transparent {self.gradient_stops[0]}%); border-radius: 50%; }}
            #plasma-purple {{ background: linear-gradient({self.angles[1]}deg, rgba(175, 82, 222, 0.7) 0%, rgba(175, 82, 222, 0.2) {self.gradient_stops[1]/2}%, transparent {self.gradient_stops[1]}%); border-radius: 50%; }}
            #plasma-blue {{ background: linear-gradient({self.angles[2]}deg, rgba(0, 122, 255, 0.6) 0%, rgba(0, 122, 255, 0.2) {self.gradient_stops[2]/2}%, transparent {self.gradient_stops[2]}%); border-radius: 50%; }}
        """.encode()
        self.dynamic_css.load_from_data(css)
        return True

    def start_loading(self):
        """Triggers the transition to the processing state."""
        log("Transitioning to processing state.")
        self.state = 'loading'
        self.monitor.stop()
        for w in [self.core, self.red, self.purple, self.blue]:
            w.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

class OrbApp(Gtk.Application):
    """Gtk Application wrapper handling lifecycle and system signals."""
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.pro")
        self.win = None

    def do_activate(self):
        self.win = RecordingOrb(self)
        self.win.present()
        # Handle Linux signals within the GLib main loop for safety
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
