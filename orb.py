#!/usr/bin/env python3
import sys
import signal
import gi
import math
import struct
import threading
import pyaudio
import time
import cairo

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
        self.set_default_size(200, 200) # Large enough to prevent "spikes"
        self.set_decorated(False)
        self.set_focusable(False)
        
        self.state = 'recording'
        self.angle = 0
        self.scale = 1.0
        self.glow_alpha = 0.3
        
        self.area = Gtk.DrawingArea()
        self.area.set_draw_func(self.on_draw)
        self.set_child(self.area)

        self.monitor = AudioMonitor()
        GLib.timeout_add(20, self.tick)

    def on_draw(self, area, cr, width, height):
        cx, cy = width / 2, height / 2
        
        # 1. Background (Force Transparency)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        if self.state == 'recording':
            # --- APPLE STYLE PULSING ORB ---
            radius = 35 * self.scale
            
            # Draw Outer Glow (Gradient)
            lg = cairo.RadialGradient(cx, cy, radius * 0.5, cx, cy, radius * 1.5)
            lg.add_color_stop_rgba(0, 1.0, 0.23, 0.18, 0.6) # Solid red center
            lg.add_color_stop_rgba(1, 1.0, 0.23, 0.18, 0.0) # Fade to nothing
            cr.set_source(lg)
            cr.arc(cx, cy, radius * 1.5, 0, 2 * math.pi)
            cr.fill()

            # Draw Main Orb (Smooth Glassy look)
            cr.set_source_rgba(1.0, 0.23, 0.18, 0.9)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.fill()
            
        else:
            # --- APPLE STYLE LOADING SPINNER ---
            radius = 25
            cr.set_line_width(5)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            
            # Background Ring
            cr.set_source_rgba(0.0, 0.48, 1.0, 0.1)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.stroke()
            
            # Rotating Gradient Arc
            lg = cairo.RadialGradient(cx, cy, radius - 10, cx, cy, radius + 10)
            lg.add_color_stop_rgba(0, 0.0, 0.48, 1.0, 1.0)
            cr.set_source_rgba(0.0, 0.48, 1.0, 1.0)
            
            # Draw a nice fading trail
            for i in range(10):
                alpha = 1.0 - (i * 0.1)
                cr.set_source_rgba(0.0, 0.48, 1.0, alpha)
                cr.arc(cx, cy, radius, self.angle - (i * 0.1), self.angle - (i * 0.1) + 0.1)
                cr.stroke()

    def tick(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            
            # Noise Gate: Re-adjusted to 0.48 to be super silent on noise
            if vol < 0.48:
                target_scale = 1.0
            else:
                # Spring physics logic for "Organic" feel
                target_scale = 1.0 + (vol * 1.2)
            
            # Organic Smoothing (Easing)
            self.scale += (target_scale - self.scale) * 0.2
        else:
            # Fast, smooth rotation
            self.angle = (self.angle + 0.15) % (2 * math.pi)
        
        self.area.queue_draw()
        return True

    def start_loading(self):
        log("Transitioning to SIRI SPINNER...")
        self.state = 'loading'
        self.monitor.stop()

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
