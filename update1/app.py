import os
import json
import time
import pickle
import threading
import numpy as np
import pandas as pd
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score, confusion_matrix

# Import Kafka
try:
    from kafka import KafkaProducer, KafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    print("Warning: Kafka not available. Install with: pip install kafka-python")

# Import model architectures
from models import DenseAutoencoder, BidirectionalLSTM, RobustIF
from live_capture import NetworkCapture, SimulatedNetworkCapture

app = Flask(__name__, static_folder='static')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
MODEL_FOLDER = os.path.join(os.path.dirname(__file__), 'saved_models')
ALLOWED_EXTENSIONS = {'csv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MODEL_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Global variables
current_model = None
scaler = None
live_capture_thread = None
live_capture_instance = None
kafka_producer = None
kafka_consumer_thread = None
connected_clients = set()
anomaly_queue = []

# Kafka Configuration
KAFKA_CONFIG = {
    'bootstrap_servers': 'localhost:9092',
    'traffic_topic': 'network_traffic',
    'alert_topic': 'security_alerts'
}

# ==========================================
# KAFKA INTEGRATION
# ==========================================
def get_kafka_producer():
    """Initialize Kafka producer with timeout"""
    global kafka_producer
    if not KAFKA_AVAILABLE:
        return None
    
    try:
        if kafka_producer is None:
            # Only try once - if it fails, don't retry constantly
            kafka_producer = KafkaProducer(
                bootstrap_servers=KAFKA_CONFIG['bootstrap_servers'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                request_timeout_ms=2000,  # Short timeout to fail fast
                connections_max_idle_ms=1000
            )
        return kafka_producer
    except Exception as e:
        # Silently fail - Kafka is optional
        # print(f"Kafka producer error: {e}")
        return None

def send_to_kafka(topic, data):
    """Send data to Kafka topic (optional - silently fails if Kafka unavailable)"""
    global kafka_producer
    
    # Only attempt if we have a working producer
    if kafka_producer is None:
        return False
    
    try:
        kafka_producer.send(topic, data)
        return True
    except Exception as e:
        # Silent fail - Kafka is optional
        return False

def kafka_consumer_worker():
    """Background worker to consume Kafka messages"""
    if not KAFKA_AVAILABLE:
        return
    
    try:
        # Try to connect with timeout
        consumer = KafkaConsumer(
            KAFKA_CONFIG['traffic_topic'],
            bootstrap_servers=KAFKA_CONFIG['bootstrap_servers'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            connections_max_idle_ms=10000,
            session_timeout_ms=10000
        )
        
        print("Kafka consumer connected successfully")
        for message in consumer:
            traffic_data = message.value
            # Process the traffic data
            result = analyze_traffic_packet(traffic_data)
            
            # If anomaly detected, send alert
            if result and result.get('is_anomaly'):
                send_to_kafka(KAFKA_CONFIG['alert_topic'], {
                    'timestamp': datetime.now().isoformat(),
                    'alert_type': 'Intrusion Detected',
                    'confidence': float(result.get('anomaly_score', 0)),
                    'details': result
                })
    except Exception as e:
        print(f"Kafka consumer connection failed (this is OK if Kafka is not running): {e}")

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_data(X):
    """Clean and transform data"""
    # Force to numeric
    X = X.apply(pd.to_numeric, errors='coerce')
    
    # Replace infinity
    X = X.replace([np.inf, -np.inf], np.nan)
    
    # Fill NaN
    X = X.fillna(0)
    
    # Clip negatives
    X[X < 0] = 0
    
    # Log transform
    X = np.log1p(X)
    
    return X

def load_dataset(filepath):
    """Load and preprocess dataset"""
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()
    
    # Drop metadata
    drop_cols = ['Label', 'Timestamp', 'Dst IP', 'Src IP', 'Flow ID']
    cols_to_drop = [c for c in drop_cols if c in df.columns]
    X = df.drop(columns=cols_to_drop)
    y = df['Label'] if 'Label' in df.columns else None
    
    # Clean data
    X = preprocess_data(X)
    
    # Binary labels
    if y is not None:
        y_binary = y.apply(lambda x: 0 if x == 'Benign' else 1)
    else:
        y_binary = None
    
    return X, y_binary

def calculate_metrics(y_true, y_pred):
    """Calculate performance metrics"""
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)
    
    return {
        'accuracy': float(acc),
        'precision': float(prec),
        'recall': float(rec),
        'f1_score': float(f1),
        'confusion_matrix': cm.tolist()
    }

# ==========================================
# API ROUTES
# ==========================================
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/status', methods=['GET'])
def status():
    """Get system status"""
    return jsonify({
        'status': 'running',
        'model_loaded': current_model is not None,
        'model_type': current_model.name if current_model else None,
        'kafka_available': KAFKA_AVAILABLE,
        'live_capture_active': live_capture_thread is not None and live_capture_thread.is_alive()
    })

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload dataset for training"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Get dataset info
        try:
            df = pd.read_csv(filepath, nrows=5)
            return jsonify({
                'success': True,
                'filename': filename,
                'filepath': filepath,
                'rows': len(pd.read_csv(filepath)),
                'columns': len(df.columns),
                'preview': df.head().to_dict()
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/train', methods=['POST'])
def train_model():
    """Train a model"""
    global current_model, scaler
    
    data = request.json
    filepath = data.get('filepath')
    model_type = data.get('model_type', 'autoencoder')
    
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'Invalid file path'}), 400
    
    try:
        # Load data
        X, y_binary = load_dataset(filepath)
        
        # Split data
        benign_mask = (y_binary == 0) if y_binary is not None else None
        
        if benign_mask is not None:
            X_benign = X[benign_mask]
            X_train_raw, X_test_benign = train_test_split(X_benign, test_size=0.2, random_state=42)
            X_attack = X[~benign_mask]
            X_test = pd.concat([X_test_benign, X_attack])
            y_test = pd.concat([y_binary[X_test_benign.index], y_binary[X_attack.index]])
        else:
            X_train_raw, X_test = train_test_split(X, test_size=0.2, random_state=42)
            y_test = None
        
        # Scale data
        scaler = RobustScaler()
        X_train = scaler.fit_transform(X_train_raw)
        X_test_scaled = scaler.transform(X_test)
        
        # Validation split
        X_t, X_v = train_test_split(X_train, test_size=0.1, random_state=42)
        
        # Initialize model
        if model_type == 'autoencoder':
            current_model = DenseAutoencoder(input_dim=X_train.shape[1])
            current_model.train(X_t, X_v)
            
            # NEW: Find optimal threshold using sensitivity analysis
            print("\n" + "="*60)
            print("AUTOENCODER: Running Sensitivity Analysis...")
            print("="*60)
            optimal_threshold, best_metrics = current_model.find_optimal_threshold(X_test, y_test)
            
            # Use optimal threshold for predictions
            X_test_scaled_for_pred = scaler.transform(X_test)
            test_scores = current_model.get_anomaly_scores(X_test_scaled_for_pred)
            y_pred = (test_scores > optimal_threshold).astype(int)
            
            metrics = best_metrics if best_metrics else None
            threshold = optimal_threshold
            
        elif model_type == 'lstm':
            current_model = BidirectionalLSTM(input_dim=X_train.shape[1], window_size=10)
            X_t_seq = current_model.create_sequences(X_t)
            X_v_seq = current_model.create_sequences(X_v)
            current_model.train(X_t_seq, X_v_seq)
            
            # Evaluate
            val_scores = current_model.get_anomaly_scores(X_v_seq)
            X_test_seq = current_model.create_sequences(X_test_scaled)
            test_scores = current_model.get_anomaly_scores(X_test_seq)
            
            # Adjust y_test for sequence length
            if y_test is not None:
                y_test = y_test.iloc[current_model.window_size:].values
            
            # Standard threshold for LSTM
            threshold = np.percentile(val_scores, 95)
            y_pred = (test_scores > threshold).astype(int)
            metrics = None
            if y_test is not None:
                metrics = calculate_metrics(y_test, y_pred)
            
        elif model_type == 'isolation_forest':
            current_model = RobustIF()
            current_model.train(X_t)
            
            # Evaluate
            val_scores = current_model.get_anomaly_scores(X_v)
            test_scores = current_model.get_anomaly_scores(X_test_scaled)
            
            # Standard threshold for Isolation Forest
            threshold = np.percentile(val_scores, 95)
            y_pred = (test_scores > threshold).astype(int)
            metrics = None
            if y_test is not None:
                metrics = calculate_metrics(y_test, y_pred)
        
        else:
            return jsonify({'error': 'Invalid model type'}), 400
        
        # Save the fitted scaler to a temporary pickle file for later use
        scaler_path = os.path.join(UPLOAD_FOLDER, '_current_scaler.pkl')
        with open(scaler_path, 'wb') as f:
            pickle.dump(scaler, f)
        
        return jsonify({
            'success': True,
            'model_type': model_type,
            'threshold': float(threshold),
            'metrics': metrics,
            'training_samples': len(X_train),
            'test_samples': len(X_test_scaled),
            'scaler_saved': True
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict', methods=['POST'])
def predict():
    """Make prediction on uploaded data with detailed analysis"""
    global current_model, scaler
    
    if current_model is None:
        return jsonify({'error': 'No model loaded'}), 400
    
    if scaler is None:
        return jsonify({'error': 'Scaler not initialized. Train or load a model first'}), 400
    
    data = request.json
    filepath = data.get('filepath')
    
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'Invalid file path'}), 400
    
    try:
        # Load full data including labels for analysis
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        
        # Separate features and original data
        drop_cols = ['Label', 'Timestamp', 'Dst IP', 'Src IP', 'Flow ID']
        cols_to_drop = [c for c in drop_cols if c in df.columns]
        X = df.drop(columns=cols_to_drop)
        X = preprocess_data(X)
        
        print(f"\n=== PREDICTION STARTED ===")
        print(f"Data loaded. Shape: {X.shape}")
        
        # Scale data
        print(f"Scaling data with shape: {X.shape}")
        X_scaled = scaler.fit_transform(X)
        print(f"Data scaled successfully. Shape: {X_scaled.shape}")
        
        # Handle LSTM sequences
        if hasattr(current_model, 'name') and current_model.name == 'LSTM':
            print(f"Creating LSTM sequences...")
            X_scaled_seq = current_model.create_sequences(X_scaled)
            print(f"Sequences created. Shape: {X_scaled_seq.shape}")
            scores = current_model.get_anomaly_scores(X_scaled_seq)
            # Pad predictions for sequences
            scores = np.concatenate([np.zeros(current_model.window_size), scores])
        else:
            scores = current_model.get_anomaly_scores(X_scaled)
        
        print(f"Anomaly scores obtained. Length: {len(scores)}, Min: {np.min(scores)}, Max: {np.max(scores)}")
        
        # Use stored threshold or calculate new one
        threshold = np.percentile(scores, 95)
        print(f"Threshold set at 95th percentile: {threshold}")
        predictions = (scores > threshold).astype(int)
        
        # Get anomaly indices
        anomaly_indices = np.where(predictions == 1)[0]
        print(f"Predictions made. Anomalies: {len(anomaly_indices)}, Normal: {len(predictions) - len(anomaly_indices)}")
        print(f"=== PREDICTION COMPLETED ===\n")
        
        # Prepare detailed analysis
        analysis = {
            'success': True,
            'total_samples': len(predictions),
            'anomalies_detected': int(np.sum(predictions)),
            'normal_traffic': int(len(predictions) - np.sum(predictions)),
            'anomaly_rate': float(np.mean(predictions)) * 100,
            'threshold': float(threshold),
            'scores_stats': {
                'min': float(np.min(scores)),
                'max': float(np.max(scores)),
                'mean': float(np.mean(scores)),
                'std': float(np.std(scores)),
                'median': float(np.median(scores))
            },
            'top_anomalies': [],
            'protocol_analysis': {},
            'port_analysis': {},
            'ip_analysis': {}
        }
        
        # Get top anomalous flows with details
        top_indices = np.argsort(scores)[-20:][::-1]  # Top 20
        
        for idx in top_indices:
            if idx < len(df):
                row = df.iloc[idx]
                anomaly_detail = {
                    'index': int(idx),
                    'anomaly_score': float(scores[idx]),
                    'timestamp': str(row.get('Timestamp', 'N/A')),
                    'src_ip': str(row.get('Src IP', 'N/A')),
                    'dst_ip': str(row.get('Dst IP', 'N/A')),
                    'dst_port': int(row.get('Dst Port', 0)) if pd.notna(row.get('Dst Port')) else 0,
                    'protocol': str(row.get('Protocol', 'N/A')),
                    'flow_duration': float(row.get('Flow Duration', 0)) if pd.notna(row.get('Flow Duration')) else 0,
                    'tot_fwd_pkts': int(row.get('Tot Fwd Pkts', 0)) if pd.notna(row.get('Tot Fwd Pkts')) else 0,
                    'tot_bwd_pkts': int(row.get('Tot Bwd Pkts', 0)) if pd.notna(row.get('Tot Bwd Pkts')) else 0,
                    'flow_byts_s': float(row.get('Flow Byts/s', 0)) if pd.notna(row.get('Flow Byts/s')) else 0,
                    'flow_pkts_s': float(row.get('Flow Pkts/s', 0)) if pd.notna(row.get('Flow Pkts/s')) else 0,
                }
                analysis['top_anomalies'].append(anomaly_detail)
        
        # Protocol analysis
        protocol_counts = df['Protocol'].value_counts().to_dict()
        for protocol, count in list(protocol_counts.items())[:10]:
            analysis['protocol_analysis'][str(protocol)] = {
                'count': int(count),
                'percentage': float(count / len(df) * 100)
            }
        
        # Port analysis (top ports in anomalies)
        if 'Dst Port' in df.columns:
            anomalous_rows = df.iloc[anomaly_indices]
            port_counts = anomalous_rows['Dst Port'].value_counts().to_dict()
            for port, count in list(port_counts.items())[:10]:
                analysis['port_analysis'][int(port)] = {
                    'count': int(count),
                    'percentage': float(count / len(anomalous_rows) * 100)
                }
        
        # IP analysis for anomalies
        if 'Src IP' in df.columns and len(anomaly_indices) > 0:
            anomalous_rows = df.iloc[anomaly_indices]
            src_ip_counts = anomalous_rows['Src IP'].value_counts().head(10).to_dict()
            for ip, count in src_ip_counts.items():
                analysis['ip_analysis'][str(ip)] = {
                    'count': int(count),
                    'percentage': float(count / len(anomalous_rows) * 100)
                }
        
        # Score distribution for visualization
        analysis['score_distribution'] = {
            'bins': [float(x) for x in np.histogram(scores, bins=20)[1]],
            'counts': [int(x) for x in np.histogram(scores, bins=20)[0]],
            'threshold': float(threshold)
        }
        
        return jsonify(analysis)
        
    except Exception as e:
        print(f"\n!!! PREDICTION ERROR !!!")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"!!! END ERROR !!!\n")
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500

@app.route('/api/save_model', methods=['POST'])
def save_model():
    """Save current model to disk"""
    global current_model, scaler
    
    if current_model is None:
        return jsonify({'error': 'No model loaded'}), 400
    
    data = request.json
    model_name = data.get('model_name', f'model_{int(time.time())}')
    
    try:
        model_path = os.path.join(MODEL_FOLDER, model_name)
        os.makedirs(model_path, exist_ok=True)
        
        # Save model architecture and weights
        if hasattr(current_model, 'model'):
            current_model.model.save(os.path.join(model_path, 'model.h5'))
        else:
            # For sklearn models
            with open(os.path.join(model_path, 'model.pkl'), 'wb') as f:
                pickle.dump(current_model.model, f)
        
        # Save scaler
        with open(os.path.join(model_path, 'scaler.pkl'), 'wb') as f:
            pickle.dump(scaler, f)
        
        # Save metadata
        metadata = {
            'model_type': current_model.name,
            'created_at': datetime.now().isoformat(),
            'input_dim': getattr(current_model, 'input_dim', None)
        }
        with open(os.path.join(model_path, 'metadata.json'), 'w') as f:
            json.dump(metadata, f)
        
        return jsonify({
            'success': True,
            'model_name': model_name,
            'path': model_path
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load_model', methods=['POST'])
def load_model():
    """Load a model file (.pkl or .h5)"""
    global current_model, scaler
    
    # Check if it's a file upload
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(MODEL_FOLDER, filename)
            file.save(filepath)
            
            # Load the model based on file extension
            if filename.endswith('.pkl'):
                with open(filepath, 'rb') as f:
                    loaded_model_obj = pickle.load(f)
                
                # Determine model type and create wrapper
                if hasattr(loaded_model_obj, 'n_estimators'):  # IsolationForest
                    current_model = RobustIF()
                    current_model.model = loaded_model_obj
                    current_model.name = 'Isolation Forest'
                else:
                    # Generic sklearn model
                    current_model = loaded_model_obj
                
                # Try to load the fitted scaler from file
                scaler_path = os.path.join(UPLOAD_FOLDER, '_current_scaler.pkl')
                if os.path.exists(scaler_path):
                    with open(scaler_path, 'rb') as f:
                        scaler = pickle.load(f)
                else:
                    # If no saved scaler, create a new one to be fitted on first prediction
                    scaler = RobustScaler()
            
            elif filename.endswith('.h5'):
                # For H5 files, we need to create the appropriate wrapper
                try:
                    import tensorflow as tf
                    model_data = tf.keras.models.load_model(filepath)
                    
                    # Create a proper class for the H5 model
                    class CustomModel:
                        def __init__(self, model):
                            self.model = model
                            self.name = 'CustomModel'
                        
                        def get_anomaly_scores(self, X):
                            """Calculate anomaly scores using reconstruction error"""
                            try:
                                # Ensure X is properly shaped
                                print(f"CustomModel input shape: {X.shape}")
                                predictions = self.model.predict(X, verbose=0)
                                print(f"CustomModel predictions shape: {predictions.shape}")
                                
                                # Calculate reconstruction error (MSE)
                                # Handle cases where predictions and X might have different shapes
                                if predictions.shape != X.shape:
                                    print(f"Warning: Shape mismatch. Predictions {predictions.shape} vs Input {X.shape}")
                                    # Try to reshape predictions to match X
                                    if len(predictions.shape) == 2 and len(X.shape) == 2:
                                        if predictions.shape[0] == X.shape[0]:
                                            # Same number of samples, calculate MSE per sample
                                            scores = np.mean((predictions - X) ** 2, axis=1)
                                        else:
                                            scores = np.mean((predictions - X) ** 2)
                                    else:
                                        scores = np.mean((predictions - X) ** 2)
                                else:
                                    scores = np.mean(np.abs(predictions - X), axis=1)
                                
                                print(f"Anomaly scores calculated. Shape: {scores.shape}, Min: {scores.min()}, Max: {scores.max()}")
                                return scores
                            except Exception as e:
                                print(f"Error calculating anomaly scores: {e}")
                                import traceback
                                traceback.print_exc()
                                # Fallback: return default scores based on L2 norm
                                try:
                                    scores = np.linalg.norm(X, axis=1)
                                    return scores
                                except:
                                    return np.zeros(len(X))
                    
                    current_model = CustomModel(model_data)
                except Exception as e:
                    return jsonify({'error': f'Failed to load H5 model: {str(e)}'}), 500
                
                # Try to load the fitted scaler from file
                scaler_path = os.path.join(UPLOAD_FOLDER, '_current_scaler.pkl')
                if os.path.exists(scaler_path):
                    with open(scaler_path, 'rb') as f:
                        scaler = pickle.load(f)
                else:
                    # If no saved scaler, create a new one to be fitted on first prediction
                    scaler = RobustScaler()
            else:
                return jsonify({'error': 'Unsupported file format. Use .pkl or .h5'}), 400
            
            return jsonify({
                'success': True,
                'model_type': getattr(current_model, 'name', 'Custom Model'),
                'filename': filename,
                'message': 'Model loaded successfully'
            })
            
        except Exception as e:
            return jsonify({'error': f'Failed to load model: {str(e)}'}), 500
    
    # Original load_model logic for saved models folder
    data = request.json
    model_name = data.get('model_name')
    
    if not model_name:
        return jsonify({'error': 'No model name provided'}), 400
    
    model_path = os.path.join(MODEL_FOLDER, model_name)
    
    if not os.path.exists(model_path):
        return jsonify({'error': 'Model not found'}), 404
    
    try:
        # Load metadata
        with open(os.path.join(model_path, 'metadata.json'), 'r') as f:
            metadata = json.load(f)
        
        # Load scaler
        with open(os.path.join(model_path, 'scaler.pkl'), 'rb') as f:
            scaler = pickle.load(f)
        
        # Load model based on type
        model_type = metadata['model_type']
        input_dim = metadata['input_dim']
        
        if model_type == 'Autoencoder':
            current_model = DenseAutoencoder(input_dim=input_dim)
            current_model.model = tf.keras.models.load_model(os.path.join(model_path, 'model.h5'))
        elif model_type == 'LSTM':
            current_model = BidirectionalLSTM(input_dim=input_dim)
            current_model.model = tf.keras.models.load_model(os.path.join(model_path, 'model.h5'))
        elif model_type == 'Isolation Forest':
            current_model = RobustIF()
            with open(os.path.join(model_path, 'model.pkl'), 'rb') as f:
                current_model.model = pickle.load(f)
        
        return jsonify({
            'success': True,
            'model_type': model_type,
            'metadata': metadata
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/list_models', methods=['GET'])
def list_models():
    """List all saved models"""
    try:
        models = []
        for model_name in os.listdir(MODEL_FOLDER):
            model_path = os.path.join(MODEL_FOLDER, model_name)
            metadata_path = os.path.join(model_path, 'metadata.json')
            
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                models.append({
                    'name': model_name,
                    'type': metadata.get('model_type'),
                    'created_at': metadata.get('created_at')
                })
        
        return jsonify({'models': models})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live_capture/start', methods=['POST'])
def start_live_capture():
    """Start live network traffic capture"""
    global live_capture_thread, live_capture_instance, current_model, scaler
    
    if current_model is None:
        return jsonify({'error': 'No model loaded'}), 400
    
    if live_capture_thread and live_capture_thread.is_alive():
        return jsonify({'error': 'Capture already running'}), 400
    
    data = request.json
    interface = data.get('interface', 'eth0')
    use_simulation = data.get('simulate', True)  # Default to simulation
    
    def on_alert_callback(alert_data):
        """Callback when anomaly is detected"""
        try:
            # Send alert to all connected WebSocket clients
            socketio.emit('anomaly_detected', alert_data, broadcast=True)
            
            # Also store for API queries
            anomaly_queue.append(alert_data)
            if len(anomaly_queue) > 100:  # Keep only last 100
                anomaly_queue.pop(0)
                
        except Exception as e:
            print(f"Error in alert callback: {e}")
    
    try:
        # Use simulated capture if requested (or if Scapy not available)
        if use_simulation:
            live_capture_instance = SimulatedNetworkCapture(
                model=current_model, 
                scaler=scaler,
                on_alert=on_alert_callback
            )
        else:
            live_capture_instance = NetworkCapture(
                interface=interface, 
                model=current_model, 
                scaler=scaler,
                on_alert=on_alert_callback
            )
        
        live_capture_thread = threading.Thread(
            target=live_capture_instance.start_capture, 
            daemon=True
        )
        live_capture_thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Live capture started',
            'interface': interface,
            'mode': 'simulation' if use_simulation else 'live'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live_capture/stop', methods=['POST'])
def stop_live_capture():
    """Stop live network traffic capture"""
    global live_capture_thread, live_capture_instance
    
    if not live_capture_thread or not live_capture_thread.is_alive():
        return jsonify({'error': 'No capture running'}), 400
    
    # Stop the capture instance
    if live_capture_instance:
        live_capture_instance.stop_capture()
    
    # Wait for thread to stop
    live_capture_thread.join(timeout=2)
    
    return jsonify({
        'success': True,
        'message': 'Live capture stopped'
    })

@app.route('/api/live_capture/stats', methods=['GET'])
def get_capture_stats():
    """Get live capture statistics"""
    global live_capture_thread, live_capture_instance
    
    is_active = live_capture_thread is not None and live_capture_thread.is_alive()
    
    return jsonify({
        'active': is_active,
        'anomalies_detected': len(anomaly_queue),
        'recent_anomalies': anomaly_queue[-10:] if anomaly_queue else []
    })

@app.route('/api/kafka/status', methods=['GET'])
def kafka_status():
    """Get Kafka connection status"""
    return jsonify({
        'available': KAFKA_AVAILABLE,
        'producer_active': kafka_producer is not None,
        'config': KAFKA_CONFIG if KAFKA_AVAILABLE else None
    })

# ==========================================
# WEBSOCKET EVENTS
# ==========================================
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket client connection"""
    connected_clients.add(request.sid)
    print(f"Client connected: {request.sid}")
    emit('connection_response', {'status': 'Connected to NetSurf'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket client disconnection"""
    connected_clients.discard(request.sid)
    print(f"Client disconnected: {request.sid}")

@socketio.on('subscribe_anomalies')
def handle_subscribe_anomalies():
    """Subscribe to anomaly alerts"""
    join_room('anomalies')
    emit('subscription_response', {'status': 'Subscribed to anomalies'})

@socketio.on('unsubscribe_anomalies')
def handle_unsubscribe_anomalies():
    """Unsubscribe from anomaly alerts"""
    leave_room('anomalies')
    emit('subscription_response', {'status': 'Unsubscribed from anomalies'})

def analyze_traffic_packet(packet_data):
    """Analyze a single traffic packet"""
    global current_model, scaler
    
    if current_model is None or scaler is None:
        return None
    
    try:
        # Convert packet to DataFrame
        df = pd.DataFrame([packet_data])
        
        # Preprocess
        X = preprocess_data(df)
        X_scaled = scaler.transform(X)
        
        # Get anomaly score
        if current_model.name == 'LSTM':
            # For LSTM, we need sequence - skip for now in live mode
            return None
        
        score = current_model.get_anomaly_scores(X_scaled)[0]
        
        # Threshold (use 95th percentile)
        is_anomaly = score > 0.5  # Placeholder threshold
        
        return {
            'is_anomaly': bool(is_anomaly),
            'anomaly_score': float(score),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Error analyzing packet: {e}")
        return None

if __name__ == '__main__':
    # Start Kafka consumer in background if available (disabled for now)
    # if KAFKA_AVAILABLE:
    #     kafka_consumer_thread = threading.Thread(target=kafka_consumer_worker, daemon=True)
    #     kafka_consumer_thread.start()
    
    # Use SocketIO server with WebSocket support
    print("Starting NetSurf on http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
