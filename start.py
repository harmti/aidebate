#!/usr/bin/env python3
"""
Start script for the AI Debate Platform.
This script is used by Railway to start the application.
"""

import os
import uvicorn

if __name__ == "__main__":
    # Get the port from the environment variable or use 8000 as default
    port = int(os.environ.get("PORT", 8000))

    print(f"Starting AI Debate Platform on port {port}...")
    print(f"Open your browser and navigate to: http://localhost:{port}")

    # Start the application
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
