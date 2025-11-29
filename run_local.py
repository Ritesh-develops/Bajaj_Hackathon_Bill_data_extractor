#!/usr/bin/env python
"""
Local development runner with ngrok tunneling
Usage:
  python run_local.py
"""

import subprocess
import time
import sys
import os
from pathlib import Path

# Set PYTHONPATH
project_root = Path(__file__).parent
os.environ['PYTHONPATH'] = str(project_root)

def main():
    print("=" * 60)
    print("Bill Extractor - Local Development Setup")
    print("=" * 60)
    
    # Start FastAPI server
    print("\n[1] Starting FastAPI server on http://localhost:8000...")
    server_cmd = [
        sys.executable, 
        "app/main.py"
    ]
    
    server_process = subprocess.Popen(
        server_cmd,
        cwd=project_root,
        env={**os.environ, 'PYTHONPATH': str(project_root)}
    )
    
    # Wait for server to start
    time.sleep(3)
    
    print("[✓] FastAPI server started")
    print("\n[2] Starting ngrok tunnel...")
    
    try:
        # Start ngrok
        ngrok_cmd = ["ngrok", "http", "8000"]
        ngrok_process = subprocess.Popen(
            ngrok_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print("[✓] ngrok started")
        
        # Read ngrok output to find public URL
        time.sleep(3)
        
        # Try to get ngrok URL from the API
        try:
            import requests
            response = requests.get('http://127.0.0.1:4040/api/tunnels', timeout=5)
            if response.status_code == 200:
                tunnels = response.json()
                if tunnels.get('tunnels'):
                    for tunnel in tunnels['tunnels']:
                        if tunnel['proto'] == 'https':
                            public_url = tunnel['public_url']
                            print(f"\n{'='*60}")
                            print(f"✓ PUBLIC URL: {public_url}")
                            print(f"{'='*60}")
                            print(f"\nAPI Endpoint: {public_url}/api/extract-bill-data")
                            print(f"Docs: {public_url}/docs")
                            print(f"Local Server: http://localhost:8000")
                            print(f"\nKeep this terminal open to maintain the tunnel.")
                            print(f"Press Ctrl+C to stop both server and ngrok.\n")
                            break
        except Exception as e:
            print(f"[!] Could not retrieve ngrok URL: {e}")
            print("[!] Check ngrok dashboard: https://dashboard.ngrok.com/")
        
        # Keep running
        server_process.wait()
        
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down...")
        ngrok_process.terminate()
        server_process.terminate()
        time.sleep(1)
        ngrok_process.kill()
        server_process.kill()
        print("[✓] Shutdown complete")
    except Exception as e:
        print(f"[!] Error: {e}")
        server_process.terminate()
        if 'ngrok_process' in locals():
            ngrok_process.terminate()

if __name__ == "__main__":
    main()
