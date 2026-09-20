#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Run Uvicorn with auto-reload (the startup summary is printed by main.py)
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
