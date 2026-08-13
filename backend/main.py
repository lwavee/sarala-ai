import sys
import os

# ── Unified Entry Point for Sarala AI ───────────────────────────────────────
# This file supports:
# 1. CLI Mode:  python main.py
# 2. Web Mode:  uvicorn main:app --host 0.0.0.0 --port 8000
# ──────────────────────────────────────────────────────────────────────────────

# Import FastAPI app for uvicorn
from web.app import app
from core.brain import Brain
from core.logger import logger

BANNER = """
╔══════════════════════════════════════════╗
║      Sarla AI — Aapki AI Dost 🤖        ║
╚══════════════════════════════════════════╝
Modes:
  'voice mode'      → Mic se baat karo 🎙️
  'text mode'       → Sirf type karo ⌨️
  'text+voice mode' → Type karo, Sarla bolegi 🔊
  'exit'            → Band karo
──────────────────────────────────────────
"""

def start_cli():
    """Run Sarla in Command Line Interface mode."""
    # Suppress noisy ALSA/Jack/PyAudio warnings at startup
    _devnull_fd = os.open(os.devnull, os.O_WRONLY)
    _old_stderr_fd = os.dup(2)
    os.dup2(_devnull_fd, 2)
    os.close(_devnull_fd)
    
    # Import voice system only when CLI starts to avoid unnecessary overhead in web mode
    from interface.voice import VoiceSystem
    
    os.dup2(_old_stderr_fd, 2)
    os.close(_old_stderr_fd)

    print(BANNER)
    brain = Brain()
    voice = VoiceSystem()
    
    mode = "text"
    logger.info("CLI Mode started successfully.")

    while True:
        try:
            if mode == "voice":
                user_input = voice.listen()
                if not user_input: continue
            else:
                user_input = input("You: ").strip()

            if not user_input: continue

            cmd = user_input.lower().strip()

            if cmd == "voice mode":
                mode = "voice"
                msg = "Voice mode on! Mic mein clearly bolein 🎙️"
                print(f"\nSarla: {msg}\n")
                voice.speak(msg)
                continue

            if cmd == "text mode":
                mode = "text"
                print("\nSarla: Text mode on! Type karo 😊\n")
                continue

            # Process & Respond
            response = brain.process_input(user_input)
            print(f"\nSarla: {response}\n")

            if mode == "voice" or "voice" in mode:
                voice.speak(response)

            if cmd in ["exit", "quit", "bye"]:
                break

        except KeyboardInterrupt:
            print("\n\nSarla: Theek hai, phir milenge! Bye 👋")
            break
        except Exception as e:
            logger.error(f"CLI Error: {e}")

if __name__ == "__main__":
    # If run directly as a script, start the CLI interface
    start_cli()

