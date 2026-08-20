"""
Sarala AI - Voice Engine Benchmark Base Class
Defines the uniform interface and hardware auto-detection for all candidate TTS engines.
"""

import os
import sys
import time
import platform
import psutil
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

def get_hardware_info() -> Dict[str, Any]:
    """Detects CPU, RAM, and hardware acceleration availability."""
    cpu_name = platform.processor() or "Intel Core i7-1185G7"
    cpu_count_physical = psutil.cpu_count(logical=False) or 4
    cpu_count_logical = psutil.cpu_count(logical=True) or 8
    total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    
    cuda_available = False
    cuda_device = None
    try:
        import torch
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            cuda_device = torch.cuda.get_device_name(0)
    except Exception:
        pass
        
    return {
        "cpu_name": cpu_name,
        "physical_cores": cpu_count_physical,
        "logical_threads": cpu_count_logical,
        "total_ram_gb": total_ram_gb,
        "cuda_available": cuda_available,
        "cuda_device": cuda_device,
        "hardware_recommendation": (
            "GPU (CUDA) detected. Full acceleration enabled."
            if cuda_available
            else "Intel Iris Xe / CPU Mode active. Running with multi-threaded CPU inference. High-compute diffusion models will exhibit higher latency."
        )
    }

class BaseVoiceEngineRunner(ABC):
    """Abstract interface for all voice benchmark runners."""
    
    def __init__(self, name: str, model_id: str):
        self.name = name
        self.model_id = model_id
        self.hardware_info = get_hardware_info()
        self.is_loaded = False
        
    @abstractmethod
    def load_model(self) -> bool:
        """Loads model weights and vocoders into memory."""
        pass
        
    @abstractmethod
    def synthesize(self, text: str, ref_audio_path: str, language: str = "hi", **kwargs) -> Dict[str, Any]:
        """
        Synthesizes speech using the reference audio prompt.
        Returns a dict containing:
        - success: bool
        - audio_data: np.ndarray (float32 mono PCM)
        - sample_rate: int
        - latency_sec: float
        - rtf: float (Real Time Factor = latency / audio_duration)
        - error: Optional[str]
        """
        pass
        
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Returns engine metadata, supported languages, prosody capabilities, and CPU feasibility."""
        pass
