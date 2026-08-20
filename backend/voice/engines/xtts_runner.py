"""
Sarala AI - XTTS-v2 Voice Benchmark Runner
Evaluates Coqui XTTS-v2 on CPU using clean reference audio.
"""

import os
import sys
import time
import logging
import numpy as np
import soundfile as sf
from typing import Dict, Any
from voice.engines.base_engine import BaseVoiceEngineRunner

logger = logging.getLogger("VoiceBenchmark.XTTS")

def patch_xtts_gpt_inference():
    """Patches GPT2InferenceModel to support HuggingFace generation pipeline."""
    try:
        from TTS.tts.layers.xtts.gpt_inference import GPT2InferenceModel  # type: ignore
        
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
    except Exception as e:
        logger.warning(f"Could not patch GPT2InferenceModel: {e}")

class XTTSBenchmarkRunner(BaseVoiceEngineRunner):
    def __init__(self):
        super().__init__(name="XTTS-v2", model_id="tts_models/multilingual/multi-dataset/xtts_v2")
        self.tts = None
        self.device = "cpu"
        
    def load_model(self) -> bool:
        if self.is_loaded and self.tts is not None:
            return True
            
        try:
            # Check if voice_engine singleton has already loaded the model into memory
            try:
                from voice.xtts_engine import voice_engine
                if voice_engine.is_model_loaded() and voice_engine._tts_model is not None:
                    self.tts = voice_engine._tts_model
                    self.device = voice_engine.device
                    self.is_loaded = True
                    logger.info("XTTS-v2 reused existing model from voice_engine singleton.")
                    return True
            except Exception as singleton_err:
                logger.debug(f"Could not reuse voice_engine singleton: {singleton_err}")

            os.environ["COQUI_TOS_AGREED"] = "1"
            import torch
            
            # Restrict PyTorch CPU threads to prevent CPU thrashing/starvation
            cpu_threads = max(1, min(4, os.cpu_count() or 4))
            torch.set_num_threads(cpu_threads)
            
            patch_xtts_gpt_inference()
            
            from TTS.api import TTS
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading XTTS-v2 on device: {self.device}...")
            
            loaded_tts = TTS(self.model_id).to(self.device)
            if loaded_tts is None:
                raise RuntimeError("Coqui TTS initialization returned None")

            self.tts = loaded_tts
            self.is_loaded = True
            logger.info("XTTS-v2 loaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to load XTTS-v2: {e}")
            self.tts = None
            self.is_loaded = False
            return False
            
    def synthesize(self, text: str, ref_audio_path: str, language: str = "hi", **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        
        if not self.load_model() or self.tts is None:
            return {
                "success": False,
                "error": "Failed to initialize XTTS-v2 model (model is not loaded).",
                "latency_sec": 0,
                "rtf": 0
            }
            
        if not os.path.exists(ref_audio_path):
            return {
                "success": False,
                "error": f"Reference audio not found: {ref_audio_path}",
                "latency_sec": 0,
                "rtf": 0
            }
            
        try:
            temp_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "benchmark"
            )
            os.makedirs(temp_dir, exist_ok=True)
            temp_out = os.path.join(temp_dir, "temp_xtts.wav")
            
            if self.tts is None:
                raise RuntimeError("XTTS-v2 model instance is None.")

            t0 = time.time()
            self.tts.tts_to_file(
                text=text,
                speaker_wav=ref_audio_path,
                language=language,
                file_path=temp_out
            )
            latency = time.time() - t0
            
            audio_data, sample_rate = sf.read(temp_out, dtype='float32')
            duration = len(audio_data) / sample_rate
            rtf = latency / duration if duration > 0 else 0
            
            if os.path.exists(temp_out):
                try:
                    os.remove(temp_out)
                except Exception:
                    pass
            
            return {
                "success": True,
                "audio_data": audio_data,
                "sample_rate": sample_rate,
                "duration_sec": round(duration, 2),
                "latency_sec": round(latency, 2),
                "rtf": round(rtf, 2),
                "device": self.device,
                "model": self.model_id
            }
        except Exception as e:
            logger.error(f"XTTS synthesis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "latency_sec": round(time.time() - start_time, 2),
                "rtf": 0
            }
            
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": "Coqui XTTS-v2",
            "model_architecture": "Autoregressive Latent Diffusion + HiFi-GAN",
            "supported_languages": ["hi", "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja", "hu", "ko"],
            "native_hindi_support": "Yes (Native Devanagari text tokenizer)",
            "cpu_feasibility": "High. Runs reliably on modern Intel Core i7 CPUs (~2-3x RTF).",
            "recommended_ref_duration": "10 - 25 seconds",
            "speaker_similarity_rating": "4.2 / 5",
            "prosody_and_emotion": "Good emotion transfer and pitch variation; occasional slight robotic inflection at sentence pauses on complex Hindi conjuncts."
        }
