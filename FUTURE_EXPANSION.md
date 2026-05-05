# Sarala AI - Future Expansion Roadmap

This document outlines the architecture strategy to upgrade Sarala from a CLI assistant to a full cross-platform application (Android & Windows).

## 1. Centralizing the Brain (API Server)
Right now, `main.py` directly imports `core/brain.py`. To support mobile and desktop apps simultaneously, we must decouple the Interface from the Brain.
- **Action:** Convert Sarala's core into a Web API using **FastAPI** or **Flask**.
- **Result:** Instead of running the loop locally, the server will expose an endpoint `POST /ask` that takes `{"user_input": "open youtube"}` and returns `{"response": "Opening YouTube..."}`. The server will run in the background.

## 2. Windows GUI Expansion
Once the Brain is an API, we can create a beautiful visual interface.
- **Framework:** `CustomTkinter` (for modern dark mode UIs) or `PyQt6`.
- **Architecture:** The GUI will act as a frontend client that sends requests to the FastAPI backend and displays the chat bubbles. Voice capabilities can be integrated directly via voice toggles on the UI.

## 3. Android Integration 
Porting pure Python voice logic to Android directly has challenges. Here are the best approaches:
- **Approach A (Termux):** For immediate usage, you can install the Termux app on Android, clone this repository, install pip dependencies, and run Sarala's CLI exactly as it runs on Linux right now!
- **Approach B (Web App / React Native):** Build a responsive React/Next.js frontend that talks to your FastAPI backend, and install it on Android as an app.
- **Approach C (Native Python with Kivy/Buildozer):** Use Kivy to build a touch-friendly UI in Python. Use Buildozer on Ubuntu to compile the Python code into an Android `.apk` file.

## Conclusion
Because we designed Sarala with a modular architecture (`Agent -> Brain -> Executor/Memory/LLM`), the core logic is already future-proof. You do not need to rewrite the brain to support a mobile app!
