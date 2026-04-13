import os
import subprocess

def convert_to_wav(input_path):
    """Convert any audio to proper 16kHz mono WAV for Whisper."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    if os.path.exists(output_path):
        return output_path
    try:
        subprocess.run([
            "ffmpeg", "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-sample_fmt", "s16",
            "-y", output_path
        ], check=True, capture_output=True)
        print(f"Converted to WAV: {output_path}")
        return output_path
    except Exception as e:
        print(f"ffmpeg conversion failed: {e}. Using original.")
        return input_path

def ensure_proper_wav(input_path):
    """Re-encode WAV to fix browser recording format issues."""
    output_path = input_path.replace(".wav", "_fixed.wav")
    if "_fixed" in input_path or "_converted" in input_path:
        return input_path
    if os.path.exists(output_path):
        return output_path
    try:
        subprocess.run([
            "ffmpeg", "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-sample_fmt", "s16",
            "-acodec", "pcm_s16le",
            "-y", output_path
        ], check=True, capture_output=True)
        print(f"Fixed WAV: {output_path}")
        return output_path
    except Exception as e:
        print(f"WAV fix skipped: {e}")
        return input_path