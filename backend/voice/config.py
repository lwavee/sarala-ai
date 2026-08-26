"""
Sarala AI — Voice Configuration
================================
Central configuration for Chatterbox voice cloning.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend directory
_backend_dir = Path(__file__).resolve().parent.parent
_env_file = _backend_dir / ".env"
if _env_file.exists():
    load_dotenv(str(_env_file), override=False)

# Load sarala_voice.json configuration profile if present
_json_config_path = _backend_dir / "voice" / "config" / "sarala_voice.json"
_json_defaults = {}
if _json_config_path.exists():
    try:
        with open(_json_config_path, "r", encoding="utf-8") as f:
            _json_defaults = json.load(f)
    except Exception:
        pass


class VoiceConfig:
    """Voice configuration initialized from sarala_voice.json and environment variables."""

    def __init__(self):
        gen_settings = _json_defaults.get("generation_settings", {})
        default_provider = _json_defaults.get("provider", "chatterbox")
        self.provider: str = os.getenv("SARALA_VOICE_PROVIDER", default_provider).lower().strip()
        self.enabled: bool = os.getenv("SARALA_VOICE_ENABLED", "true").lower() in ("true", "1", "yes")
        self.language: str = os.getenv("SARALA_VOICE_LANGUAGE", _json_defaults.get("language", "hi"))
        self.inference_mode: str = os.getenv("INFERENCE_MODE", _json_defaults.get("inference_mode", "remote_gpu"))

        # Reference audio path resolution (prefers backend/voice/output)
        _custom_ref = os.getenv("SARALA_VOICE_REFERENCE")
        _project_root = _backend_dir.parent
        _candidate_paths = []
        if _custom_ref:
            p = Path(_custom_ref)
            _candidate_paths.append(p if p.is_absolute() else _project_root / _custom_ref)
        if _json_defaults.get("reference_audio"):
            _candidate_paths.append(_project_root / _json_defaults["reference_audio"])
        _candidate_paths.extend([
            _backend_dir / "voice" / "output" / "sarala_hi_5342896e81.wav",
            _backend_dir / "voice" / "output" / "sarala_test_cloned.wav",
            _backend_dir / "voice" / "reference" / "sarala_reference.wav",
        ])

        _ref_path = _candidate_paths[-1]
        for candidate in _candidate_paths:
            if candidate.exists() and candidate.stat().st_size > 0:
                _ref_path = candidate
                break

        self.reference_audio_path: Path = _ref_path

        # Output directory for generated speech
        self.output_dir: Path = Path(__file__).resolve().parent / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Chatterbox Generation Settings
        self.exaggeration: float = float(os.getenv("CHATTERBOX_EXAGGERATION", str(gen_settings.get("exaggeration", 0.25))))
        self.temperature: float = float(os.getenv("CHATTERBOX_TEMPERATURE", str(gen_settings.get("temperature", 0.45))))
        self.seed: int = int(os.getenv("CHATTERBOX_SEED", str(gen_settings.get("seed", 0))))
        self.cfg_weight: float = float(os.getenv("CHATTERBOX_CFG_WEIGHT", str(gen_settings.get("cfg_weight", 0.5))))

        self.json_profile: dict = _json_defaults

    def __repr__(self) -> str:
        return (
            f"VoiceConfig("
            f"provider={self.provider!r}, "
            f"enabled={self.enabled}, "
            f"language={self.language!r}, "
            f"reference={self.reference_audio_path}, "
            f"inference_mode={self.inference_mode!r})"
        )

    def is_chatterbox_provider(self) -> bool:
        return self.provider in ("chatterbox", "chatterbox_online", "chatterbox_multilingual")


# Global singleton
voice_config = VoiceConfig()
