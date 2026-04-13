# Diarization is now handled inside transcription_service.py via WhisperX.
# This file is kept as a placeholder.

def diarize_audio(audio_path, num_speakers=2):
    return []

def merge_transcript_with_diarization(transcript_segments, diarization_segments):
    return transcript_segments

def _alternating_fallback(transcript_segments):
    result = []
    for i, seg in enumerate(transcript_segments):
        role = "DOCTOR" if i % 2 == 0 else "PATIENT"
        result.append({**seg, "speaker": role})
    return result