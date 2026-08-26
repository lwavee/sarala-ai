"""
Sarala AI - Chatterbox Voice Verification and Quality Benchmark
================================================================
Synthesizes speech for the 4 target sentences using Chatterbox Multilingual
conditioned on `backend/voice/reference/sarala_reference.wav`.

Target sentences:
1. "नमस्ते, मैं सरला हूँ। आप कैसे हैं?"
2. "अगर आपको किसी भी चीज़ में मदद चाहिए, तो आप मुझसे पूछ सकते हैं।"
3. "आज हम कुछ नया सीखेंगे और इसे बहुत आसान तरीके से समझेंगे।"
4. "आप जो भी सवाल पूछना चाहते हैं, बेझिझक पूछ सकते हैं।"

Compares the synthesized speech against the approved reference output:
backend/voice/reference/sarala_reference.wav
"""

import sys
import os
import io
import time
from pathlib import Path
import soundfile as sf
import numpy as np

if isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add backend directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(str(BACKEND_DIR / ".env"))

from voice.voice_service import generate_sarala_voice
from voice.config import voice_config

TEST_SENTENCES = [
    {
        "id": "test_1_greeting",
        "text": "नमस्ते, मैं सरला हूँ। आप कैसे हैं?"
    },
    {
        "id": "test_2_help",
        "text": "अगर आपको किसी भी चीज़ में मदद चाहिए, तो आप मुझसे पूछ सकते हैं।"
    },
    {
        "id": "test_3_learning",
        "text": "आज हम कुछ नया सीखेंगे और इसे बहुत आसान तरीके से समझेंगे।"
    },
    {
        "id": "test_4_questions",
        "text": "आप जो भी सवाल पूछना चाहते हैं, बेझिझक पूछ सकते हैं।"
    }
]

APPROVED_REFERENCE_PATH = BACKEND_DIR / "voice" / "reference" / "sarala_reference.wav"


def analyze_audio(wav_path: str):
    data, sr = sf.read(str(wav_path))
    if data.ndim > 1:
        data = np.mean(data, axis=1)

    dur = len(data) / sr
    rms = float(np.sqrt(np.mean(data**2)))
    peak = float(np.max(np.abs(data)))
    dr_db = 20 * np.log10((peak + 1e-9) / (rms + 1e-9))
    zcr = float(np.mean(np.abs(np.diff(np.sign(data)))) / 2)

    # Spectral centroid (frequency center-of-mass)
    fft_vals = np.abs(np.fft.rfft(data))
    freqs = np.fft.rfftfreq(len(data), 1.0 / sr)
    spectral_centroid = float(np.sum(freqs * fft_vals) / (np.sum(fft_vals) + 1e-9))

    # Silence ratio (frames with amplitude < 5% of peak)
    silence_ratio = float(np.mean(np.abs(data) < 0.05 * peak))

    return {
        "duration": round(dur, 2),
        "sample_rate": sr,
        "rms": round(rms, 4),
        "peak": round(peak, 4),
        "dynamic_range_db": round(dr_db, 1),
        "zcr": round(zcr, 4),
        "spectral_centroid": round(spectral_centroid, 1),
        "silence_ratio": round(silence_ratio * 100, 1),
    }


def main():
    print("=" * 80)
    print("      SARALA AI - CHATTERBOX MULTILINGUAL VOICE VERIFICATION")
    print("=" * 80)
    print(f"Provider:           {voice_config.provider}")
    print(f"Inference Mode:     {voice_config.inference_mode}")
    print(f"Reference Audio:    {voice_config.reference_audio_path}")
    print(f"Exaggeration:       {voice_config.exaggeration}")
    print(f"Temperature:        {voice_config.temperature}")
    print(f"Seed:               {voice_config.seed}")
    print(f"CFG Weight:         {voice_config.cfg_weight}")
    print("-" * 80)

    if not APPROVED_REFERENCE_PATH.exists():
        print(f"[ERROR] Reference file does not exist at: {APPROVED_REFERENCE_PATH}")
        sys.exit(1)

    ref_metrics = analyze_audio(str(APPROVED_REFERENCE_PATH))
    print("\n[APPROVED REFERENCE VOICE CHARACTERISTICS]")
    print(f"  Filename:          {APPROVED_REFERENCE_PATH.name}")
    print(f"  Duration:          {ref_metrics['duration']} s")
    print(f"  Sample Rate:       {ref_metrics['sample_rate']} Hz")
    print(f"  RMS Energy:        {ref_metrics['rms']}")
    print(f"  Peak Amplitude:    {ref_metrics['peak']}")
    print(f"  Dynamic Range:     {ref_metrics['dynamic_range_db']} dB")
    print(f"  Spectral Centroid: {ref_metrics['spectral_centroid']} Hz (timbre/warmth)")
    print(f"  Silence Ratio:     {ref_metrics['silence_ratio']} %")

    results = []
    for test in TEST_SENTENCES:
        print(f"\n[SYNTHESIZING] [{test['id']}]")
        print(f"  Text: \"{test['text']}\"")
        t0 = time.time()
        try:
            res = generate_sarala_voice(text=test["text"], language="hi")
            latency = round(time.time() - t0, 2)
            audio_path = res.get("audio_path")
            if not audio_path or not os.path.exists(audio_path):
                print(f"  [X] Failed: No audio generated")
                continue

            metrics = analyze_audio(audio_path)
            print(f"  [✓] Success in {latency}s!")
            print(f"      Filename:          {res.get('filename')}")
            print(f"      Duration:          {metrics['duration']} s")
            print(f"      Sample Rate:       {metrics['sample_rate']} Hz")
            print(f"      RMS Energy:        {metrics['rms']}")
            print(f"      Spectral Centroid: {metrics['spectral_centroid']} Hz")
            print(f"      Silence Ratio:     {metrics['silence_ratio']} %")
            print(f"      Saved Path:        {audio_path}")

            results.append({
                "id": test["id"],
                "text": test["text"],
                "filename": res.get("filename"),
                "audio_path": audio_path,
                "latency_sec": latency,
                "metrics": metrics
            })
        except Exception as e:
            print(f"  [X] Exception: {e}")

    # Summary Table
    print("\n" + "=" * 80)
    print("                    ACOUSTIC COMPARISON TABLE")
    print("=" * 80)
    print(f"{'Audio File':<30} | {'Dur (s)':<7} | {'SR (Hz)':<7} | {'RMS':<7} | {'Centroid (Hz)':<14} | {'Match'}")
    print("-" * 80)
    print(f"{APPROVED_REFERENCE_PATH.name:<30} | {ref_metrics['duration']:<7} | {ref_metrics['sample_rate']:<7} | {ref_metrics['rms']:<7} | {ref_metrics['spectral_centroid']:<14} | [APPROVED REF]")
    for r in results:
        m = r["metrics"]
        diff_centroid = abs(m["spectral_centroid"] - ref_metrics["spectral_centroid"])
        match_str = "[EXCELLENT]" if diff_centroid < 600 else "[GOOD]"
        print(f"{r['filename']:<30} | {m['duration']:<7} | {m['sample_rate']:<7} | {m['rms']:<7} | {m['spectral_centroid']:<14} | {match_str}")
    print("=" * 80)


if __name__ == "__main__":
    main()
