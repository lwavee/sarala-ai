import os
import time
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('backend/.env')
from gradio_client import Client, handle_file

ref_path = Path('backend/voice/reference/sarala_reference.wav')
if not ref_path.exists():
    # Fallback to output/sarala_hi_5342896e81.wav
    ref_path = Path('backend/voice/output/sarala_hi_5342896e81.wav')

print(f"Reference Audio: {ref_path} ({ref_path.stat().st_size} bytes)")

token = os.getenv('HF_TOKEN')
spaces = [
    "ResembleAI/Chatterbox-Multilingual-TTS-hi",
    "TGPro1/Chatterbox-Multilingual-TTS",
    "Echo-AI-official/Chatterbox-Multilingual-TTS"
]

text = "नमस्ते, मैं सरला हूँ। आप कैसे हैं?"
success = False
dest: Path | None = None

for space in spaces:
    try:
        print(f"\n--- Testing Space: {space} ---")
        t0 = time.time()
        client = Client(space, token=token)
        print(f"Connected in {time.time()-t0:.2f}s")
        
        api_info = client.view_api(print_info=False, return_format="dict")
        param_names: list[str] = []
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
        
        args = {
            "text_input": text,
            "audio_prompt_path_input": handle_file(str(ref_path)),
            "exaggeration_input": 0.25,
            "temperature_input": 0.45,
            "seed_num_input": 0,
            "cfgw_input": 0.5,
            "api_name": "/generate_tts_audio"
        }
        if "language_id" in param_names:
            args["language_id"] = "hi"
            
        print("Calling /generate_tts_audio with Sarala reference...")
        t_gen = time.time()
        result = client.predict(**args)
        print(f"Generated successfully in {time.time()-t_gen:.2f}s! Result: {result}")
        
        out_dir = Path("backend/voice/output")
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / "sarala_test_cloned.wav"
        shutil.copy2(result, dest)
        print(f"Saved: {dest} ({dest.stat().st_size} bytes)")
        success = True
        break
    except Exception as e:
        print(f"Space {space} failed: {e}")

if not success or dest is None:
    print("All spaces failed.")
else:
    print("\n--- ACOUSTIC ANALYSIS ---")
    import soundfile as sf, numpy as np
    data, sr = sf.read(str(dest))
    if data.ndim > 1: data = np.mean(data, axis=1)
    dur = len(data)/sr
    rms = float(np.sqrt(np.mean(data**2)))
    fft_vals = np.abs(np.fft.rfft(data))
    freqs = np.fft.rfftfreq(len(data), 1.0 / sr)
    spectral_centroid = float(np.sum(freqs * fft_vals) / (np.sum(fft_vals) + 1e-9))
    print(f"Generated File: {dest.name}, SR: {sr}, Dur: {dur:.2f}s, RMS: {rms:.4f}, Centroid: {spectral_centroid:.1f} Hz")
