#!/usr/bin/env python3
"""
Entry point script for the AI Debate Platform.
Run this script to start the web server.
"""

import uvicorn

if __name__ == "__main__":
    print("Starting AI Debate Platform...")
    print("Open your browser and navigate to: http://localhost:8000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="warning")
