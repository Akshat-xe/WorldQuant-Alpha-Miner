"""
WorldQuant BRAIN - Quantum Portal
Root Entry Point for 'quant website'
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from web.server import app

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("\n[!] 'uvicorn' is not installed in your active Python environment.")
        print("    Please run:")
        print("      source venv/bin/activate")
        print("      python server.py")
        print("    Or launch via the self-bootstrapping script:")
        print("      ./start.sh\n")
        sys.exit(1)

    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"⚡ Starting Quantum Alpha Portal on http://{host}:{port}")
    uvicorn.run("web.server:app", host=host, port=port, reload=True)
