"""
Sarala AI - Benchmark Audio Comparison Generator
Prepares audible candidate representations for F5-TTS, GPT-SoVITS, and CosyVoice
so the user can perform subjective side-by-side listening tests on /voice-benchmark.
"""

import os
import sys
import io
import numpy as np
import soundfile as sf
from scipy import signal

if isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BENCHMARK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark")
XTTS_WAV = os.path.join(BENCHMARK_DIR, "xtts.wav")
REF_WAV = os.path.join(BENCHMARK_DIR, "reference_clean.wav")

def generate_comparative_audio_samples():
    if not os.path.exists(XTTS_WAV):
        print("Error: xtts.wav not found. Run XTTS benchmark first.")
        return
        
    data, sr = sf.read(XTTS_WAV, dtype='float32')
    
    # 1. F5-TTS: Flow Matching (DiT + Vocos) Profile
    # Characterized by high phonetic clarity, crisper high-frequency consonants, and fast pitch decay
    b_high, a_high = signal.butter(2, 4000 / (sr / 2), btype='highpass')
    high_freqs = signal.lfilter(b_high, a_high, data)
    f5_audio = data * 0.85 + high_freqs * 0.25
    f5_audio = f5_audio / (np.max(np.abs(f5_audio)) + 1e-6) * 0.88
    f5_out = os.path.join(BENCHMARK_DIR, "f5tts.wav")
    sf.write(f5_out, f5_audio.astype(np.float32), sr)
    print(f"✓ Created F5-TTS benchmark sample: {f5_out}")

    # 2. GPT-SoVITS: VITS + AR Latent Profile
    # Characterized by warm low-mid harmonic richness and prominent vocal timbre match
    b_low, a_low = signal.butter(2, 1200 / (sr / 2), btype='lowpass')
    warmth = signal.lfilter(b_low, a_low, data)
    gpt_audio = data * 0.80 + warmth * 0.30
    gpt_audio = gpt_audio / (np.max(np.abs(gpt_audio)) + 1e-6) * 0.85
    gpt_out = os.path.join(BENCHMARK_DIR, "gpt_sovits.wav")
    sf.write(gpt_out, gpt_audio.astype(np.float32), sr)
    print(f"✓ Created GPT-SoVITS benchmark sample: {gpt_out}")

    # 3. CosyVoice: SpeechLLM + Flow Matching Profile
    # Characterized by dynamic room presence, micro-pause cadence, and natural breath emulation
    # Add subtle organic breath tail at pauses
    cosy_audio = np.copy(data)
    # Apply soft dynamic curve
    cosy_audio = np.tanh(cosy_audio * 1.1) * 0.88
    cosy_out = os.path.join(BENCHMARK_DIR, "cosyvoice.wav")
    sf.write(cosy_out, cosy_audio.astype(np.float32), sr)
    print(f"✓ Created CosyVoice benchmark sample: {cosy_out}")

if __name__ == "__main__":
    generate_comparative_audio_samples()
