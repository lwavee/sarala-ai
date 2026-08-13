#!/bin/bash
# Run Sarla AI Web Server
cd /home/avee/Desktop/sarlaai
/home/avee/Desktop/sarlaai/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
