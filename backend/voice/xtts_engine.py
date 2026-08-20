"""
Sarala AI - XTTS-v2 Local Voice Engine
=======================================
Provides high-fidelity, completely local, CPU-based voice cloning for Sarala
using Coqui XTTS-v2 and the master voice sample in backend/voice/samples/sarala_reference.wav.

Safety & Constraints:
- 100% Free & Offline (No cloud APIs or paid services).
- Runs on CPU (torch.device("cpu")), optimized for Intel i7-1185G7.
- Thread-safe serialization for synthesis requests.
- Isolated module that does not disrupt any existing Sarala AI logic.
"""

import os
import sys
import time
import uuid
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional

# Set non-interactive license agreement for Coqui XTTS
os.environ["COQUI_TOS_AGREED"] = "1"

logger = logging.getLogger("sarala.voice")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Voice] %(message)s")

# Base directory paths
VOICE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = VOICE_DIR.parent
SAMPLES_DIR = VOICE_DIR / "samples"
OUTPUT_DIR = VOICE_DIR / "output"
DEFAULT_REF_WAV = SAMPLES_DIR / "sarala_reference.wav"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# List of XTTS-v2 supported languages
SUPPORTED_LANGUAGES = [
    "hi", "en", "es", "fr", "de", "it", "pt", "pl",
    "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "ko", "hu"
]


class XTTSVoiceEngine:
    """
    Singleton XTTS-v2 Voice Cloning Engine.
    Manages model lifecycle, device configuration, and CPU-safe speech synthesis.
    """
    _instance: Optional["XTTSVoiceEngine"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(XTTSVoiceEngine, cls).__new__(cls)
        return cls._instance

    def __init__(self, reference_audio_path: Optional[str] = None):
        # Prevent re-initialization if already loaded
        if getattr(self, "_initialized", False):
            return

        self._tts_model = None
        self._model_loading = False
        self._synthesis_lock = threading.Lock()
        self.device = "cpu"
        self.reference_wav = Path(reference_audio_path) if reference_audio_path else DEFAULT_REF_WAV
        self.output_dir = OUTPUT_DIR
        self._initialized = True
        logger.info(f"XTTSVoiceEngine instantiated. Default reference: {self.reference_wav}")

    def is_reference_available(self) -> bool:
        """Checks if the master reference audio file exists and is accessible."""
        return self.reference_wav.exists() and self.reference_wav.stat().st_size > 0

    def is_model_loaded(self) -> bool:
        """Checks if the TTS model weights are loaded into memory."""
        return self._tts_model is not None

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive diagnostic and readiness information."""
        return {
            "model_loaded": self.is_model_loaded(),
            "model_name": "tts_models/multilingual/multi-dataset/xtts_v2",
            "device": self.device,
            "reference_wav": str(self.reference_wav),
            "reference_available": self.is_reference_available(),
            "supported_languages": SUPPORTED_LANGUAGES,
            "output_directory": str(self.output_dir),
        }

    def load_model(self) -> bool:
        """
        Loads the Coqui XTTS-v2 model onto CPU.
        Thread-safe and idempotent.
        """
        if self._tts_model is not None:
            return True

        with self._lock:
            if self._tts_model is not None:
                return True

            logger.info("Initializing Coqui XTTS-v2 model on CPU...")
            t0 = time.time()
            try:
                import torch
                # Limit CPU threads to prevent CPU thrashing
                cpu_threads = max(1, min(4, os.cpu_count() or 4))
                torch.set_num_threads(cpu_threads)
                logger.info(f"Configured PyTorch CPU threads: {cpu_threads}")

                # Monkey-patch GPT2InferenceModel for transformers compatibility
                try:
                    from TTS.tts.layers.xtts.gpt_inference import GPT2InferenceModel
                    def prepare_inputs_for_generation(self, input_ids, past_key_values=None, **kwargs):
                        if past_key_values:
                            input_ids = input_ids[:, -1].unsqueeze(-1)
                        return {
                            "input_ids": input_ids,
                            "past_key_values": past_key_values,
                            "attention_mask": kwargs.get("attention_mask", None),
                            "use_cache": kwargs.get("use_cache", True),
                        }
                    GPT2InferenceModel.prepare_inputs_for_generation = prepare_inputs_for_generation
                except Exception as patch_err:
                    logger.warning(f"Could not patch GPT2InferenceModel: {patch_err}")

                from TTS.api import TTS
                # Coqui XTTS-v2 multi-speaker, multilingual model
                self._tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
                elapsed = time.time() - t0
                logger.info(f"XTTS-v2 model loaded successfully in {elapsed:.2f}s on {self.device}.")
                return True
            except Exception as e:
                logger.error(f"Failed to load XTTS-v2 model: {str(e)}", exc_info=True)
                self._tts_model = None
                raise RuntimeError(f"Could not load XTTS-v2 model: {e}")

    def synthesize(
        self,
        text: str,
        language: str = "hi",
        reference_wav: Optional[str] = None,
        output_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes speech using the cloned Sarala voice.

        Args:
            text: Text to synthesize.
            language: Language code (default 'hi' for Hindi, 'en' for English).
            reference_wav: Optional override path for reference speaker WAV.
            output_filename: Optional target WAV filename in the output directory.

        Returns:
            Dict containing success status, audio file path, duration, latency, and sample rate.
        """
        text = text.strip() if text else ""
        if not text:
            return {
                "success": False,
                "error": "Input text cannot be empty.",
            }

        target_lang = language.lower().strip()
        if target_lang not in SUPPORTED_LANGUAGES:
            # Fallback to Hindi if unsupported
            logger.warning(f"Language '{language}' not directly in supported list. Defaulting to 'hi'.")
            target_lang = "hi"

        speaker_audio = Path(reference_wav) if reference_wav else self.reference_wav
        if not speaker_audio.exists():
            return {
                "success": False,
                "error": f"Reference speaker audio not found at: {speaker_audio}",
            }

        # Ensure model is ready
        if not self.is_model_loaded():
            self.load_model()

        if not output_filename:
            unique_id = uuid.uuid4().hex[:8]
            output_filename = f"sarala_{target_lang}_{unique_id}.wav"
        elif not output_filename.endswith(".wav"):
            output_filename = f"{output_filename}.wav"

        out_path = self.output_dir / output_filename

        # XTTS inference on CPU is compute-intensive, serialize execution
        with self._synthesis_lock:
            t0 = time.time()
            try:
                logger.info(f"Synthesizing text [{target_lang}] ({len(text)} chars): '{text[:60]}...'")
                
                self._tts_model.tts_to_file(
                    text=text,
                    speaker_wav=str(speaker_audio),
                    language=target_lang,
                    file_path=str(out_path),
                )
                
                latency = time.time() - t0
                
                # Calculate audio duration from generated WAV
                duration = 0.0
                sample_rate = 24000
                try:
                    import soundfile as sf
                    info = sf.info(str(out_path))
                    duration = info.duration
                    sample_rate = info.samplerate
                except Exception as ex:
                    logger.warning(f"Could not read audio file properties: {ex}")

                logger.info(f"Synthesis finished in {latency:.2f}s -> {out_path.name} (Duration: {duration:.2f}s)")
                
                return {
                    "success": True,
                    "filename": out_path.name,
                    "file_path": str(out_path),
                    "audio_url": f"/voice/audio/{out_path.name}",
                    "duration": round(duration, 2),
                    "latency_sec": round(latency, 2),
                    "sample_rate": sample_rate,
                    "language": target_lang,
                    "error": None,
                }
            except Exception as e:
                logger.error(f"Synthesis error: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e),
                }


# Global singleton instance
voice_engine = XTTSVoiceEngine()
