# NetSurf - Network Intrusion Detection System

A comprehensive, AI-powered Network Intrusion Detection System with real-time monitoring, multiple ML models, and a modern web interface.

## 🚀 Quick Start (2 minutes)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start server
python app.py

# 3. Open browser
http://localhost:5000
```

## 🎯 Features

- **Multiple ML Models**: Autoencoder, LSTM, Isolation Forest
- **Live Monitoring**: Real-time packet capture with WebSocket alerts (<100ms latency)
- **Live Feed**: Threat visualization with color-coded alerts
- **Model Training**: Train on your own datasets
- **Easy to Use**: Simple web interface, no command line needed

## 📖 Usage

### Training Tab
1. Click "Choose File" to upload a CSV dataset
2. Select model: **Autoencoder** (best), **LSTM** (for sequences), or **Isolation Forest** (fastest)
3. Click "Start Training" 
4. View metrics: Accuracy, Precision, Recall, F1-Score

### Prediction/Analysis Tab
1. Upload network traffic CSV
2. Click "Analyze Traffic"
3. View results: total samples, normal vs anomalous, anomaly scores, charts

### Live Capture Tab
1. Select mode: **Simulated** (default, no special permissions) or **Real** (requires admin/root)
2. Click "Start Monitoring"
3. Watch real-time detections appear in live feed
4. Each alert shows: timestamp, IPs, ports, protocol, threat level (Critical/High/Medium)
5. Click "Stop Monitoring" when done

**Threat Levels:**
- 🔴 Critical (>70%): Definitely malicious
- 🟠 High (50-70%): Likely malicious  
- 🟡 Medium (<50%): Possibly anomalous

## 🏗️ Architecture

- **Backend**: Flask 3.0 + SocketIO 5.3 (real-time WebSocket)
- **Models**: Autoencoder, LSTM, Isolation Forest (TensorFlow/Scikit-learn)
- **Capture**: Scapy for real network packets, simulated mode for testing
- **Frontend**: HTML/JS with live WebSocket feed
- **Data**: Pandas/NumPy for preprocessing

Key files:
- `app.py` - Flask server with WebSocket support
- `live_capture.py` - Packet capture and ML inference
- `models.py` - ML model definitions
- `index.html` + `app.js` - Web interface

## 🔌 Configuration

Edit `config.py` to customize:
```python
ANOMALY_THRESHOLD = 0.5      # Detection sensitivity (0.0-1.0)
CAPTURE_BUFFER_SIZE = 5      # Packets per batch
FEED_HISTORY_SIZE = 20       # Max anomalies in live feed
```

## ⚙️ Requirements

- Python 3.8+
- TensorFlow 2.15+
- Scikit-learn 1.4+
- Flask 3.0+
- Flask-SocketIO 5.3+

All listed in `requirements.txt`

## 🐛 Troubleshooting

**Port 5000 already in use?**
```bash
# Windows: Find process using port 5000
netstat -ano | findstr :5000

# Use different port
python app.py --port 5001
```

**WebSocket not connecting?**
- Check browser console (F12) for errors
- Verify server running: `python app.py` should show "Running on..."
- Try refreshing page or restarting browser

**No anomalies in live capture?**
- Ensure model is trained first
- Lower threshold in `config.py`
- Check simulated mode is enabled

**High CPU/Memory?**
- Use Isolation Forest (fastest)
- Reduce CAPTURE_BUFFER_SIZE
- Use simulated instead of real capture
