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
import random

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

LOG_FILE = "/tmp/dictate_debug.log"

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.ctime()}: [WaveOrb] {msg}\n")

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

class RecordingOrb(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Dictate Overlay")
        self.set_default_size(250, 250)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        
        # Transparent background for GTK3
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        self.state = 'recording'
        self.angle = 0
        self.vol_smooth = 0
        
        # Wave particles
        self.waves = [] # Each wave: [radius, color, alpha, speed]

        self.area = Gtk.DrawingArea()
        self.area.connect("draw", self.on_draw)
        self.add(self.area)

        self.monitor = AudioMonitor()
        GLib.timeout_add(20, self.tick)

    def on_draw(self, area, cr):
        width = area.get_allocated_width()
        height = area.get_allocated_height()
        cx, cy = width / 2, height / 2
        
        # Clear
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        if self.state == 'recording':
            # 1. DRAW WAVES (Expanding Rings)
            for wave in self.waves[:]:
                radius, color, alpha, speed = wave
                cr.set_line_width(2)
                if color == 'red':
                    cr.set_source_rgba(1.0, 0.23, 0.18, alpha)
                else:
                    cr.set_source_rgba(0.0, 0.48, 1.0, alpha)
                
                cr.arc(cx, cy, radius, 0, 2 * math.pi)
                cr.stroke()
                
                # Update wave
                wave[0] += speed
                wave[2] -= 0.02 # Fade out
                if wave[2] <= 0:
                    self.waves.remove(wave)

            # 2. DRAW WHITE CORE
            radius = 20 + (self.vol_smooth * 15)
            # Subtle shadow
            cr.set_source_rgba(0, 0, 0, 0.1)
            cr.arc(cx, cy, radius + 2, 0, 2 * math.pi)
            cr.fill()
            # Main white ball
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.fill()
            
        else:
            # SIRI SPINNER
            radius = 25
            cr.set_line_width(4)
            cr.set_source_rgba(0.0, 0.48, 1.0, 0.2)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.stroke()
            
            cr.set_source_rgba(0.0, 0.48, 1.0, 1.0)
            cr.arc(cx, cy, radius, self.angle, self.angle + (math.pi * 0.7))
            cr.stroke()

    def tick(self):
        if self.state == 'recording':
            vol = self.monitor.get_volume()
            # Noise gate 0.45
            vol = vol if vol > 0.45 else 0
            self.vol_smooth += (vol - self.vol_smooth) * 0.2
            
            # Spawn new waves based on sound
            if vol > 0.5:
                # Spawn red or blue wave
                color = 'red' if random.random() > 0.5 else 'blue'
                # [radius, color, alpha, speed]
                self.waves.append([20, color, 0.8, 2.0 + (vol * 3.0)])
            
            # Rotate spinner angle just in case
            self.angle = (self.angle + 0.15) % (2 * math.pi)
        else:
            self.angle = (self.angle + 0.15) % (2 * math.pi)
        
        self.area.queue_draw()
        return True

    def start_loading(self):
        self.state = 'loading'
        self.monitor.stop()

if __name__ == "__main__":
    win = RecordingOrb()
    
    def sigusr1_handler(signum, frame):
        GLib.idle_add(win.start_loading)
    def sigterm_handler(signum, frame):
        win.monitor.stop()
        Gtk.main_quit()
        
    signal.signal(signal.SIGUSR1, sigusr1_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)
    
    win.show_all()
    Gtk.main()
