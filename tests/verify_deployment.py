import sys
import time
import requests
import subprocess
import os

def verify_deployment():
    print("Starting verification...")
    
    # Start the app in a subprocess
    process = subprocess.Popen(
        [sys.executable, "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy()
    )
    
    try:
        # Wait for startup
        print("Waiting for server to start...")
        time.sleep(10)
        
        # Check health
        try:
            response = requests.get("http://localhost:7860/health", timeout=5)
            if response.status_code == 200:
                print("✅ Health check passed")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check exception: {e}")
            return False
            
        # Check Gradio
        try:
            response = requests.get("http://localhost:7860/gradio", timeout=5)
            if response.status_code in [200, 307, 308]:
                print("✅ Gradio mount passed")
            else:
                print(f"❌ Gradio mount failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Gradio exception: {e}")
            return False
            
        print("✅ Verification successful!")
        return True
        
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    success = verify_deployment()
    sys.exit(0 if success else 1)
