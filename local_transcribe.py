#!/usr/bin/env python3
"""
Local Whisper Transcriber - GPU Hardware Accelerated (AMD Radeon RX 5500M VRAM via Vulkan)
Supports short & long multi-minute recordings with zero truncation.
"""

import sys
import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_PATH = os.path.join(SCRIPT_DIR, "bin", "whisper-cli")
MODEL_PATH = os.path.join(SCRIPT_DIR, "models", "ggml-large-v3-turbo-q5_0.bin")

def transcribe_gpu(audio_path):
    """Runs whisper-cli with Vulkan acceleration on AMD Radeon RX 5500M (Device 1)."""
    if not os.path.exists(BIN_PATH) or not os.path.exists(MODEL_PATH):
        return None

    cmd = [
        BIN_PATH,
        "--model", MODEL_PATH,
        "--file", audio_path,
        "--device", "1", # Dedicated AMD Radeon RX 5500M GPU
        "--threads", "6",
        "--language", "auto",
        "--beam-size", "1",
        "--suppress-nst",
        "--no-timestamps",
        "--split-on-word",
        "--max-len", "0"
    ]

    try:
        # Generous 180s timeout for long multi-minute voice recordings
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180
        )
        if res.returncode == 0:
            lines = res.stdout.strip().split('\n')
            clean_lines = []
            for line in lines:
                l = line.strip()
                if not l or l.startswith("ggml_") or l.startswith("whisper_") or l.startswith("system_info") or l.startswith("main:") or l.startswith("read_audio"):
                    continue
                clean_lines.append(l)
            text = " ".join(clean_lines).strip()
            return text
    except subprocess.TimeoutExpired:
        print("GPU transcription timed out.", file=sys.stderr)
    except Exception as e:
        print(f"GPU transcribe error: {e}", file=sys.stderr)
    return None

def transcribe_cpu_fallback(audio_path):
    """Fallback to CPU faster-whisper if GPU is unavailable."""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=8)
        segments, _ = model.transcribe(audio_path, beam_size=1)
        return " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
    except Exception as e:
        print(f"CPU fallback error: {e}", file=sys.stderr)
        return ""

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 local_transcribe.py <path_to_audio.wav>")
        sys.exit(1)
        
    audio_path = sys.argv[1]
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        print("")
        sys.exit(0)

    # 1. Try Hardware GPU acceleration (AMD Radeon RX 5500M VRAM)
    text = transcribe_gpu(audio_path)
    
    # 2. Fallback to CPU if needed
    if text is None or not text:
        text = transcribe_cpu_fallback(audio_path)

    print(text or "")

if __name__ == "__main__":
    main()
