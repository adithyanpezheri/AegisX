"""
NetSurf Configuration File
Customize settings for your deployment
"""

# Flask Configuration
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
FLASK_DEBUG = True

# File Upload Configuration
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {'csv'}
UPLOAD_FOLDER = 'uploads'
MODEL_FOLDER = 'saved_models'

# Kafka Configuration
KAFKA_ENABLED = True
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
KAFKA_TRAFFIC_TOPIC = 'network_traffic'
KAFKA_ALERT_TOPIC = 'security_alerts'
KAFKA_CONSUMER_GROUP = 'netsurf-consumers'

# Model Training Configuration
AUTOENCODER_CONFIG = {
    'epochs': 30,
    'batch_size': 1024,
    'validation_split': 0.1,
    'early_stopping_patience': 5,
    'reduce_lr_patience': 2
}

LSTM_CONFIG = {
    'window_size': 10,
    'epochs': 20,
    'batch_size': 512,
    'validation_split': 0.1,
    'early_stopping_patience': 4,
    'reduce_lr_patience': 2
}

ISOLATION_FOREST_CONFIG = {
    'n_estimators': 200,
    'max_samples': 0.8,
    'contamination': 'auto',
    'n_jobs': -1
}

# Detection Thresholds
ANOMALY_THRESHOLD_PERCENTILE = 95  # 95th percentile of normal traffic

# Live Capture Configuration
DEFAULT_NETWORK_INTERFACE = 'eth0'
PACKET_BUFFER_SIZE = 10
CAPTURE_TIMEOUT = 60  # seconds

# Logging Configuration
LOG_LEVEL = 'INFO'
LOG_FILE = 'netsurf.log'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Security Configuration
ENABLE_CORS = True
CORS_ORIGINS = '*'  # Set specific origins in production

# Performance Configuration
SCALER_TYPE = 'robust'  # 'robust', 'standard', 'minmax'
USE_GPU = False  # Set to True if TensorFlow GPU is available

# Feature Engineering
APPLY_LOG_TRANSFORM = True
CLIP_NEGATIVE_VALUES = True
REPLACE_INFINITY = True

# Data Preprocessing
DROP_COLUMNS = ['Label', 'Timestamp', 'Dst IP', 'Src IP', 'Flow ID']
