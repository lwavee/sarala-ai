"""
Sarala AI - Online Chatterbox Hindi Voice Engine
=================================================
Connects to the ResembleAI/Chatterbox-Multilingual-TTS-hi Hugging Face Space
via the lightweight gradio_client. Provides voice cloning by sending:
  - Text to synthesize
  - Reference audio path (Sarala's voice sample)
  - Synthesis parameters (exaggeration, temperature, cfg_weight, seed)

The model runs entirely on Hugging Face's cloud GPU.
Your computer only sends text + audio → receives generated WAV.

API Schema (verified from HF Space source code):
  Function: generate_tts_audio
  Inputs:   [text, ref_wav, exaggeration, temperature, seed_num, cfg_weight]
  Returns:  (sample_rate: int, wav_array: numpy.ndarray)
"""

import os
import time
import uuid
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("sarala.chatterbox_online")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [ChatterboxOnline] %(message)s",
    )


class OnlineChatterboxVoice:
    """
    Client for the ResembleAI Chatterbox Multilingual Hindi HF Space.

    Uses gradio_client to call the online Space API.
    No local model weights are downloaded or loaded.
    """

    def __init__(self, space_id: str = "ResembleAI/Chatterbox-Multilingual-TTS-hi"):
        self.space_id = space_id
        self._client = None
        self._initialized = False

    # ── Initialization ────────────────────────────────────────────────────────

    def initialize(self) -> bool:
        """
        Create a gradio_client.Client connected to the HF Space.
        Returns True if successful, False if the Space is unreachable.
        """
        if self._initialized and self._client is not None:
            return True

        try:
            from gradio_client import Client  # type: ignore

            logger.info(f"Connecting to HF Space: {self.space_id} ...")
            self._client = Client(self.space_id)
            if self._client is None:
                raise RuntimeError("Client() returned None unexpectedly")
            self._initialized = True
            logger.info("Chatterbox HF Space client initialized successfully.")
            return True
        except ImportError:
            logger.error(
                "gradio_client is not installed. Run: pip install gradio_client"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to connect to HF Space '{self.space_id}': {e}")
            self._initialized = False
            self._client = None
            return False

    # ── Synthesis ─────────────────────────────────────────────────────────────

    def synthesize(
        self,
        text: str,
        reference_audio: str,
        exaggeration: float = 0.5,
        temperature: float = 0.8,
        cfg_weight: float = 0.5,
        seed: int = 0,
        output_dir: Optional[str] = None,
        output_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize Hindi speech using the online Chatterbox Hindi Space.

        Args:
            text:             Text to synthesize (max 300 chars).
            reference_audio:  Path to the speaker reference WAV file.
            exaggeration:     Emotion exaggeration (0.5 = neutral, range 0.25–2.0).
            temperature:      Sampling temperature (0.8 = default, range 0.05–5.0).
            cfg_weight:       CFG / pace weight (0.5 = default, range 0.2–1.0).
            seed:             Random seed (0 = random each time).
            output_dir:       Directory to save the output WAV. Defaults to voice/output/.
            output_filename:  Filename for the output WAV. Auto-generated if None.

        Returns:
            Dict with keys: success, filename, file_path, audio_url, latency_sec,
                            sample_rate, duration_sec, provider, language, error.
        """
        t0 = time.time()

        # ── Validate inputs ──────────────────────────────────────────────────
        text = text.strip() if text else ""
        if not text:
            return {"success": False, "error": "Text cannot be empty.", "provider": "chatterbox_online"}

        ref_path = Path(reference_audio)
        if not ref_path.exists():
            return {
                "success": False,
                "error": f"Reference audio not found: {reference_audio}",
                "provider": "chatterbox_online",
            }

        # Chatterbox enforces 300-char limit
        if len(text) > 300:
            logger.warning(
                f"Text truncated from {len(text)} to 300 chars for Chatterbox."
            )
            text = text[:300]

        # ── Ensure client is ready ───────────────────────────────────────────
        if not self._initialized or self._client is None:
            if not self.initialize():
                return {
                    "success": False,
                    "error": (
                        f"Cannot connect to Chatterbox HF Space '{self.space_id}'. "
                        "Check your internet connection or try again later."
                    ),
                    "provider": "chatterbox_online",
                }

        # ── Call the HF Space API ────────────────────────────────────────────
        try:
            logger.info(
                f"Calling Chatterbox Space (lang=hi, {len(text)} chars): '{text[:60]}...'"
            )
            logger.info(
                f"  Params: exaggeration={exaggeration}, temperature={temperature}, "
                f"cfg_weight={cfg_weight}, seed={seed}"
            )

            # Defensive guard: ensure client is not None before calling predict.
            # This can happen if initialize() returned True but the Client object
            # was unexpectedly None, or if a prior connection error reset the client.
            if self._client is None:
                self._initialized = False
                return {
                    "success": False,
                    "error": (
                        "Chatterbox client is not available (client is None after "
                        "initialization). Please retry — the connection will be "
                        "re-established on the next request."
                    ),
                    "provider": "chatterbox_online",
                }

            # Parameter order MUST match the Space's `inputs` list:
            # [text, ref_wav, exaggeration, temperature, seed_num, cfg_weight]
            result = self._client.predict(
                text,                         # text_input
                str(ref_path),               # audio_prompt_path_input
                exaggeration,                # exaggeration_input
                temperature,                 # temperature_input
                seed,                        # seed_num_input
                cfg_weight,                  # cfgw_input
                api_name="/generate_tts_audio",
            )

            # result is a tuple: (sample_rate, numpy_array)
            if isinstance(result, (list, tuple)) and len(result) == 2:
                sample_rate, wav_array = result
            else:
                return {
                    "success": False,
                    "error": f"Unexpected API response format: {type(result)}",
                    "provider": "chatterbox_online",
                }

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Chatterbox API call failed: {err_msg}")
            # Reset client on connection errors to force reconnect next time
            if any(k in err_msg.lower() for k in ["connection", "timeout", "reset", "closed"]):
                self._initialized = False
                self._client = None
            return {
                "success": False,
                "error": f"Chatterbox API error: {err_msg}",
                "provider": "chatterbox_online",
            }

        # ── Save the generated audio ─────────────────────────────────────────
        if output_dir is None:
            from voice.config import OUTPUT_DIR
            out_dir = OUTPUT_DIR
        else:
            out_dir = Path(output_dir)

        out_dir.mkdir(parents=True, exist_ok=True)

        if output_filename is None:
            uid = uuid.uuid4().hex[:10]
            output_filename = f"sarala_hi_{uid}.wav"
        elif not output_filename.endswith(".wav"):
            output_filename += ".wav"

        save_result = self.save_output(
            sample_rate=sample_rate,
            wav_array=wav_array,
            output_path=str(out_dir / output_filename),
        )

        if not save_result["success"]:
            return save_result

        latency = round(time.time() - t0, 2)
        file_path = out_dir / output_filename
        duration = save_result.get("duration_sec", 0.0)

        logger.info(
            f"Chatterbox synthesis complete in {latency}s → {output_filename} "
            f"({duration:.2f}s audio)"
        )

        return {
            "success": True,
            "filename": output_filename,
            "file_path": str(file_path),
            "audio_url": f"/voice/audio/{output_filename}",
            "latency_sec": latency,
            "duration_sec": duration,
            "sample_rate": sample_rate,
            "provider": "chatterbox_online",
            "language": "hi",
            "error": None,
        }

    # ── Save Output ───────────────────────────────────────────────────────────

    def save_output(
        self,
        sample_rate: int,
        wav_array,
        output_path: str,
    ) -> Dict[str, Any]:
        """
        Save numpy audio array to a WAV file.

        Args:
            sample_rate:  Sample rate of the audio (e.g. 24000).
            wav_array:    Numpy array of audio samples (float32).
            output_path:  Full path to write the WAV file.

        Returns:
            Dict with success, file_path, duration_sec.
        """
        try:
            import numpy as np
            import soundfile as sf

            arr = np.array(wav_array, dtype=np.float32)
            if arr.ndim > 1:
                arr = arr.squeeze()

            duration_sec = len(arr) / sample_rate if sample_rate > 0 else 0.0

            sf.write(output_path, arr, sample_rate, subtype="PCM_16")

            if not Path(output_path).exists():
                return {"success": False, "error": f"File not written: {output_path}"}

            return {
                "success": True,
                "file_path": output_path,
                "duration_sec": round(duration_sec, 2),
            }

        except Exception as e:
            logger.error(f"Failed to save WAV output: {e}")
            return {"success": False, "error": f"Failed to save audio: {e}"}

    # ── Health Check ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """
        Quick liveness check for the HF Space client.
        Returns status dict suitable for the /voice/health endpoint.
        """
        try:
            if not self._initialized or self._client is None:
                ok = self.initialize()
                if not ok:
                    return {
                        "chatterbox_online": False,
                        "space": self.space_id,
                        "error": "Cannot reach HF Space",
                    }

            # Confirm client is valid before calling view_api
            if self._client is None:
                return {
                    "chatterbox_online": False,
                    "space": self.space_id,
                    "error": "Client is None after initialization",
                }
            self._client.view_api(print_info=False)
            return {
                "chatterbox_online": True,
                "space": self.space_id,
                "status": "reachable",
            }
        except Exception as e:
            return {
                "chatterbox_online": False,
                "space": self.space_id,
                "error": str(e),
            }


# ── Module-level singleton ────────────────────────────────────────────────────
chatterbox_voice = OnlineChatterboxVoice()
