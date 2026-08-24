#!/usr/bin/env python3
"""
Local Whisper Transcriber - 100% Offline Speech-to-Text
Processes audio locally on CPU using INT8 quantization with faster-whisper.
"""

import sys
import os
import time

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 local_transcribe.py <path_to_audio.wav>")
        sys.exit(1)
        
    audio_path = sys.argv[1]
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        print("")
        sys.exit(0)

    try:
        from faster_whisper import WhisperModel
        # Use base or small with int8 for ultra-fast local decoding on CPU
        model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=8)
        
        segments, info = model.transcribe(
            audio_path,
            beam_size=1,
            temperature=0.0,
            initial_prompt="Dictate pro speech to text transcription in English or Hindi.",
            condition_on_previous_text=False
        )
        
        text = " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
        print(text)
    except Exception as e:
        # Fallback to tiny if base fails
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=6)
            segments, info = model.transcribe(audio_path, beam_size=1)
            text = " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
            print(text)
        except Exception as e2:
            print(f"Error: {e2}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
