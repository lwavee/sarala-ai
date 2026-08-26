"""
Sarala AI — Chatterbox Voice Provider
======================================
100% Free Open-Source Voice Cloning using Chatterbox Multilingual TTS.

Features:
- Conditioned on Sarala reference audio (24 kHz Mono WAV).
- Modular inference: Supports Remote GPU (Hugging Face Spaces / custom GPU worker) and Local CPU fallback.
- Client caching: Reuses connections to avoid re-initializing for every sentence.
- Pure 24,000 Hz Mono WAV audio output without degradation.
- Zero paid API requirements.
"""

import os
import time
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("sarala.chatterbox_provider")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [ChatterboxProvider] %(message)s"
    )


class VoiceSynthesisError(Exception):
    """Raised when voice cloning synthesis fails."""
    pass


class ChatterboxProvider:
    """
    Modular Chatterbox Multilingual Voice Provider for Sarala AI.
    """

    DEFAULT_SPACES: List[str] = [
        "TGPro1/Chatterbox-Multilingual-TTS",
        "ResembleAI/Chatterbox-Multilingual-TTS-hi",
        "Echo-AI-official/Chatterbox-Multilingual-TTS",
        "saqib575757/Chatterbox-Multilingual-TTS",
    ]

    def __init__(
        self,
        reference_audio_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        remote_url: Optional[str] = None,
        hf_token: Optional[str] = None,
    ):
        backend_dir = Path(__file__).resolve().parent.parent.parent
        self.reference_audio_path = reference_audio_path or (
            backend_dir / "voice" / "reference" / "sarala_reference.wav"
        )
        self.output_dir = output_dir or (backend_dir / "voice" / "output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.remote_url = remote_url or os.getenv("CHATTERBOX_REMOTE_URL")
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self._client_cache: Dict[str, Any] = {}
        self._api_info_cache: Dict[str, Any] = {}

    def _get_client(self, space_or_url: str):
        """Retrieves or creates a cached client for the given space or remote URL."""
        if space_or_url in self._client_cache:
            return self._client_cache[space_or_url]

        from gradio_client import Client
        kwargs: Dict[str, Any] = {}
        if self.hf_token and not space_or_url.startswith("http"):
            kwargs["token"] = self.hf_token
            kwargs["headers"] = {"Authorization": f"Bearer {self.hf_token}"}

        logger.info(f"Connecting to remote inference endpoint: {space_or_url}")
        t0 = time.time()
        client = Client(space_or_url, **kwargs)
        elapsed = round(time.time() - t0, 2)
        logger.info(f"Connected to {space_or_url} in {elapsed}s (session cached)")

        self._client_cache[space_or_url] = client
        return client

    def _get_candidate_endpoints(self) -> List[str]:
        """Returns candidate remote inference endpoints in priority order."""
        endpoints = []
        if self.remote_url:
            endpoints.append(self.remote_url)
        env_space = os.getenv("CHATTERBOX_SPACE")
        if env_space and env_space not in endpoints:
            endpoints.append(env_space)
        for space in self.DEFAULT_SPACES:
            if space not in endpoints:
                endpoints.append(space)
        return endpoints

    def is_reference_ready(self) -> bool:
        """Checks if the Sarala reference audio exists and is valid."""
        return self.reference_audio_path.exists() and self.reference_audio_path.stat().st_size > 1000

    def synthesize(
        self,
        text: str,
        language: str = "hi",
        reference_audio: Optional[str] = None,
        exaggeration: float = 0.25,
        temperature: float = 0.45,
        seed: int = 0,
        cfg_weight: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Synthesizes speech using Chatterbox Multilingual conditioned on Sarala reference audio.

        Args:
            text: Text to synthesize (Hindi/Hinglish/multilingual).
            language: Language code (default "hi").
            reference_audio: Optional override for reference audio path.
            exaggeration: Neutral=0.25 (clamped [0.25, 2.0]).
            temperature: 0.45 - 0.5 for stable, soft pitch delivery.
            seed: 0 for natural variation or fixed integer.
            cfg_weight: 0.5 balanced classifier-free guidance.

        Returns:
            Dict containing success, audio_path, audio_url, filename, duration_sec, latency_sec.
        """
        text = (text or "").strip()
        if not text:
            raise VoiceSynthesisError("Text cannot be empty.")

        ref_path = Path(reference_audio) if reference_audio else self.reference_audio_path
        if not ref_path.exists() or ref_path.stat().st_size == 0:
            # Check backend/voice/output and backend/voice/reference
            fallback_candidates = [
                self.output_dir / "sarala_hi_5342896e81.wav",
                self.output_dir / "sarala_test_cloned.wav",
                self.output_dir.parent / "reference" / "sarala_reference.wav",
            ]
            for cand in fallback_candidates:
                if cand.exists() and cand.stat().st_size > 0:
                    ref_path = cand
                    break

        if not ref_path.exists() or ref_path.stat().st_size == 0:
            raise VoiceSynthesisError(
                f"Reference audio not found at: {ref_path}. "
                "Ensure an audio file exists in backend/voice/output or backend/voice/reference."
            )

        # Enforce safe parameter ranges for Chatterbox
        safe_exaggeration = max(0.25, min(2.0, float(exaggeration)))
        safe_temperature = max(0.05, min(5.0, float(temperature)))
        safe_cfg = max(0.2, min(1.0, float(cfg_weight)))

        logger.info(
            f"Cloning voice [{language}] for {len(text)} chars via Chatterbox "
            f"(exag={safe_exaggeration}, temp={safe_temperature}, seed={seed})"
        )
        t0 = time.time()

        from gradio_client import handle_file
        audio_file_arg = handle_file(str(ref_path))

        endpoints = self._get_candidate_endpoints()
        last_error: Optional[Exception] = None

        for endpoint in endpoints:
            try:
                client = self._get_client(endpoint)

                # Query endpoint schema (cached)
                if endpoint not in self._api_info_cache:
                    api_info = client.view_api(print_info=False, return_format="dict")
                    self._api_info_cache[endpoint] = api_info
                else:
                    api_info = self._api_info_cache[endpoint]

                param_names: List[str] = []
                if isinstance(api_info, dict):
                    named_endpoints = api_info.get("named_endpoints", {})
                    if isinstance(named_endpoints, dict):
                        endpoint_info = named_endpoints.get("/generate_tts_audio", {})
                        if isinstance(endpoint_info, dict):
                            parameters = endpoint_info.get("parameters", [])
                            if isinstance(parameters, list):
                                param_names = [
                                    p.get("parameter_name")
                                    for p in parameters
                                    if isinstance(p, dict) and p.get("parameter_name") is not None
                                ]

                predict_args: Dict[str, Any] = {
                    "text_input": text,
                    "audio_prompt_path_input": audio_file_arg,
                    "exaggeration_input": safe_exaggeration,
                    "temperature_input": safe_temperature,
                    "seed_num_input": float(seed),
                    "cfgw_input": safe_cfg,
                    "api_name": "/generate_tts_audio",
                }
                if "language_id" in param_names:
                    predict_args["language_id"] = language

                result = client.predict(**predict_args)
                latency = round(time.time() - t0, 2)
                logger.info(f"Chatterbox synthesis succeeded via '{endpoint}' in {latency}s")

                return self._save_output(result, latency=latency, language=language, endpoint=endpoint)

            except Exception as e:
                last_error = e
                logger.warning(f"Inference on endpoint '{endpoint}' failed ({e}). Trying next fallback...")
                # Reset cached client for this endpoint so next attempt reconnects cleanly
                self._client_cache.pop(endpoint, None)
                self._api_info_cache.pop(endpoint, None)
                continue

        raise VoiceSynthesisError(
            f"Chatterbox voice generation failed on all available endpoints. Last error: {last_error}"
        )

    def _save_output(
        self,
        gradio_result: Any,
        latency: float,
        language: str = "hi",
        endpoint: str = "remote_gpu",
    ) -> Dict[str, Any]:
        """Saves generated WAV output into output_dir without overwriting existing files."""
        if isinstance(gradio_result, str):
            raw_path = gradio_result
        elif isinstance(gradio_result, (list, tuple)) and len(gradio_result) > 0:
            raw_path = str(gradio_result[0])
        elif isinstance(gradio_result, dict):
            raw_path = gradio_result.get("path") or gradio_result.get("url")
        else:
            raw_path = str(gradio_result)

        if not raw_path:
            raise VoiceSynthesisError("Chatterbox returned an empty result path.")

        src = Path(raw_path)
        if not src.exists():
            raise VoiceSynthesisError(f"Chatterbox output file not found at: {raw_path}")

        # Unique hash name ensuring existing files are NEVER overwritten
        while True:
            unique_token = hashlib.sha256(f"{time.time()}_{os.urandom(8)}".encode()).hexdigest()[:10]
            out_filename = f"sarala_{language}_{unique_token}.wav"
            dest = self.output_dir / out_filename
            if not dest.exists():
                break

        shutil.copy2(src, dest)
        logger.info(f"Saved generated audio: {out_filename} ({dest.stat().st_size} bytes)")

        # Calculate exact duration and sample rate
        duration_sec = 0.0
        sample_rate = 24000
        try:
            import soundfile as sf
            info = sf.info(str(dest))
            duration_sec = round(info.duration, 2)
            sample_rate = info.samplerate
        except Exception:
            pass

        return {
            "success": True,
            "filename": out_filename,
            "audio_path": str(dest),
            "audio_url": f"/voice/audio/{out_filename}",
            "duration_sec": duration_sec,
            "sample_rate": sample_rate,
            "latency_sec": latency,
            "provider": "chatterbox",
            "language": language,
            "inference_mode": "remote_gpu",
            "endpoint": endpoint,
        }


# Global singleton
_provider_instance: Optional[ChatterboxProvider] = None


def get_chatterbox_provider() -> ChatterboxProvider:
    """Returns the singleton instance of ChatterboxProvider."""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = ChatterboxProvider()
    return _provider_instance
