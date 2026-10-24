#!/usr/bin/env python3
"""
Groq Whisper Audio Transcriber
- Sends the entire audio at the end in a single request.
- If audio exceeds 24MB, automatically compresses via ffmpeg.
- If audio still exceeds API limits (marathon dictations), appropriately chunks and stitches the segments.
"""

import os
import sys
import json
import subprocess
import tempfile
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "dictate.config.json")
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MAX_GROQ_BYTES = 24 * 1024 * 1024  # 24 MB safety threshold (Groq limit is 25 MB)

def load_api_key():
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GROQ_API_KEY="):
                        val = line.split("=", 1)[1].strip()
                        return val.strip("\"'")
        except Exception:
            pass
    return None

def load_config():
    config = {
        "groq_model": "whisper-large-v3-turbo",
        "language": "auto",
        "temperature": 0.0
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
                config.update(data)
        except Exception:
            pass
    return config

def transcribe_single_file(file_path, api_key, model, language="auto", temperature=0.0):
    """Sends a single audio file to Groq API and returns the transcribed text."""
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model,
        "temperature": str(temperature),
        "response_format": "json"
    }
    if language and language != "auto":
        data["language"] = language

    filename = os.path.basename(file_path)
    mime_type = "audio/wav"
    if file_path.endswith(".mp3"):
        mime_type = "audio/mpeg"
    elif file_path.endswith(".m4a"):
        mime_type = "audio/m4a"
    elif file_path.endswith(".ogg"):
        mime_type = "audio/ogg"

    with open(file_path, "rb") as f:
        files = {
            "file": (filename, f, mime_type)
        }
        resp = requests.post(GROQ_API_URL, headers=headers, files=files, data=data, timeout=180)

    if resp.status_code == 200:
        res_json = resp.json()
        return res_json.get("text", "").strip()
    else:
        err_msg = f"Groq API Error ({resp.status_code})"
        try:
            err_data = resp.json()
            if "error" in err_data and "message" in err_data["error"]:
                err_msg = err_data["error"]["message"]
        except Exception:
            err_msg = resp.text or err_msg
        raise RuntimeError(err_msg)

def compress_audio(input_wav, output_mp3):
    """Compresses WAV to high-quality mono MP3 using ffmpeg to drastically reduce file size."""
    cmd = [
        "ffmpeg", "-y", "-i", input_wav,
        "-vn", "-ac", "1", "-ar", "16000",
        "-b:a", "64k",
        output_mp3
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def chunk_audio(input_file, output_pattern, chunk_seconds=600):
    """Splits audio into segments of chunk_seconds length."""
    cmd = [
        "ffmpeg", "-y", "-i", input_file,
        "-f", "segment",
        "-segment_time", str(chunk_seconds),
        "-c", "copy",
        output_pattern
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 groq_transcribe.py <path_to_audio.wav>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        # File missing or smaller than 1KB (essentially empty / silent)
        sys.exit(0)

    api_key = load_api_key()
    if not api_key:
        print("GROQ_API_KEY not found in environment or .env file", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    model = config.get("groq_model", "whisper-large-v3-turbo")
    language = config.get("language", "auto")
    temperature = config.get("temperature", 0.0)

    file_size = os.path.getsize(audio_path)
    temp_files = []

    try:
        # Case 1: Audio fits within Groq limit (<= 24 MB) -> Send whole audio at end
        if file_size <= MAX_GROQ_BYTES:
            text = transcribe_single_file(audio_path, api_key, model, language, temperature)
            print(text)
            return

        # Case 2: Audio > 24 MB -> First attempt MP3 compression (reduces size ~85%)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
            compressed_path = tmp_mp3.name
            temp_files.append(compressed_path)

        try:
            compress_audio(audio_path, compressed_path)
            compressed_size = os.path.getsize(compressed_path)
        except Exception as e:
            compressed_size = file_size
            compressed_path = audio_path

        # If compressed audio is within limit, send the whole compressed audio file at end
        if compressed_size <= MAX_GROQ_BYTES:
            text = transcribe_single_file(compressed_path, api_key, model, language, temperature)
            print(text)
            return

        # Case 3: Still > 24 MB (extreme marathon dictation > 1 hour) -> Chunk appropriately
        chunk_dir = tempfile.mkdtemp(prefix="dictate_chunks_")
        chunk_pattern = os.path.join(chunk_dir, "chunk_%03d.mp3")
        chunk_audio(compressed_path, chunk_pattern, chunk_seconds=600)  # 10-minute segments

        chunks = sorted([os.path.join(chunk_dir, f) for f in os.listdir(chunk_dir) if f.startswith("chunk_")])
        transcribed_parts = []

        for chunk in chunks:
            part_text = transcribe_single_file(chunk, api_key, model, language, temperature)
            if part_text:
                transcribed_parts.append(part_text)
            try:
                os.remove(chunk)
            except Exception:
                pass

        try:
            os.rmdir(chunk_dir)
        except Exception:
            pass

        full_text = " ".join(transcribed_parts).strip()
        print(full_text)

    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    finally:
        for tmp in temp_files:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

if __name__ == "__main__":
    main()
