#!/usr/bin/env python3
"""
Dictate Pro - 3-Element Floating Triad (Distraction-Free Offline Voice Interface)
- Left Element: Cancel [ ✕ ] button (immediately discards recording)
- Center Element: Horizontal rounded Waveform Pill with live audio reactivity & smooth loading animation
- Right Element: Confirm [ ✓ ] button (stops recording and transcribes locally via small model)
- Zero background transcription overhead during speech (100% lightweight & fast).
"""

import sys
import os
import signal
import math
import struct
import threading
import time
import random
import ctypes
import subprocess
import numpy as np

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
import cairo

LOG_FILE = "/tmp/dictate_debug.log"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DICTATE_SCRIPT = os.path.join(SCRIPT_DIR, "dictate.sh")

def log(msg):
    """Log messages to a debug file for easier troubleshooting."""
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.ctime()}: [Orb] {msg}\n")
    except Exception:
        pass

def suppress_c_stderr():
    """Temporarily redirect C-level stderr to /dev/null to silence ALSA/Jack spew."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        old_stderr = os.dup(2)
        os.dup2(devnull, 2)
        os.close(devnull)
        return old_stderr
    except Exception:
        return None

def restore_c_stderr(old_stderr):
    """Restore C-level stderr."""
    if old_stderr is not None:
        try:
            os.dup2(old_stderr, 2)
            os.close(old_stderr)
        except Exception:
            pass

class AudioMonitor:
    """Analyzes microphone input via PyAudio callback to provide real-time volume and spectrum."""
    def __init__(self, num_bands=19):
        self.num_bands = num_bands
        self.current_volume = 0.0
        self.band_levels = [0.0] * num_bands
        self.p = None
        self.stream = None
        self.window = np.hanning(512)
        
        try:
            import pyaudio
            old_err = suppress_c_stderr()
            self.p = pyaudio.PyAudio()
            restore_c_stderr(old_err)
            
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=512,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
        except Exception as e:
            log(f"Mic initialization error: {e}")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Processes audio buffer in PyAudio callback thread."""
        try:
            import pyaudio
            if not in_data:
                return (None, pyaudio.paContinue)
            samples = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Compute RMS Volume
            rms = float(np.sqrt(np.mean(samples ** 2)))
            if np.isnan(rms):
                rms = 0.0
            level = math.log10(rms * 9.0 + 1.0) if rms > 0 else 0.0
            self.current_volume = min(max(level, 0.0), 1.0)
            
            # Compute FFT for frequency spectrum (approx 100Hz to 3800Hz)
            if len(samples) == len(self.window):
                fft = np.abs(np.fft.rfft(samples * self.window))
            else:
                fft = np.abs(np.fft.rfft(samples))
            freq_bins = len(fft)
            
            band_vals = []
            voice_min_bin = 3
            voice_max_bin = min(115, freq_bins - 1)
            bin_step = max(1, (voice_max_bin - voice_min_bin) // self.num_bands)
            
            for b in range(self.num_bands):
                start_b = voice_min_bin + b * bin_step
                end_b = min(start_b + bin_step, voice_max_bin)
                if end_b > start_b:
                    energy = float(np.mean(fft[start_b:end_b]))
                else:
                    energy = float(fft[start_b]) if start_b < freq_bins else 0.0
                
                val = math.log10(energy * 25.0 + 1.0) / 1.6
                band_vals.append(min(max(val, 0.0), 1.0))
            
            self.band_levels = band_vals
            return (None, pyaudio.paContinue)
        except Exception:
            import pyaudio
            return (None, pyaudio.paContinue)

    def stop(self):
        """Cleanly stops and releases audio resources."""
        try:
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            if self.p:
                self.p.terminate()
                self.p = None
        except Exception as e:
            log(f"Audio cleanup exception: {e}")

class RecordingOrb(Gtk.ApplicationWindow):
    """Floating UI with 3-Element Triad: [ ✕ ] [ Waveform Pill ] [ ✓ ]"""
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("Dictate Pro")
        
        # Window canvas size
        self.win_w = 340
        self.win_h = 70
        
        # Triad Geometry
        self.triad_cy = 35.0
        self.pill_w = 210.0
        self.pill_h = 46.0
        self.pill_r = 23.0
        self.pill_x = (self.win_w - self.pill_w) / 2.0 # 65.0
        self.pill_y = (self.win_h - self.pill_h) / 2.0 # 12.0
        
        self.btn_r = 20.0 # 40px diameter buttons
        self.btn_gap = 12.0
        self.cx_cancel = self.pill_x - self.btn_gap - self.btn_r # 33.0
        self.cx_confirm = self.pill_x + self.pill_w + self.btn_gap + self.btn_r # 307.0
        
        self.set_default_size(self.win_w, self.win_h)
        self.set_decorated(False)
        self.set_focusable(False)
        self.set_resizable(False)
        
        self.state = 'recording' # 'recording', 'loading'
        self.start_time = time.time()
        self.time_sec = 0.0
        
        self.vol_smooth = 0.0
        self.entrance_scale = 0.0
        self.num_bars = 19
        self.bar_heights = [4.0] * self.num_bars
        
        # Hover and click states
        self.hover_btn = None # 'cancel', 'confirm', or None
        self.cancel_hover_anim = 0.0
        self.confirm_hover_anim = 0.0
        
        # Color angles for gentle ambient background drift
        self.angles = [random.randint(0, 360) for _ in range(5)]
        self.base_speeds = [0.0] * 5
        self.target_speeds = [0.0] * 5
        
        # Loading animation parameters
        self.loading_progress = 0.0
        self.load_transition = 0.0
        
        # Audio Monitor
        self.monitor = AudioMonitor(num_bands=self.num_bars)
        
        self.randomize_parameters()
        self.setup_ui()
        
        # 60 FPS animation timer (16ms)
        GLib.timeout_add(16, self.on_animation_frame)
        GLib.timeout_add(2500, self.randomize_parameters)

    def setup_ui(self):
        """Sets up GTK4 DrawingArea with Cairo rendering and mouse interaction controllers."""
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_size_request(self.win_w, self.win_h)
        self.drawing_area.set_draw_func(self.draw_func, None)
        
        # Mouse Click Controller
        click_controller = Gtk.GestureClick()
        click_controller.connect("pressed", self.on_mouse_pressed)
        self.drawing_area.add_controller(click_controller)
        
        # Mouse Motion Controller (Hover)
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("motion", self.on_mouse_motion)
        motion_controller.connect("leave", self.on_mouse_leave)
        self.drawing_area.add_controller(motion_controller)
        
        self.set_child(self.drawing_area)
        
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window {
                background-color: transparent;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_mouse_motion(self, controller, x, y):
        """Tracks hover state over left Cancel button and right Confirm button."""
        dist_cancel_sq = (x - self.cx_cancel) ** 2 + (y - self.triad_cy) ** 2
        dist_confirm_sq = (x - self.cx_confirm) ** 2 + (y - self.triad_cy) ** 2
        hit_radius_sq = (self.btn_r + 5.0) ** 2
        
        old_hover = self.hover_btn
        if dist_cancel_sq <= hit_radius_sq:
            self.hover_btn = 'cancel'
        elif dist_confirm_sq <= hit_radius_sq:
            self.hover_btn = 'confirm'
        else:
            self.hover_btn = None
            
        if self.hover_btn != old_hover:
            cursor_name = "pointer" if self.hover_btn else "default"
            self.set_cursor_from_name(cursor_name)
            self.drawing_area.queue_draw()

    def on_mouse_leave(self, controller):
        """Clears hover state when mouse leaves window."""
        if self.hover_btn is not None:
            self.hover_btn = None
            self.set_cursor_from_name("default")
            self.drawing_area.queue_draw()

    def on_mouse_pressed(self, gesture, n_press, x, y):
        """Handles clicks on Cancel [ ✕ ] and Confirm [ ✓ ] buttons."""
        dist_cancel_sq = (x - self.cx_cancel) ** 2 + (y - self.triad_cy) ** 2
        dist_confirm_sq = (x - self.cx_confirm) ** 2 + (y - self.triad_cy) ** 2
        hit_radius_sq = (self.btn_r + 5.0) ** 2
        
        if dist_cancel_sq <= hit_radius_sq:
            # User clicked Cancel [ ✕ ]
            log("Cancel button [X] clicked -> Aborting recording session.")
            self.monitor.stop()
            os.system(f"bash {DICTATE_SCRIPT} --cancel &")
            self.get_application().quit()
        elif dist_confirm_sq <= hit_radius_sq:
            # User clicked Confirm [ ✓ ]
            if self.state == 'recording':
                log("Confirm button [✓] clicked -> Submitting recording.")
                self.start_loading()
                os.system(f"bash {DICTATE_SCRIPT} &")

    def randomize_parameters(self):
        # Calm, gentle ambient drift speed
        self.target_speeds = [random.uniform(0.06, 0.18) * random.choice([-1, 1]) for _ in range(5)]
        return True

    def start_loading(self):
        """Transitions overlay to loading state without re-triggering dictate.sh."""
        if self.state != 'loading':
            self.state = 'loading'
            self.monitor.stop()

    def on_animation_frame(self):
        """Main 60 FPS animation tick."""
        self.time_sec = time.time() - self.start_time
        
        # Smooth entrance scale
        if self.entrance_scale < 1.0:
            self.entrance_scale += (1.0 - self.entrance_scale) * 0.2
            if self.entrance_scale > 0.995:
                self.entrance_scale = 1.0

        # Hover transitions
        target_cancel_h = 1.0 if self.hover_btn == 'cancel' else 0.0
        self.cancel_hover_anim += (target_cancel_h - self.cancel_hover_anim) * 0.2
        
        target_confirm_h = 1.0 if self.hover_btn == 'confirm' else 0.0
        self.confirm_hover_anim += (target_confirm_h - self.confirm_hover_anim) * 0.2

        # State transition interpolation
        if self.state == 'loading':
            if self.load_transition < 1.0:
                self.load_transition += (1.0 - self.load_transition) * 0.15
            self.loading_progress += 0.05
            vol = 0.0
            band_levels = [0.0] * self.num_bars
        else:
            vol = self.monitor.current_volume
            band_levels = self.monitor.band_levels

        # Audio volume smoothing
        vol_active = vol if vol > 0.06 else 0.0
        self.vol_smooth += (vol_active - self.vol_smooth) * 0.25
        speed_boost = 1.0 + (self.vol_smooth * 0.3) if self.state == 'recording' else 1.0

        # Rotate spinning color angles smoothly
        for i in range(5):
            self.base_speeds[i] += (self.target_speeds[i] - self.base_speeds[i]) * 0.04
            self.angles[i] = (self.angles[i] + (self.base_speeds[i] * speed_boost)) % 360

        # Waveform physics
        for i in range(self.num_bars):
            norm_idx = (i - (self.num_bars - 1) / 2.0) / ((self.num_bars - 1) / 2.0)
            center_weight = math.cos(norm_idx * (math.pi / 2.6))
            
            idle_wave = 3.5 + 2.5 * math.sin(self.time_sec * 3.5 + i * 0.45)
            b_energy = band_levels[i] if i < len(band_levels) else 0.0
            voice_target = (b_energy * 0.7 + self.vol_smooth * 0.5) * center_weight * 32.0
            
            target_h = max(idle_wave, 3.5 + voice_target)
            target_h = min(target_h, 32.0)
            
            if target_h > self.bar_heights[i]:
                self.bar_heights[i] += (target_h - self.bar_heights[i]) * 0.45
            else:
                self.bar_heights[i] += (target_h - self.bar_heights[i]) * 0.15

        self.drawing_area.queue_draw()
        return True

    def _draw_pill_path(self, cr, x, y, w, h, r):
        """Draws a rounded pill / rounded rectangle path."""
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def draw_func(self, area, cr, width, height, user_data):
        """Renders the 3-Element Floating Triad: [ ✕ ] [ Waveform Pill ] [ ✓ ]"""
        scale = self.entrance_scale
        if scale <= 0.01:
            return

        cx = width / 2.0
        cy = height / 2.0

        pw = self.pill_w * scale
        ph = self.pill_h * scale
        pr = self.pill_r * scale
        px = self.pill_x + (self.pill_w - pw) / 2.0
        py = self.pill_y + (self.pill_h - ph) / 2.0

        btn_rad = self.btn_r * scale
        cx_cancel = self.cx_cancel
        cx_confirm = self.cx_confirm
        cy_triad = self.triad_cy

        # -------------------------------------------------------------------------
        # A. LEFT ELEMENT: Cancel Button [ ✕ ]
        # -------------------------------------------------------------------------
        # Drop Shadow
        cr.arc(cx_cancel, cy_triad + 2.5, btn_rad, 0, math.pi * 2)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.35)
        cr.fill()

        # Hover Ambient Coral Glow
        c_hover = self.cancel_hover_anim
        if c_hover > 0.02:
            glow_r = btn_rad + 4.0 * scale
            cr.arc(cx_cancel, cy_triad, glow_r, 0, math.pi * 2)
            c_glow = cairo.RadialGradient(cx_cancel, cy_triad, btn_rad * 0.5, cx_cancel, cy_triad, glow_r)
            c_glow.add_color_stop_rgba(0.0, 1.0, 0.27, 0.23, 0.35 * c_hover)
            c_glow.add_color_stop_rgba(1.0, 1.0, 0.27, 0.23, 0.0)
            cr.set_source(c_glow)
            cr.fill()

        # Button Body
        cr.arc(cx_cancel, cy_triad, btn_rad, 0, math.pi * 2)
        bg_cancel = cairo.LinearGradient(cx_cancel, cy_triad - btn_rad, cx_cancel, cy_triad + btn_rad)
        bg_cancel.add_color_stop_rgba(0.0, 0.08 + 0.10 * c_hover, 0.09, 0.12, 0.95)
        bg_cancel.add_color_stop_rgba(1.0, 0.04 + 0.08 * c_hover, 0.04, 0.06, 0.97)
        cr.set_source(bg_cancel)
        cr.fill()

        # Button Rim
        cr.arc(cx_cancel, cy_triad, btn_rad - 0.75, 0, math.pi * 2)
        rim_c = cairo.LinearGradient(cx_cancel, cy_triad - btn_rad, cx_cancel, cy_triad + btn_rad)
        rim_c.add_color_stop_rgba(0.0, 1.0, 0.27 + 0.73 * (1.0 - c_hover), 0.23 + 0.77 * (1.0 - c_hover), 0.25 + 0.55 * c_hover)
        rim_c.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.3)
        cr.set_source(rim_c)
        cr.stroke()

        # Cancel Icon: Crisp [ ✕ ]
        x_size = 5.2 * scale
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_width(2.2 * scale)
        cr.move_to(cx_cancel - x_size, cy_triad - x_size)
        cr.line_to(cx_cancel + x_size, cy_triad + x_size)
        cr.move_to(cx_cancel + x_size, cy_triad - x_size)
        cr.line_to(cx_cancel - x_size, cy_triad + x_size)
        cr.set_source_rgba(1.0, 0.30 + 0.70 * (1.0 - c_hover), 0.25 + 0.75 * (1.0 - c_hover), 0.85 + 0.15 * c_hover)
        cr.stroke()

        # -------------------------------------------------------------------------
        # B. CENTER ELEMENT: Waveform Pill
        # -------------------------------------------------------------------------
        # Drop Shadow
        self._draw_pill_path(cr, px, py + 2.8, pw, ph, pr)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.35)
        cr.fill()

        # Subtle Ambient Glow
        glow_intensity = (self.vol_smooth * 0.25) if self.state == 'recording' else 0.15
        if glow_intensity > 0.02:
            glow_pad = 4.0 * scale
            self._draw_pill_path(cr, px - glow_pad, py - glow_pad, pw + glow_pad * 2, ph + glow_pad * 2, pr + glow_pad)
            glow_grad = cairo.LinearGradient(px, py, px + pw, py + ph)
            glow_grad.add_color_stop_rgba(0.0, 0.0, 0.48, 1.0, 0.15 * glow_intensity)
            glow_grad.add_color_stop_rgba(0.5, 0.68, 0.32, 0.87, 0.18 * glow_intensity)
            glow_grad.add_color_stop_rgba(1.0, 1.0, 0.23, 0.19, 0.14 * glow_intensity)
            cr.set_source(glow_grad)
            cr.fill()

        # Pill Body
        self._draw_pill_path(cr, px, py, pw, ph, pr)
        bg_grad = cairo.LinearGradient(px, py, px, py + ph)
        bg_grad.add_color_stop_rgba(0.0, 0.07, 0.08, 0.12, 0.95)
        bg_grad.add_color_stop_rgba(1.0, 0.03, 0.04, 0.07, 0.97)
        cr.set_source(bg_grad)
        cr.fill()

        # Plasma Background Inside Pill
        cr.save()
        self._draw_pill_path(cr, px, py, pw, ph, pr)
        cr.clip()

        swirl_rad = pw * 0.75
        plasma_alpha = 0.08 + (self.vol_smooth * 0.06) if self.state == 'recording' else 0.09
        
        rad1 = math.radians(self.angles[0])
        x1 = cx + math.cos(rad1) * (pw * 0.35)
        y1 = cy_triad + math.sin(rad1) * (ph * 0.4)
        grad1 = cairo.RadialGradient(x1, y1, 0, x1, y1, swirl_rad)
        grad1.add_color_stop_rgba(0.0, 1.0, 0.23, 0.19, plasma_alpha * 0.75)
        grad1.add_color_stop_rgba(0.7, 1.0, 0.23, 0.19, 0.0)
        cr.set_source(grad1)
        cr.paint()

        rad2 = math.radians(self.angles[1])
        x2 = cx + math.cos(rad2) * (pw * 0.35)
        y2 = cy_triad + math.sin(rad2) * (ph * 0.4)
        grad2 = cairo.RadialGradient(x2, y2, 0, x2, y2, swirl_rad)
        grad2.add_color_stop_rgba(0.0, 0.68, 0.32, 0.87, plasma_alpha * 0.85)
        grad2.add_color_stop_rgba(0.7, 0.68, 0.32, 0.87, 0.0)
        cr.set_source(grad2)
        cr.paint()

        rad3 = math.radians(self.angles[2])
        x3 = cx + math.cos(rad3) * (pw * 0.35)
        y3 = cy_triad + math.sin(rad3) * (ph * 0.4)
        grad3 = cairo.RadialGradient(x3, y3, 0, x3, y3, swirl_rad)
        grad3.add_color_stop_rgba(0.0, 0.0, 0.48, 1.0, plasma_alpha * 0.90)
        grad3.add_color_stop_rgba(0.7, 0.0, 0.48, 1.0, 0.0)
        cr.set_source(grad3)
        cr.paint()

        # Waveform Content
        trans = self.load_transition
        if trans < 0.99:
            wave_alpha = (1.0 - trans)
            bar_w = 3.2 * scale
            bar_spacing = 6.2 * scale
            total_wave_w = (self.num_bars - 1) * bar_spacing
            start_x = cx - total_wave_w / 2.0

            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_width(bar_w)

            for i in range(self.num_bars):
                bx_bar = start_x + i * bar_spacing
                bh_bar = self.bar_heights[i] * scale * (1.0 - trans)
                if bh_bar < 3.0 * scale:
                    bh_bar = 3.0 * scale

                y_top = cy_triad - bh_bar / 2.0
                y_bot = cy_triad + bh_bar / 2.0
                bar_grad = cairo.LinearGradient(bx_bar, y_top, bx_bar, y_bot)
                
                norm_pos = i / float(self.num_bars - 1)
                r = 0.2 + 0.8 * norm_pos
                g = 0.5 + 0.4 * (1.0 - abs(norm_pos - 0.5) * 2.0)
                b = 1.0
                
                bar_grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.95 * wave_alpha)
                bar_grad.add_color_stop_rgba(0.2, r, g, b, 0.90 * wave_alpha)
                bar_grad.add_color_stop_rgba(1.0, 0.0, 0.48, 1.0, 0.85 * wave_alpha)

                cr.move_to(bx_bar, y_top)
                cr.line_to(bx_bar, y_bot)
                cr.set_source(bar_grad)
                cr.stroke()

        # Loading Animation in Pill
        if trans > 0.01:
            load_alpha = trans
            num_load_dots = 7
            load_spacing = 13.0 * scale
            total_load_w = (num_load_dots - 1) * load_spacing
            load_start_x = cx - total_load_w / 2.0

            for d in range(num_load_dots):
                dx = load_start_x + d * load_spacing
                phase = self.loading_progress * 4.0 - d * 0.6
                dy_offset = math.sin(phase) * (5.5 * scale)
                dot_size = (3.0 + 1.8 * math.cos(phase)) * scale
                if dot_size < 1.8 * scale:
                    dot_size = 1.8 * scale

                dot_y = cy_triad + dy_offset
                dot_grad = cairo.RadialGradient(dx, dot_y, 0, dx, dot_y, dot_size * 2.0)
                
                c_idx = (d / float(num_load_dots))
                dr = 0.1 + 0.9 * c_idx
                dg = 0.6 + 0.4 * math.sin(phase)
                db = 1.0
                
                dot_grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.95 * load_alpha)
                dot_grad.add_color_stop_rgba(0.4, dr, dg, db, 0.85 * load_alpha)
                dot_grad.add_color_stop_rgba(1.0, 0.0, 0.48, 1.0, 0.0)

                cr.arc(dx, dot_y, dot_size, 0, math.pi * 2)
                cr.set_source(dot_grad)
                cr.fill()

        cr.restore()

        # Pill Rim
        self._draw_pill_path(cr, px + 0.75, py + 0.75, pw - 1.5, ph - 1.5, pr - 0.75)
        rim_rad = math.radians(self.angles[4])
        rim_x1 = cx + math.cos(rim_rad) * (pw / 2.0)
        rim_y1 = cy_triad + math.sin(rim_rad) * (ph / 2.0)
        rim_x2 = cx - math.cos(rim_rad) * (pw / 2.0)
        rim_y2 = cy_triad - math.sin(rim_rad) * (ph / 2.0)
        
        rim_grad = cairo.LinearGradient(rim_x1, rim_y1, rim_x2, rim_y2)
        rim_grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.35)
        rim_grad.add_color_stop_rgba(0.3, 0.68, 0.32, 0.87, 0.22)
        rim_grad.add_color_stop_rgba(0.7, 0.0, 0.48, 1.0, 0.18)
        rim_grad.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.08)
        
        cr.set_line_width(1.3)
        cr.set_source(rim_grad)
        cr.stroke()

        # -------------------------------------------------------------------------
        # C. RIGHT ELEMENT: Confirm Button [ ✓ ]
        # -------------------------------------------------------------------------
        # Drop Shadow
        cr.arc(cx_confirm, cy_triad + 2.5, btn_rad, 0, math.pi * 2)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.35)
        cr.fill()

        # Hover Ambient Emerald Glow
        cf_hover = self.confirm_hover_anim
        if cf_hover > 0.02:
            glow_r = btn_rad + 4.0 * scale
            cr.arc(cx_confirm, cy_triad, glow_r, 0, math.pi * 2)
            cf_glow = cairo.RadialGradient(cx_confirm, cy_triad, btn_rad * 0.5, cx_confirm, cy_triad, glow_r)
            cf_glow.add_color_stop_rgba(0.0, 0.19, 0.82, 0.35, 0.35 * cf_hover)
            cf_glow.add_color_stop_rgba(1.0, 0.19, 0.82, 0.35, 0.0)
            cr.set_source(cf_glow)
            cr.fill()

        # Button Body
        cr.arc(cx_confirm, cy_triad, btn_rad, 0, math.pi * 2)
        bg_confirm = cairo.LinearGradient(cx_confirm, cy_triad - btn_rad, cx_confirm, cy_triad + btn_rad)
        bg_confirm.add_color_stop_rgba(0.0, 0.08, 0.10 + 0.08 * cf_hover, 0.09, 0.95)
        bg_confirm.add_color_stop_rgba(1.0, 0.04, 0.06 + 0.06 * cf_hover, 0.04, 0.97)
        cr.set_source(bg_confirm)
        cr.fill()

        # Button Rim
        cr.arc(cx_confirm, cy_triad, btn_rad - 0.75, 0, math.pi * 2)
        rim_cf = cairo.LinearGradient(cx_confirm, cy_triad - btn_rad, cx_confirm, cy_triad + btn_rad)
        rim_cf.add_color_stop_rgba(0.0, 0.19 + 0.81 * (1.0 - cf_hover), 0.82 + 0.18 * (1.0 - cf_hover), 0.35 + 0.65 * (1.0 - cf_hover), 0.25 + 0.55 * cf_hover)
        rim_cf.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.3)
        cr.set_source(rim_cf)
        cr.stroke()

        # Confirm Icon: Crisp [ ✓ ]
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_width(2.4 * scale)
        cr.move_to(cx_confirm - 5.5 * scale, cy_triad + 0.5 * scale)
        cr.line_to(cx_confirm - 1.5 * scale, cy_triad + 4.5 * scale)
        cr.line_to(cx_confirm + 5.5 * scale, cy_triad - 3.5 * scale)
        cr.set_source_rgba(0.20 + 0.80 * (1.0 - cf_hover), 0.85 + 0.15 * (1.0 - cf_hover), 0.38 + 0.62 * (1.0 - cf_hover), 0.85 + 0.15 * cf_hover)
        cr.stroke()

class OrbApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.master.v7.triad")
        self.win = None
        
    def do_activate(self):
        self.win = RecordingOrb(self)
        self.win.present()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.on_sigusr1)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.on_sigterm)
        
    def on_sigusr1(self):
        """Triggered when Space or Confirm button is pressed (switches to loading state)."""
        log("Received SIGUSR1 -> switching to loading state")
        if self.win:
            GLib.idle_add(self.win.start_loading)
        return True
        
    def on_sigterm(self):
        """Triggered when transcription is done (closes overlay)."""
        log("Received SIGTERM -> closing overlay")
        if self.win:
            self.win.monitor.stop()
        self.quit()
        return False

if __name__ == "__main__":
    app = OrbApp()
    app.run(None)
