import os
import warnings
import torch
import whisperx
import warnings
warnings.filterwarnings("ignore", message="torchcodec is not installed")
warnings.filterwarnings("ignore", message="In 2.9, this function")

DEVICE       = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float32"
HF_TOKEN     = os.getenv("HUGGINGFACE_TOKEN")

_model = None

def _get_model():
    global _model
    if _model is None:
        print("Loading WhisperX model...")
        _model = whisperx.load_model(
            "small",
            DEVICE,
            compute_type=COMPUTE_TYPE,
            language="en"
        )
        print("WhisperX model loaded ✅")
    return _model


def transcribe_audio(audio_path, use_diarization=True):
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"Transcribing: {audio_path}")
    model  = _get_model()
    audio  = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=4)
    print(f"Transcription done. {len(result['segments'])} segments.")

    # Alignment
    try:
        align_model, metadata = whisperx.load_align_model(
            language_code=result["language"],
            device=DEVICE
        )
        result = whisperx.align(
            result["segments"], align_model,
            metadata, audio, DEVICE,
            return_char_alignments=False
        )
        print("Alignment done ✅")
    except Exception as e:
        print(f"Alignment skipped: {e}")

    # Diarization
    if use_diarization and HF_TOKEN:
        try:
            print("Running diarization...")
            from pyannote.audio import Pipeline as PyannotePipeline
            import torch

            diarize_pipeline = PyannotePipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=HF_TOKEN
            )
            diarize_pipeline = diarize_pipeline.to(torch.device(DEVICE))

            import torchaudio
            waveform, sample_rate = torchaudio.load(audio_path)
            audio_dict = {"waveform": waveform, "sample_rate": sample_rate}

            diarization = diarize_pipeline(audio_dict, min_speakers=2, max_speakers=2)

            # Convert pyannote output to whisperx-compatible format
            diarize_segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                diarize_segments.append({
                    "start":   round(turn.start, 2),
                    "end":     round(turn.end,   2),
                    "speaker": speaker
                })

            # Assign speakers to transcript segments by time overlap
            segments = result["segments"] if "segments" in result else result
            final    = _assign_speakers(segments, diarize_segments)
            print("Diarization done ✅")
            return final

        except Exception as e:
            print(f"Diarization failed: {e}. Using alternating fallback.")

    segments = result["segments"] if "segments" in result else result
    return _build_segments_fallback(segments)


def _assign_speakers(transcript_segments, diarize_segments):
    """Match transcript segments to speakers using time midpoint."""
    speaker_map = {}
    role_labels = ["DOCTOR", "PATIENT", "SPEAKER_3", "SPEAKER_4"]
    result      = []

    for seg in transcript_segments:
        mid         = (seg.get("start", 0) + seg.get("end", 0)) / 2
        best_speaker = None
        best_overlap = -1

        for d in diarize_segments:
            if d["start"] <= mid <= d["end"]:
                overlap = d["end"] - d["start"]
                if overlap > best_overlap:
                    best_overlap  = overlap
                    best_speaker  = d["speaker"]

        raw = best_speaker or "SPEAKER_00"
        if raw not in speaker_map:
            idx = len(speaker_map)
            speaker_map[raw] = role_labels[idx] if idx < len(role_labels) else raw

        role = speaker_map[raw]
        result.append({
            "start":      round(seg.get("start", 0), 2),
            "end":        round(seg.get("end",   0), 2),
            "text":       seg.get("text", "").strip(),
            "speaker":    role,
            "confidence": 0.95
        })
        print(f"  [{role}] {seg.get('start',0):.1f}s: {seg.get('text','').strip()}")

    print(f"Speaker mapping: {speaker_map}")
    return result


def _build_segments_fallback(segments):
    """Strictly alternate DOCTOR / PATIENT."""
    print("Using alternating speaker fallback.")
    result = []
    for i, seg in enumerate(segments):
        role = "DOCTOR" if i % 2 == 0 else "PATIENT"
        result.append({
            "start":      round(seg.get("start", 0), 2),
            "end":        round(seg.get("end",   0), 2),
            "text":       seg.get("text", "").strip(),
            "speaker":    role,
            "confidence": 0.95
        })
        print(f"  [{role}] {seg.get('start',0):.1f}s: {seg.get('text','').strip()}")
    return result