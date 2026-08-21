"""
Sarala AI - Voice Preprocessing Utility
Converts, cleans, normalizes, and extracts the optimal reference audio for Sarala AI Voice Engine.
NEVER modifies original files in assets/voice.
"""

import os
import sys
import json
import shutil
import subprocess
import io
from typing import Tuple, List, Dict, Any, Optional

import numpy as np
import soundfile as sf

# Setup stdout for UTF-8 in Windows environments
if isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def get_ffmpeg_path() -> str:
    """
    Locates FFmpeg executable from system PATH, imageio_ffmpeg, or virtual environment.
    """
    # 1. System PATH
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg

    # 2. imageio_ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except ImportError:
        pass

    # 3. Virtual environment locations
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_binaries = os.path.join(base_dir, "venv", "Lib", "site-packages", "imageio_ffmpeg", "binaries")
    if os.path.exists(venv_binaries):
        for f in os.listdir(venv_binaries):
            if f.startswith("ffmpeg") and f.endswith(".exe"):
                return os.path.join(venv_binaries, f)

    return ""


def find_voice_assets_dir() -> str:
    """
    Finds the directory where raw Sarala voice recordings are stored.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "assets", "voice"),
        os.path.join(os.path.dirname(base_dir), "assets", "voice"),
        os.path.join(base_dir, "voice", "assets"),
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0])


def decode_audio_to_wav(file_path: str, ffmpeg_exe: str, target_sr: int = 22050) -> Tuple[np.ndarray, int]:
    """
    Decodes any audio file (wav, mp3, m4a, flac, ogg) to mono float32 PCM numpy array at target_sr.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".wav":
        try:
            data, sr = sf.read(file_path, dtype='float32')
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)  # Convert stereo/multi-channel to mono
            if sr != target_sr:
                try:
                    from scipy import signal
                    num_samples = int(len(data) * target_sr / sr)
                    resampled = signal.resample(data, num_samples)
                    if isinstance(resampled, tuple):
                        resampled = resampled[0]
                    data = np.asarray(resampled, dtype=np.float32)
                    sr = target_sr
                except ImportError:
                    # Linear interpolation fallback if scipy is not installed
                    duration = len(data) / sr
                    new_times = np.linspace(0, duration, int(duration * target_sr), endpoint=False)
                    old_times = np.linspace(0, duration, len(data), endpoint=False)
                    resampled = np.interp(new_times, old_times, data)
                    data = np.asarray(resampled, dtype=np.float32)
                    sr = target_sr
            return data, sr
        except Exception:
            pass  # Fallback to ffmpeg below

    if not ffmpeg_exe or not os.path.exists(ffmpeg_exe):
        raise RuntimeError(
            "FFmpeg executable is required to decode non-wav or complex audio files (.m4a, .mp3, .ogg, .flac). "
            "Please ensure imageio-ffmpeg is installed in venv or ffmpeg is on system PATH."
        )

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", file_path,
        "-f", "wav",
        "-ar", str(target_sr),
        "-ac", "1",
        "pipe:1"
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        err = proc.stderr.decode('utf-8', errors='ignore')
        raise RuntimeError(f"FFmpeg decoding failed for {os.path.basename(file_path)}: {err[:200]}")

    data, sr = sf.read(io.BytesIO(proc.stdout), dtype='float32')
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)
    return data.astype(np.float32), sr


def trim_silence(data: np.ndarray, sr: int, top_db: float = 30.0, pad_sec: float = 0.15) -> np.ndarray:
    """
    Removes leading and trailing silence while preserving natural breathing and speech transitions.
    """
    if len(data) == 0:
        return data

    frame_len = int(sr * 0.05)  # 50ms window
    if frame_len <= 0 or len(data) < frame_len:
        return data

    num_frames = len(data) // frame_len
    frames = data[:num_frames * frame_len].reshape(num_frames, frame_len)
    rms = np.sqrt(np.mean(frames**2, axis=1))

    max_rms = np.max(rms)
    if max_rms <= 1e-6:
        return data  # Silent audio

    threshold = max_rms * (10 ** (-top_db / 20.0))
    speech_indices = np.where(rms > threshold)[0]

    if len(speech_indices) == 0:
        return data

    pad_frames = int(pad_sec / 0.05)
    start_frame = max(0, speech_indices[0] - pad_frames)
    end_frame = min(num_frames, speech_indices[-1] + 1 + pad_frames)

    start_sample = start_frame * frame_len
    end_sample = min(len(data), end_frame * frame_len)

    return data[start_sample:end_sample]


def normalize_audio(data: np.ndarray, target_peak_db: float = -1.0) -> np.ndarray:
    """
    Normalizes audio peak to avoid clipping while preserving dynamic range.
    """
    peak = np.max(np.abs(data))
    if peak <= 1e-6:
        return data
    target_peak = 10 ** (target_peak_db / 20.0)
    gain = target_peak / peak
    # Avoid extreme amplification on very quiet noise
    gain = min(gain, 10.0)
    normalized = data * gain
    return np.clip(normalized, -1.0, 1.0).astype(np.float32)


def evaluate_audio_quality(data: np.ndarray, sr: int) -> Dict[str, Any]:
    """
    Evaluates audio characteristics: duration, RMS level, peak, dynamic range, and quality score.
    """
    duration = len(data) / sr
    if duration <= 0:
        return {"score": 0.0, "rms": 0.0, "peak": 0.0, "duration": 0.0, "status": "empty"}

    rms = float(np.sqrt(np.mean(data**2)))
    peak = float(np.max(np.abs(data)))

    # Frame-level analysis for active speech vs background noise
    frame_len = int(sr * 0.05)
    if len(data) >= frame_len:
        num_frames = len(data) // frame_len
        frames = data[:num_frames * frame_len].reshape(num_frames, frame_len)
        frame_rms = np.sqrt(np.mean(frames**2, axis=1))
        speech_frames = np.sum(frame_rms > (rms * 0.3))
        speech_ratio = float(speech_frames / num_frames)
    else:
        speech_ratio = 1.0

    # Score criteria:
    # 1. Adequate duration (ideal: 15s - 120s for cloning reference)
    # 2. Strong RMS presence (0.05 - 0.20)
    # 3. High speech activity ratio
    duration_score = min(duration / 30.0, 1.0) * 40.0
    energy_score = min(rms / 0.10, 1.0) * 30.0
    speech_score = speech_ratio * 30.0

    total_score = duration_score + energy_score + speech_score

    status = "clean"
    if duration < 3.0:
        status = "too_short"
        total_score *= 0.5
    elif rms < 0.02:
        status = "too_quiet"
        total_score *= 0.6

    return {
        "score": round(total_score, 2),
        "rms": round(rms, 4),
        "peak": round(peak, 4),
        "duration": round(duration, 2),
        "speech_ratio": round(speech_ratio, 2),
        "status": status
    }


def extract_best_reference_clip(
    data: np.ndarray,
    sr: int,
    min_duration: float = 10.0,
    target_duration: float = 24.0,
    max_duration: float = 30.0
) -> np.ndarray:
    """
    Extracts the cleanest, most continuous segment of speech for reference conditioning.
    """
    total_sec = len(data) / sr
    if total_sec <= max_duration:
        return data

    window_samples = int(target_duration * sr)
    step_samples = int(2.0 * sr)  # Slide by 2 seconds

    best_start = 0
    best_energy = -1.0

    for start in range(0, len(data) - window_samples, step_samples):
        segment = data[start:start + window_samples]
        energy = np.mean(segment**2)
        if energy > best_energy:
            best_energy = energy
            best_start = start

    return data[best_start:best_start + window_samples]


def preprocess_all_recordings(target_sr: int = 22050) -> bool:
    """
    Main preprocessing pipeline:
    1. Scans backend/assets/voice/
    2. Converts and cleans all recordings
    3. Selects optimal master reference clip
    4. Saves backend/voice/samples/sarala_reference.wav
    5. Saves backend/voice/reference_report.json
    """
    assets_dir = find_voice_assets_dir()
    base_voice_dir = os.path.dirname(os.path.abspath(__file__))
    samples_dir = os.path.join(base_voice_dir, "samples")
    os.makedirs(samples_dir, exist_ok=True)

    print("=" * 60)
    print("SARALA AI - VOICE DATA PREPROCESSING")
    print("=" * 60)
    print(f"Source Directory: {assets_dir}")

    ffmpeg_exe = get_ffmpeg_path()
    print(f"FFmpeg Available: {'Yes (' + ffmpeg_exe + ')' if ffmpeg_exe else 'No (WAV only)'}")
    print(f"Target Samples Dir: {samples_dir}")

    if not os.path.exists(assets_dir):
        print(f"\n[ERROR] Assets directory not found: {assets_dir}")
        return False

    supported_exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
    source_files = [
        f for f in os.listdir(assets_dir)
        if os.path.splitext(f)[1].lower() in supported_exts and not f.startswith(".")
    ]

    print(f"Found {len(source_files)} audio recording(s).\n")

    if not source_files:
        print(f"[WARNING] No audio recordings found in {assets_dir}")
        return False

    candidates = []
    file_reports = []

    for filename in sorted(source_files):
        file_path = os.path.join(assets_dir, filename)
        try:
            raw_audio, sr = decode_audio_to_wav(file_path, ffmpeg_exe, target_sr=target_sr)
            clean_audio = trim_silence(raw_audio, sr)
            norm_audio = normalize_audio(clean_audio)

            quality = evaluate_audio_quality(norm_audio, sr)

            record = {
                "filename": filename,
                "path": file_path,
                "sr": sr,
                "audio": norm_audio,
                "raw_duration": len(raw_audio) / sr,
                "clean_duration": quality["duration"],
                "rms": quality["rms"],
                "peak": quality["peak"],
                "score": quality["score"],
                "status": quality["status"]
            }
            candidates.append(record)

            file_reports.append({
                "filename": filename,
                "raw_duration_sec": round(len(raw_audio) / sr, 2),
                "clean_duration_sec": quality["duration"],
                "rms_energy": quality["rms"],
                "quality_score": quality["score"],
                "status": quality["status"]
            })

            print(f"✓ Processed: {filename}")
            print(f"  Duration: {len(raw_audio)/sr:.2f}s -> {quality['duration']:.2f}s clean | RMS: {quality['rms']:.4f} | Status: {quality['status']}")

        except Exception as e:
            print(f"✗ Failed to process {filename}: {e}")
            file_reports.append({
                "filename": filename,
                "error": str(e),
                "status": "failed"
            })

    if not candidates:
        print("\n[ERROR] No audio files could be successfully processed.")
        return False

    # Sort candidates by quality score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    print("\n" + "=" * 60)
    print(f"SELECTED MASTER REFERENCE: {best['filename']}")
    print(f"Quality Score: {best['score']:.2f} | Duration: {best['clean_duration']:.2f}s")
    print("=" * 60)

    # Extract optimal reference clip (target ~24 seconds for conditioning)
    ref_clip = extract_best_reference_clip(
        best["audio"],
        best["sr"],
        min_duration=10.0,
        target_duration=24.0,
        max_duration=30.0
    )
    ref_clip_duration = len(ref_clip) / best["sr"]

    master_ref_path = os.path.join(samples_dir, "sarala_reference.wav")
    sf.write(master_ref_path, ref_clip, best["sr"], subtype='PCM_16')
    print(f"✓ Master reference saved: {master_ref_path}")
    print(f"  Format: 16-bit PCM WAV | Channels: 1 (Mono) | Sample Rate: {best['sr']}Hz | Duration: {ref_clip_duration:.2f}s\n")

    # Generate reference_report.json
    report_data = {
        "master_reference": {
            "source_file": best["filename"],
            "output_path": "backend/voice/samples/sarala_reference.wav",
            "sample_rate": best["sr"],
            "channels": 1,
            "duration_sec": round(ref_clip_duration, 2),
            "file_size_bytes": os.path.getsize(master_ref_path),
            "rms_energy": round(float(np.sqrt(np.mean(ref_clip**2))), 4),
            "peak_amplitude": round(float(np.max(np.abs(ref_clip))), 4),
            "format": "WAV (16-bit PCM Mono)"
        },
        "all_source_files": file_reports,
        "total_files_scanned": len(source_files),
        "successful_conversions": len(candidates),
        "ffmpeg_used": ffmpeg_exe or "system/internal",
        "status": "ready"
    }

    report_path = os.path.join(base_voice_dir, "reference_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print(f"✓ Reference report generated: {report_path}")
    print("Preprocessing completed successfully!\n")
    return True


if __name__ == "__main__":
    success = preprocess_all_recordings()
    if not success:
        sys.exit(1)
