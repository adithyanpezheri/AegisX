#!/usr/bin/env python3
"""
NetSurf Live Capture & Detection - Quick Setup Script

This script sets up and runs NetSurf with live capture and detection.
"""

import os
import sys
import subprocess
import platform

def check_python_version():
    """Check if Python 3.8+ is installed"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    print(f"✅ Python {sys.version.split()[0]} detected")
    return True

def install_requirements():
    """Install required packages"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def check_dependencies():
    """Check if all required packages are available"""
    print("\n🔍 Checking dependencies...")
    
    required_packages = [
        'flask',
        'flask_cors',
        'flask_socketio',
        'numpy',
        'pandas',
        'sklearn',
        'tensorflow',
        'socketio'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("   Run: pip install -r requirements.txt")
        return False
    
    print("\n✅ All dependencies present")
    return True

def check_models():
    """Check if trained models exist"""
    print("\n🤖 Checking models...")
    
    model_dir = os.path.join(os.path.dirname(__file__), 'saved_models')
    
    if not os.path.exists(model_dir):
        print(f"  ❌ No models directory. Train a model first in the Training tab.")
        return False
    
    models = os.listdir(model_dir)
    if models:
        print(f"  ✅ Found {len(models)} saved model(s):")
        for model in models:
            print(f"     - {model}")
        return True
    else:
        print(f"  ⚠️  No trained models found. Train one first!")
        return False

def start_server():
    """Start the NetSurf server"""
    print("\n🚀 Starting NetSurf server...")
    print("   " + "="*50)
    print("   🌐 Web Interface: http://localhost:5000")
    print("   📊 Live Capture: Ready for network traffic analysis")
    print("   🔌 WebSocket: Real-time anomaly notifications enabled")
    print("   " + "="*50)
    print("\n✨ Press Ctrl+C to stop the server\n")
    
    try:
        subprocess.call([sys.executable, "app.py"])
    except KeyboardInterrupt:
        print("\n\n✋ Server stopped")
        return True
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False

def main():
    """Main setup function"""
    print("="*60)
    print("  NetSurf - Network Intrusion Detection System")
    print("  Live Capture & Detection Setup")
    print("="*60)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Check if dependencies are installed
    if not check_dependencies():
        print("\n❓ Would you like to install missing dependencies? (y/n)")
        if input().lower() == 'y':
            if not install_requirements():
                return False
        else:
            return False
    
    # Check for trained models
    has_models = check_models()
    
    if not has_models:
        print("\n⚠️  No trained models found!")
        print("\n📝 To use live capture and detection:")
        print("   1. Start the server (continue below)")
        print("   2. Go to http://localhost:5000")
        print("   3. Go to the 'Training' tab")
        print("   4. Upload a network traffic CSV dataset")
        print("   5. Select a model type and train")
        print("   6. Once trained, go to 'Live Capture' tab")
    else:
        print("\n✅ Ready to use live capture and detection!")
    
    # Start server
    return start_server()

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
