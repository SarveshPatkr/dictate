#!/usr/bin/env python3
"""AI Chat - Mac frosted theme, dictation bar + chat history."""

import sys, os, time, json, subprocess, threading, math, random
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = "/tmp/ai_chat_debug.log"

def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{time.ctime()}: [AI Chat] {msg}\n")
    except Exception:
        pass

def load_env():
    path = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()


class AIChatWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("AI Ask")
        # Calculate screen height
        screen_height = 800
        try:
            display = Gdk.Display.get_default()
            monitors = display.get_monitors()
            if monitors and monitors.get_n_items() > 0:
                monitor = monitors.get_item(0)
                if monitor:
                    screen_height = monitor.get_geometry().height
        except Exception:
            pass
        window_height = int(screen_height * 0.80)
        self.set_default_size(540, window_height)
        self.set_decorated(False)
        self.set_resizable(True)  # Enable to allow programmatic shrinking via self.resize()
        self.is_recording = False
        self.record_proc = None
        self.audio_file = "/tmp/ai_chat_audio.wav"
        self.chat_history = []

        self.angles = [random.randint(0, 360) for _ in range(5)]
        self.speeds = [random.uniform(0.3, 1.5) * random.choice([-1, 1]) for _ in range(5)]
        self.stops = [10.0 + random.uniform(0, 20) for _ in range(3)]
        self.shimmer_stop = 15.0
        self.breath = 0.0
        self.arc_angle = 0

        # Kill any stray processes before starting
        self.cleanup_old_recordings()

        self.setup_style()
        self.build_ui()
        
        self.orb_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self.orb_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.connect("destroy", self.on_destroy)

        GLib.timeout_add(33, self.animate_orb)
        GLib.timeout_add(1200, self.jiggle_speeds)
        GLib.idle_add(self.start_dictation)
        GLib.idle_add(self.force_shrink)

    def force_shrink(self):
        pass

    def on_text_changed(self, buffer):
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True).strip()
        self.placeholder_lbl.set_visible(len(text) == 0)

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if state & Gdk.ModifierType.SHIFT_MASK:
                return False
            else:
                self.on_ask()
                return True
        return False

    def _entry_get_text(self):
        buf = self.entry.get_buffer()
        start, end = buf.get_bounds()
        return buf.get_text(start, end, True)

    def _entry_set_text(self, text):
        self.entry.get_buffer().set_text(text)

    def _entry_set_placeholder(self, text):
        if hasattr(self, 'placeholder_lbl'):
            self.placeholder_lbl.set_text(text)

    def on_destroy(self, *args):
        self._stop_recording()
        self.cleanup_old_recordings()

    def cleanup_old_recordings(self):
        log("Cleaning up old recordings...")
        # 1. Kill any existing pw-record processes started by us
        try:
            import subprocess
            pids = subprocess.check_output(["pgrep", "-f", "pw-record.*ai_chat_audio.wav"], text=True)
            for pid in pids.strip().split():
                if pid:
                    log(f"Killing old process {pid}")
                    os.kill(int(pid), 9)  # SIGKILL to guarantee death
        except Exception:
            pass

        # 2. Delete the audio file so we start fresh
        try:
            if os.path.exists(self.audio_file):
                os.remove(self.audio_file)
                log("Deleted old audio file.")
        except Exception:
            pass

    def setup_style(self):
        css = Gtk.CssProvider()
        css.load_from_data(b"""
            /* Force full transparency on the window container elements to avoid black backdrops */
            window, window.background, window.decoration, .background {
                background-color: transparent;
                background-image: none;
                box-shadow: none;
                border: none;
            }
            
            /* Main container box styling - Fully transparent window container */
            .window-container {
                background: transparent;
                border: none;
                box-shadow: none;
                margin: 1px;
                padding: 1px;
            }
            
            /* Transparent Drag Strip at top */
            .drag-strip {
                background: transparent;
            }
            
            /* Chat scrollview and content area */
            .chat-scroll {
                background: transparent;
                border: none;
            }
            .chat-scroll viewport {
                background: transparent;
            }
            .chat-scroll scrollbar {
                background: transparent;
                min-width: 6px;
            }
            .chat-scroll scrollbar slider {
                background: rgba(255, 255, 255, 0.12);
                border-radius: 3px;
                min-width: 6px;
            }
            .chat-scroll scrollbar slider:hover {
                background: rgba(255, 255, 255, 0.25);
            }
            
            /* Message layouts - Added soft shadows to ensure readability on transparent backing */
            .msg-wrap {
                padding: 1px;
                margin: 1px;
                font-size: 13px;
                line-height: 1.35;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            }
            .msg-wrap.user {
                background: linear-gradient(135deg, #007aff 0%, #8944ab 50%, #e03e3e 100%);
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 12px 12px 4px 12px;
            }
            .msg-wrap.user .msg-label {
                color: #ffffff;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.15);
            }
            
            /* AI Response bubbles - Dark obsidian/black with orb color tones */
            .msg-wrap.ai {
                background: linear-gradient(135deg, #121217 0%, #21122a 60%, #271212 100%);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px 12px 12px 4px;
            }
            .msg-wrap.ai .msg-label {
                color: #ffffff;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
            }
            
            /* Input Area Capsule - Light background, only part with solid container styling */
            .input-area {
                padding: 1px;
                margin: 1px;
                background: transparent;
            }
            .input-capsule {
                background: rgba(255, 255, 255, 0.9);
                border-radius: 20px;
                border: 1px solid rgba(0, 0, 0, 0.1);
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
                padding: 1px;
                margin: 1px;
                transition: all 0.25s ease;
            }
            
            /* Text Entry inside capsule - Black text color */
            .input-capsule textview, 
            .input-capsule textview:focus,
            .input-capsule textview text,
            .input-capsule textview text:focus {
                background: transparent;
                background-color: transparent;
                border: none;
                box-shadow: none;
                outline: none;
                outline-width: 0;
                outline-style: none;
                color: #000000;
                font-size: 13px;
                padding: 0;
                caret-color: #0a84ff;
            }
            
            /* Placeholder styling */
            .placeholder-label {
                color: rgba(0, 0, 0, 0.45);
                font-size: 13px;
                margin-left: 6px;
            }
            
            /* Action Buttons (Circular 36px, adapted to light container) */
            .btn-action {
                min-width: 36px;
                min-height: 36px;
                border-radius: 50%;
                border: 1px solid rgba(0, 0, 0, 0.05);
                background: rgba(0, 0, 0, 0.05);
                color: #000000;
                font-size: 14px;
                padding: 0;
                margin: 0;
                transition: all 0.2s ease;
            }
            .btn-orb-host {
                background: transparent;
                border: none;
                box-shadow: none;
                padding: 0;
            }
            .btn-orb-host:hover {
                background: transparent;
                opacity: 0.95;
            }
            .btn-orb-host:active {
                background: transparent;
                opacity: 0.8;
            }
            
            /* Static Idle Orb Styles */
            #idle_or { background: rgba(255, 59, 48, 0.7); border-radius: 50%; filter: blur(3px); }
            #idle_op { background: rgba(175, 82, 222, 0.6); border-radius: 50%; filter: blur(5px); }
            #idle_ob { background: rgba(0, 122, 255, 0.5); border-radius: 50%; filter: blur(7px); }
            #idle_os { background: linear-gradient(135deg, rgba(255, 255, 255, 0.7) 0%, transparent 25%); border-radius: 50%; opacity: 0.6; filter: blur(2px); }
            #idle_oc { background-color: #ffffff; border-radius: 50%; }
            .btn-action:hover {
                background: rgba(0, 0, 0, 0.1);
            }
            .btn-action:active {
                background: rgba(0, 0, 0, 0.03);
            }
            
            .btn-primary {
                background: #0a84ff;
                color: #ffffff;
                border: 1px solid rgba(10, 132, 255, 0.15);
            }
            .btn-primary:hover {
                background: #2994ff;
            }
            .btn-primary:active {
                background: #0070dd;
            }
            
            /* Cancel and Check buttons */
            .btn-x {
                background: rgba(255, 59, 48, 0.1);
                color: #ff3b30;
                border: 1px solid rgba(255, 59, 48, 0.15);
            }
            .btn-x:hover {
                background: rgba(255, 59, 48, 0.2);
            }
            
            .btn-check {
                background: rgba(52, 199, 89, 0.1);
                color: #34c759;
                border: 1px solid rgba(52, 199, 89, 0.15);
            }
            .btn-check:hover {
                background: rgba(52, 199, 89, 0.2);
            }
            
            /* Status spinners and labels */
            .spinner-label {
                color: rgba(0, 0, 0, 0.7);
                font-size: 12px;
                font-weight: 500;
            }
            spinner {
                color: #0a84ff;
            }
            
            /* Micro-spinner inside the pulsing orb */
            .orb-spinner {
                color: #ffffff;
            }

            /* Sleek Close Button at bottom center */
            .btn-close-bottom {
                min-width: 30px;
                min-height: 30px;
                border-radius: 50%;
                background: rgba(255, 59, 48, 0.75);
                border: 1px solid rgba(255, 59, 48, 0.45);
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
                padding: 0;
                margin: 0;
                transition: all 0.2s ease;
                box-shadow: 0 2px 8px rgba(255, 59, 48, 0.25);
            }
            .btn-close-bottom:hover {
                background: rgba(255, 59, 48, 0.95);
                border-color: rgba(255, 59, 48, 0.6);
                box-shadow: 0 4px 12px rgba(255, 59, 48, 0.4);
            }
            .btn-close-bottom:active {
                background: rgba(255, 59, 48, 0.5);
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_ui(self):
        # Root Overlay
        self.root_overlay = Gtk.Overlay()
        self.set_child(self.root_overlay)

        # Main window container box (No background - fully transparent)
        window_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        window_container.add_css_class("window-container")
        window_container.set_hexpand(True)
        window_container.set_vexpand(True)
        
        # Calculate screen height
        screen_height = 800
        try:
            display = Gdk.Display.get_default()
            monitors = display.get_monitors()
            if monitors and monitors.get_n_items() > 0:
                monitor = monitors.get_item(0)
                if monitor:
                    screen_height = monitor.get_geometry().height
        except Exception:
            pass
        window_height = int(screen_height * 0.80)
        window_container.set_size_request(540, window_height)

        # Window handle container for drag ability
        self.window_handle = Gtk.WindowHandle()
        self.window_handle.set_child(window_container)
        self.root_overlay.add_overlay(self.window_handle)

        # 1. Transparent Drag Strip at the top instead of a header title bar
        self.drag_strip = Gtk.Box()
        self.drag_strip.set_size_request(-1, 1)
        self.drag_strip.add_css_class("drag-strip")
        window_container.append(self.drag_strip)

        # 2. Chat Scroll Area
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add_css_class("chat-scroll")
        scrolled.set_margin_start(1)
        scrolled.set_margin_end(1)
        scrolled.set_margin_top(1)
        scrolled.set_margin_bottom(1)
        self.scrolled = scrolled

        self.history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self.history_box.set_valign(Gtk.Align.END)
        scrolled.set_child(self.history_box)
        window_container.append(scrolled)

        # 3. Input Capsule Bottom Area
        input_area = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        input_area.add_css_class("input-area")

        input_capsule = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        input_capsule.add_css_class("input-capsule")
        input_capsule.set_hexpand(True)

        # Scrolled overlay for multi-line TextView with overlayed placeholder label
        entry_overlay = Gtk.Overlay()
        entry_overlay.set_hexpand(True)
        entry_overlay.set_valign(Gtk.Align.CENTER)

        self.entry = Gtk.TextView()
        self.entry.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.entry.set_hexpand(True)
        self.entry.set_valign(Gtk.Align.CENTER)
        self.entry.set_accepts_tab(False)
        
        # Connect text changed signal to toggle placeholder
        self.entry.get_buffer().connect("changed", self.on_text_changed)
        
        # Connect key event listener for Shift+Enter vs Enter
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.entry.add_controller(key_controller)

        entry_scroll = Gtk.ScrolledWindow()
        entry_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        entry_scroll.set_propagate_natural_height(True)
        entry_scroll.set_max_content_height(80)  # Grow to ~4 lines then scroll
        entry_scroll.set_hexpand(True)
        entry_scroll.set_vexpand(False)
        entry_scroll.set_child(self.entry)

        self.placeholder_lbl = Gtk.Label(label="Ask anything...")
        self.placeholder_lbl.set_halign(Gtk.Align.START)
        self.placeholder_lbl.set_valign(Gtk.Align.CENTER)
        self.placeholder_lbl.add_css_class("placeholder-label")
        self.placeholder_lbl.set_can_target(False)  # Click-through

        entry_overlay.set_child(entry_scroll)
        entry_overlay.add_overlay(self.placeholder_lbl)
        input_capsule.append(entry_overlay)

        # Action stack for buttons (Sized perfectly for 36px buttons and orb)
        self.action_stack = Gtk.Stack()
        self.action_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.action_stack.set_transition_duration(200)
        self.action_stack.set_size_request(110, 36)
        self.action_stack.set_valign(Gtk.Align.CENTER)

        # State 1: Idle
        self.idle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.idle_box.set_halign(Gtk.Align.END)
        self.idle_box.set_valign(Gtk.Align.CENTER)
        
        # Idle Orb Overlay (36x36 layout)
        self.idle_orb_overlay = Gtk.Overlay()
        self.idle_orb_overlay.set_size_request(36, 36)
        self.idle_orb_overlay.set_valign(Gtk.Align.CENTER)
        
        self.idle_orb_core = Gtk.Box(name="idle_oc")
        self.idle_orb_r = Gtk.Box(name="idle_or")
        self.idle_orb_p = Gtk.Box(name="idle_op")
        self.idle_orb_b = Gtk.Box(name="idle_ob")
        self.idle_orb_s = Gtk.Box(name="idle_os")
        
        for w in [self.idle_orb_core, self.idle_orb_r, self.idle_orb_p, self.idle_orb_b, self.idle_orb_s]:
            w.set_size_request(36, 36)
            
        self.idle_orb_overlay.set_child(self.idle_orb_core)
        for w in [self.idle_orb_b, self.idle_orb_r, self.idle_orb_p, self.idle_orb_s]:
            self.idle_orb_overlay.add_overlay(w)

        self.chat_dictate_btn = Gtk.Button()
        self.chat_dictate_btn.set_tooltip_text("Dictate voice input")
        self.chat_dictate_btn.add_css_class("btn-action")
        self.chat_dictate_btn.add_css_class("btn-orb-host")
        self.chat_dictate_btn.set_size_request(36, 36)
        self.chat_dictate_btn.set_child(self.idle_orb_overlay)
        self.chat_dictate_btn.connect("clicked", lambda b: self.start_dictation())
        
        self.ask_btn = Gtk.Button(label="✦")
        self.ask_btn.set_tooltip_text("Send message")
        self.ask_btn.add_css_class("btn-action")
        self.ask_btn.add_css_class("btn-primary")
        self.ask_btn.set_size_request(36, 36)
        self.ask_btn.connect("clicked", lambda b: self.on_ask())
        
        self.idle_box.append(self.chat_dictate_btn)
        self.idle_box.append(self.ask_btn)
        self.action_stack.add_named(self.idle_box, "idle")

        # State 2: Recording (X + Orb visualizer + Check)
        self.recording_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.recording_box.set_halign(Gtk.Align.END)
        self.recording_box.set_valign(Gtk.Align.CENTER)
        
        self.x_btn = Gtk.Button(label="✕")
        self.x_btn.set_tooltip_text("Cancel dictation")
        self.x_btn.add_css_class("btn-action")
        self.x_btn.add_css_class("btn-x")
        self.x_btn.set_size_request(36, 36)
        self.x_btn.connect("clicked", lambda b: self.cancel_dictation())
        
        # Orb Overlay (36x36 layout)
        self.orb_overlay = Gtk.Overlay()
        self.orb_overlay.set_size_request(36, 36)
        self.orb_overlay.set_valign(Gtk.Align.CENTER)
        
        self.orb_core = Gtk.Box(name="oc")
        self.orb_r = Gtk.Box(name="or")
        self.orb_p = Gtk.Box(name="op")
        self.orb_b = Gtk.Box(name="ob")
        self.orb_s = Gtk.Box(name="os")
        self.orb_arc = Gtk.Box(name="oa")  # Spinning White Arc
        
        for w in [self.orb_core, self.orb_r, self.orb_p, self.orb_b, self.orb_s, self.orb_arc]:
            w.set_size_request(36, 36)
            
        self.orb_overlay.set_child(self.orb_core)
        for w in [self.orb_b, self.orb_r, self.orb_p, self.orb_s, self.orb_arc]:
            self.orb_overlay.add_overlay(w)
            
        # Add the spinner directly inside the orb_overlay
        self.orb_spinner = Gtk.Spinner()
        self.orb_spinner.set_size_request(18, 18)
        self.orb_spinner.set_halign(Gtk.Align.CENTER)
        self.orb_spinner.set_valign(Gtk.Align.CENTER)
        self.orb_spinner.add_css_class("orb-spinner")
        self.orb_spinner.set_visible(False)
        self.orb_overlay.add_overlay(self.orb_spinner)
            
        self.check_btn = Gtk.Button(label="✓")
        self.check_btn.set_tooltip_text("Accept dictation")
        self.check_btn.add_css_class("btn-action")
        self.check_btn.add_css_class("btn-check")
        self.check_btn.set_size_request(36, 36)
        self.check_btn.connect("clicked", lambda b: self.accept_dictation())
        
        self.recording_box.append(self.x_btn)
        self.recording_box.append(self.orb_overlay)
        self.recording_box.append(self.check_btn)
        self.action_stack.add_named(self.recording_box, "recording")

        # State 3: Thinking / Querying AI
        self.thinking_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.thinking_box.set_halign(Gtk.Align.END)
        self.thinking_box.set_valign(Gtk.Align.CENTER)
        think_spinner = Gtk.Spinner()
        think_spinner.set_size_request(16, 16)
        think_spinner.start()
        think_lbl = Gtk.Label(label="Thinking")
        think_lbl.add_css_class("spinner-label")
        self.thinking_box.append(think_spinner)
        self.thinking_box.append(think_lbl)
        self.action_stack.add_named(self.thinking_box, "thinking")

        input_capsule.append(self.action_stack)
        input_area.append(input_capsule)
        window_container.append(input_area)

        # 4. Bottom Close Button Area
        self.bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.bottom_bar.set_halign(Gtk.Align.CENTER)
        self.bottom_bar.set_margin_top(1)
        self.bottom_bar.set_margin_bottom(1)
        
        self.close_btn = Gtk.Button(label="✕")
        self.close_btn.add_css_class("btn-close-bottom")
        self.close_btn.connect("clicked", lambda b: self.close())
        self.bottom_bar.append(self.close_btn)
        window_container.append(self.bottom_bar)

    # --- Dictation ---

    def start_dictation(self):
        if self.is_recording:
            return
        self.is_recording = True
        
        # Kill previous duplicate processes and delete the audio file to start fresh
        self.cleanup_old_recordings()
        
        self.action_stack.set_visible_child_name("recording")
        
        # Reset buttons visibility and sensitiveness
        self.x_btn.set_visible(True)
        self.check_btn.set_visible(True)
        self.x_btn.set_sensitive(True)
        self.check_btn.set_sensitive(True)
        self.orb_spinner.set_visible(False)
        self.orb_spinner.stop()
        
        self.record_proc = subprocess.Popen(
            ["pw-record", "--format=s16", "--rate=16000", "--channels=1", self.audio_file],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self.entry.set_editable(False)
        self._entry_set_text("")
        self._entry_set_placeholder("Listening... Speak now")
        self.entry.grab_focus()
        log("Dictation started")
        self.force_shrink()

    def cancel_dictation(self):
        self._stop_recording()
        
        # Reset recording controls
        self.x_btn.set_visible(True)
        self.check_btn.set_visible(True)
        self.orb_spinner.set_visible(False)
        self.orb_spinner.stop()
        
        self.action_stack.set_visible_child_name("idle")
        self.entry.set_editable(True)
        self._entry_set_text("")
        self._entry_set_placeholder("Ask anything...")
        self.entry.grab_focus()
        self.force_shrink()

    def accept_dictation(self):
        self._stop_recording()
        
        # Animate the Accept state: Hide check/cancel, show processing spinner inside the orb
        self.x_btn.set_visible(False)
        self.check_btn.set_visible(False)
        self.orb_spinner.set_visible(True)
        self.orb_spinner.start()
        
        self._entry_set_placeholder("Transcribing your voice...")
        
        # Run transcription in a background thread
        threading.Thread(target=self.transcribe, daemon=True).start()

    def _stop_recording(self):
        self.is_recording = False
        if self.record_proc:
            self.record_proc.terminate()
            try:
                self.record_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.record_proc.kill()
            self.record_proc = None

    def transcribe(self):
        try:
            key = os.environ.get("GROQ_API_KEY")
            if not key:
                GLib.idle_add(lambda: self._to_idle("GROQ_API_KEY not set"))
                return
            r = subprocess.run([
                "curl", "-s", "-X", "POST",
                "https://api.groq.com/openai/v1/audio/transcriptions",
                "-H", f"Authorization: Bearer {key}",
                "-F", f"file=@{self.audio_file}",
                "-F", "model=whisper-large-v3-turbo",
                "-F", "temperature=0",
                "response_format=json"
            ], capture_output=True, text=True, timeout=30)
            log(f"Whisper raw: {r.stdout[:200]}")
            data = json.loads(r.stdout)
            text = data.get("text") or ""
            log(f"Transcribed: '{text}'")
            GLib.idle_add(lambda t=text: self._to_idle(t.strip() if t else ""))
        except Exception as e:
            log(f"Transcribe error: {e}")
            GLib.idle_add(lambda: self._to_idle(""))
            GLib.idle_add(lambda: self._entry_set_placeholder("Transcription failed"))

    def _to_idle(self, text=""):
        # Reset recording controls
        self.x_btn.set_visible(True)
        self.check_btn.set_visible(True)
        self.orb_spinner.set_visible(False)
        self.orb_spinner.stop()
        
        self.action_stack.set_visible_child_name("idle")
        self.entry.set_editable(True)
        self._entry_set_placeholder("Ask anything...")
        if text:
            log(f"Setting text: '{text}'")
            self._entry_set_text(text)
        self.entry.grab_focus()
        self.force_shrink()

    # --- Chat ---

    def on_ask(self):
        text = self._entry_get_text().strip()
        if not text:
            return
        self.add_message("user", text)
        self._entry_set_text("")
        self.entry.set_editable(False)
        self._entry_set_placeholder("AI is thinking...")
        self.action_stack.set_visible_child_name("thinking")
        threading.Thread(target=self.query_ai, args=(text,), daemon=True).start()

    def query_ai(self, text):
        try:
            key = os.environ.get("GROQ_API_KEY")
            if not key:
                GLib.idle_add(lambda: self.add_message("ai", "GROQ_API_KEY not set"))
                return
            # Added a system role message instructing the AI to keep responses short and brief
            payload = json.dumps({
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant. Keep your responses extremely short, brief, and concise."},
                    {"role": "user", "content": text}
                ],
                "model": "qwen/qwen3.6-27b",
                "temperature": 0.6,
                "max_completion_tokens": 4096,
                "top_p": 0.95,
                "stream": False,
                "reasoning_effort": "default",
                "stop": None
            })
            r = subprocess.run([
                "curl", "-s", "-X", "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                "-H", "Content-Type: application/json",
                "-H", f"Authorization: Bearer {key}",
                "-d", payload
            ], capture_output=True, text=True, timeout=120)
            data = json.loads(r.stdout)
            content = data["choices"][0]["message"]["content"]
            import re
            content = re.sub(r'<think>.*?(?:</think>|$)', '', content, flags=re.DOTALL).strip()
            GLib.idle_add(lambda: self.add_message("ai", content))
        except Exception as e:
            log(f"AI: {e}")
            GLib.idle_add(lambda: self.add_message("ai", "Query failed."))
        finally:
            GLib.idle_add(self._reset_chat)

    def _reset_chat(self):
        self.action_stack.set_visible_child_name("idle")
        self.entry.set_editable(True)
        self._entry_set_placeholder("Ask anything...")
        self.entry.grab_focus()
        self.force_shrink()

    def add_message(self, role, text):
        self.chat_history.append((role, text))
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row.set_margin_top(4)
        row.set_margin_bottom(4)
        if role == "user":
            row.set_halign(Gtk.Align.END)
            row.set_margin_start(60)
        else:
            row.set_halign(Gtk.Align.START)
            row.set_margin_end(60)
            
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        wrap.add_css_class("msg-wrap")
        wrap.add_css_class(role)
        
        lbl = Gtk.Label(label=text)
        lbl.set_wrap(True)
        lbl.set_selectable(True)
        lbl.set_xalign(1.0 if role == "user" else 0.0)
        lbl.add_css_class("msg-label")
        
        wrap.append(lbl)
        row.append(wrap)
        self.history_box.append(row)
        row.set_visible(True)
        
        self.scroll_to_bottom()
        self.force_shrink()

    def scroll_to_bottom(self):
        GLib.idle_add(self._do_scroll)

    def _do_scroll(self):
        adj = self.scrolled.get_vadjustment()
        if adj:
            adj.set_value(adj.get_upper() - adj.get_page_size())
        return False

    # --- Orb animation ---

    def animate_orb(self):
        try:
            state = self.action_stack.get_visible_child_name()
            if state != "recording":
                return True
            
            # Animate faster when transcribing (indicated by the overlay spinner being visible)
            is_processing = self.orb_spinner.get_visible()
            
            dt = 0.033
            if is_processing:
                self.breath += dt * 2.5
                speed_multiplier = 4.5
                b = 0.5 + 0.5 * math.sin(self.breath)
                self.arc_angle = (self.arc_angle + 12) % 360  # Spin fast!
            else:
                self.breath += dt * 0.6
                speed_multiplier = 1.0
                b = 0.7 + 0.3 * math.sin(self.breath)
                self.arc_angle = (self.arc_angle + 2) % 360  # Spin slowly!
                
            sb = 0.8 + b * 1.2
            for i in range(5):
                self.angles[i] = (self.angles[i] + self.speeds[i] * sb * speed_multiplier) % 360
            for i in range(3):
                self.stops[i] += (10.0 + b * 20 - self.stops[i]) * 0.05
            self.shimmer_stop += (8.0 + b * 22 - self.shimmer_stop) * 0.05

            def g(angle, color, stop):
                fs = stop + 8.0  # Sharper gradients for 40px boundaries
                f_color = color.replace('0.7', '0.1').replace('0.6', '0.1').replace('0.5', '0.05')
                return f"linear-gradient({angle}deg, {color} 0%, {color} {stop}%, {f_color} {stop}%, {f_color} {fs}%, transparent {fs}%)"
            
            if is_processing:
                red_color = 'rgba(255, 59, 48, 0.5)'
                purple_color = 'rgba(175, 82, 222, 0.7)'
                blue_color = 'rgba(0, 122, 255, 0.8)'
            else:
                red_color = 'rgba(255, 59, 48, 0.7)'
                purple_color = 'rgba(175, 82, 222, 0.6)'
                blue_color = 'rgba(0, 122, 255, 0.5)'
                
            css = (
                f"#or {{ background: {g(self.angles[0], red_color, self.stops[0])}; border-radius:50%; filter:blur(3px); }}\n"
                f"#op {{ background: {g(self.angles[1], purple_color, self.stops[1])}; border-radius:50%; filter:blur(5px); }}\n"
                f"#ob {{ background: {g(self.angles[2], blue_color, self.stops[2])}; border-radius:50%; filter:blur(7px); }}\n"
                f"#os {{ background: linear-gradient({self.angles[4]}deg, rgba(255,255,255,0.7) 0%, transparent {self.shimmer_stop}%); border-radius:50%; opacity:0.6; filter:blur(2px); }}\n"
                f"#oc {{ background-color:#ffffff; border-radius:50%; }}\n"
                f"#oa {{ "
                f"border-radius:50%; "
                f"border:2px solid transparent; "
                f"border-top-color:#ffffff; "
                f"border-right-color:rgba(255,255,255,0.45); "
                f"border-bottom-color:transparent; "
                f"border-left-color:rgba(255,255,255,0.15); "
                f"transform:rotate({self.arc_angle}deg); "
                f"opacity:{'1.0' if is_processing else '0.4'}; "
                f"}}\n"
            ).encode()
            self.orb_css.load_from_data(css)
        except Exception:
            pass
        return True

    def jiggle_speeds(self):
        for i in range(5):
            self.speeds[i] += random.uniform(-0.3, 0.3)
            self.speeds[i] = max(-2.0, min(2.0, self.speeds[i]))
        return True


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.openclaw.dictate.ai_chat")

    def do_activate(self):
        w = AIChatWindow(self)
        w.present()


if __name__ == "__main__":
    load_env()
    app = App()
    app.run(None)
