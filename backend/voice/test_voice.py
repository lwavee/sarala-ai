"""
Sarala AI - Voice Cloning Test & Benchmark Script
=================================================
Validates the XTTS-v2 local voice cloning pipeline by generating both Hindi
and English test utterances and verifying audio quality metrics (RMS, peak, duration).

Outputs:
- backend/voice/output/sarala_test_hi.wav
- backend/voice/output/sarala_test_en.wav
- backend/voice/voice_test_report.json
"""

import os
import sys
import time
import json
import logging
import io
from pathlib import Path

# Fix Windows console UTF-8 output for Hindi text
if isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if isinstance(sys.stderr, io.TextIOWrapper):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Ensure non-interactive acceptance
os.environ["COQUI_TOS_AGREED"] = "1"

# Add backend directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from voice.xtts_engine import XTTSVoiceEngine, DEFAULT_REF_WAV, OUTPUT_DIR

TEST_CASES = [
    {
        "id": "hindi_greeting",
        "language": "hi",
        "text": "नमस्ते, मैं सरला हूँ। आज मैं आपके साथ कुछ नया सीखने वाली हूँ।",
        "filename": "sarala_test_hi.wav"
    },
    {
        "id": "english_intro",
        "language": "en",
        "text": "Hello, I am Sarala. This is my local AI voice running completely offline.",
        "filename": "sarala_test_en.wav"
    }
]


def analyze_audio_quality(wav_path: Path) -> dict:
    """Computes technical audio telemetry (duration, sample rate, RMS, peak amplitude)."""
    import soundfile as sf
    import numpy as np

    data, samplerate = sf.read(str(wav_path))
    if data.ndim > 1:
        data = data.mean(axis=1)

    duration = len(data) / samplerate
    rms = float(np.sqrt(np.mean(data ** 2)))
    peak = float(np.max(np.abs(data)))
    
    # Estimate silence ratio (samples below -40 dBFS)
    silence_threshold = 0.01
    silence_ratio = float(np.mean(np.abs(data) < silence_threshold))

    return {
        "duration_seconds": round(duration, 3),
        "sample_rate": samplerate,
        "rms_energy": round(rms, 4),
        "peak_amplitude": round(peak, 4),
        "silence_ratio": round(silence_ratio, 4),
        "file_size_bytes": wav_path.stat().st_size
    }


def run_voice_tests():
    print("=" * 60)
    print("Sarala AI - Local Voice Cloning Benchmark (XTTS-v2 CPU)")
    print("=" * 60)

    engine = XTTSVoiceEngine()
    print(f"[*] Default reference audio: {DEFAULT_REF_WAV}")
    print(f"[*] Reference available: {engine.is_reference_available()}")
    
    if not engine.is_reference_available():
        print(f"[!] ERROR: Reference audio not found at {DEFAULT_REF_WAV}")
        sys.exit(1)

    print("\n[1/3] Loading XTTS-v2 model onto CPU...")
    t0 = time.time()
    engine.load_model()
    load_time = time.time() - t0
    print(f"[+] Model loaded in {load_time:.2f}s.\n")

    results = []
    print("[2/3] Generating test speech samples...")
    for idx, tc in enumerate(TEST_CASES, start=1):
        print(f"\n--- Test Case {idx}: [{tc['language'].upper()}] {tc['id']} ---")
        print(f"Text: '{tc['text']}'")
        
        t_synth = time.time()
        res = engine.synthesize(
            text=tc["text"],
            language=tc["language"],
            output_filename=tc["filename"]
        )
        synth_latency = time.time() - t_synth

        if not res["success"]:
            print(f"[!] FAILED: {res.get('error')}")
            results.append({
                "test_id": tc["id"],
                "language": tc["language"],
                "success": False,
                "error": res.get("error")
            })
            continue

        wav_file = Path(res["file_path"])
        telemetry = analyze_audio_quality(wav_file)

        print(f"[+] Successfully generated: {wav_file.name}")
        print(f"    - Synthesis Latency: {synth_latency:.2f}s")
        print(f"    - Audio Duration:    {telemetry['duration_seconds']}s")
        print(f"    - Sample Rate:       {telemetry['sample_rate']} Hz")
        print(f"    - RMS Energy:        {telemetry['rms_energy']}")
        print(f"    - Peak Amplitude:    {telemetry['peak_amplitude']}")

        # Real-time factor (RTF = latency / audio_duration)
        rtf = round(synth_latency / telemetry['duration_seconds'], 2) if telemetry['duration_seconds'] > 0 else 0
        print(f"    - Real-Time Factor:  {rtf}x")

        results.append({
            "test_id": tc["id"],
            "language": tc["language"],
            "text": tc["text"],
            "success": True,
            "filename": tc["filename"],
            "latency_seconds": round(synth_latency, 2),
            "real_time_factor": rtf,
            "telemetry": telemetry
        })

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": {
            "device": "cpu",
            "model": "tts_models/multilingual/multi-dataset/xtts_v2",
            "model_load_time_seconds": round(load_time, 2)
        },
        "reference_sample": str(DEFAULT_REF_WAV),
        "results": results
    }

    report_path = SCRIPT_DIR / "voice_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"[3/3] Benchmark Complete! Report saved to: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    run_voice_tests()
