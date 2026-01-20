
import streamlit as st
import pandas as pd
import numpy as np
import time
import os
import plotly.express as px
import plotly.graph_objects as go

# --- Machine Learning Imports ---
import tensorflow as tf
from tensorflow.keras.models import Model, Sequential
from tensorflow.keras.layers import Input, Dense, Dropout, BatchNormalization, LSTM, RepeatVector, TimeDistributed, Bidirectional, GaussianNoise
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.regularizers import l2
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

# --- Page Configuration ---
st.set_page_config(
    page_title="Network Traffic Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- UTILS & DATA LOADING ---

class DataLoader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.scaler = RobustScaler()
        self.columns = None
    
    @st.cache_data(show_spinner=False)
    def load_raw_data(_self, filepath, nrows=None):
        """Loads data with basic cleaning."""
        try:
            df = pd.read_csv(filepath, nrows=nrows)
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None

        df.columns = df.columns.str.strip()
        
        # Drop Metadata
        drop_cols = ['Label', 'Timestamp', 'Dst IP', 'Src IP', 'Flow ID'] 
        cols_to_drop = [c for c in drop_cols if c in df.columns]
        X = df.drop(columns=cols_to_drop)
        y = df['Label']

        # Cleaning Pipeline (Consolidated from scripts)
        # 1. Force to numeric
        X = X.apply(pd.to_numeric, errors='coerce')
        # 2. Infinite -> NaN
        X = X.replace([np.inf, -np.inf], np.nan)
        # 3. NaNs -> 0
        X = X.fillna(0)
        # 4. Clip negatives
        X[X < 0] = 0
        
        # 5. Log Transform
        X = np.log1p(X)
        
        return X, y

    def preprocess_and_split(self, X, y, test_size=0.2, semi_supervised=False):
        """
        Splits data.
        If semi_supervised=True, Train set will contain ONLY BENIGN data.
        """
        y_binary = y.apply(lambda x: 0 if x == 'Benign' else 1)
        
        if semi_supervised:
            # For Autoencoder / Isolation Forest / LSTM
            benign_mask = (y_binary == 0)
            X_benign = X[benign_mask]
            
            # Train only on Benign
            X_train, X_test_benign = train_test_split(X_benign, test_size=test_size, random_state=42)
            
            # Test on Mixed (remaining benign + all attacks)
            X_attack = X[~benign_mask]
            y_attack = y_binary[~benign_mask]
            
            X_test = pd.concat([X_test_benign, X_attack])
            y_test = pd.concat([pd.Series(0, index=X_test_benign.index), y_attack])
            
            return X_train, X_test, y_test
        else:
            # For RF / SVM
            return train_test_split(X, y_binary, test_size=test_size, random_state=42)

# --- MODELS ---

class AutoencoderModel:
    def __init__(self, input_dim):
        self.input_dim = input_dim
        self.model = self._build_model()
        self.scaler = RobustScaler()
        self.threshold = None

    def _build_model(self):
        # Code from au.py
        input_layer = Input(shape=(self.input_dim,))
        x = Dense(64, activation='relu')(input_layer)
        x = BatchNormalization()(x)
        x = Dropout(0.2)(x)
        x = Dense(32, activation='relu')(x)
        x = BatchNormalization()(x)
        encoded = Dense(16, activation='relu')(x) # Bottleneck
        x = Dense(32, activation='relu')(encoded)
        x = BatchNormalization()(x)
        x = Dense(64, activation='relu')(x)
        x = BatchNormalization()(x)
        decoded = Dense(self.input_dim, activation='linear')(x)
        
        ae = Model(inputs=input_layer, outputs=decoded)
        ae.compile(optimizer='adam', loss='huber')
        return ae

    def train(self, X_train):
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_t, X_v = train_test_split(X_train_scaled, test_size=0.1, random_state=42)
        
        with st.spinner("Training Autoencoder..."):
            history = self.model.fit(
                X_t, X_t,
                epochs=20, # Reduced slightly for interactive speed
                batch_size=1024,
                shuffle=True,
                validation_data=(X_v, X_v),
                verbose=0,
                callbacks=[EarlyStopping(monitor='val_loss', patience=3, restore_best_weights=True)]
            )
        
        # Set threshold (95th percentile of validation error)
        val_preds = self.model.predict(X_v, verbose=0)
        val_errors = np.mean(np.abs(val_preds - X_v), axis=1)
        self.threshold = np.percentile(val_errors, 95)
        
        return history

    def predict_anomaly_score(self, X):
        X_scaled = self.scaler.transform(X)
        preds = self.model.predict(X_scaled, verbose=0)
        errors = np.mean(np.abs(preds - X_scaled), axis=1)
        return errors, (errors > self.threshold).astype(int)

class RobustIsolationForest:
    def __init__(self):
        self.model = IsolationForest(n_estimators=100, max_samples=0.8, n_jobs=-1, random_state=42)
        self.scaler = RobustScaler()
        self.threshold = None

    def train(self, X_train):
        X_train_scaled = self.scaler.fit_transform(X_train)
        with st.spinner("Training Isolation Forest..."):
            self.model.fit(X_train_scaled)
        
        # Calculate threshold
        # score_samples returns negative scores. Lower = Abnormal.
        # We invert so Higher = Abnormal.
        scores = -self.model.score_samples(X_train_scaled)
        self.threshold = np.percentile(scores, 95)

    def predict_anomaly_score(self, X):
        X_scaled = self.scaler.transform(X)
        scores = -self.model.score_samples(X_scaled)
        return scores, (scores > self.threshold).astype(int)

class LSTMModel:
    def __init__(self, input_dim, window_size=10):
        self.input_dim = input_dim
        self.window_size = window_size
        self.model = self._build_model()
        self.scaler = RobustScaler()
        self.threshold = None

    def _build_model(self):
        # Code from lstm.py
        model = Sequential()
        model.add(Input(shape=(self.window_size, self.input_dim)))
        model.add(GaussianNoise(0.2))
        model.add(Bidirectional(LSTM(64, activation='tanh', return_sequences=True, kernel_regularizer=l2(0.001))))
        model.add(BatchNormalization())
        model.add(Dropout(0.3))
        model.add(Bidirectional(LSTM(16, activation='tanh', return_sequences=False)))
        model.add(BatchNormalization())
        model.add(RepeatVector(self.window_size)) # Bottleneck
        model.add(Bidirectional(LSTM(16, activation='tanh', return_sequences=True)))
        model.add(BatchNormalization())
        model.add(Bidirectional(LSTM(64, activation='tanh', return_sequences=True)))
        model.add(BatchNormalization())
        model.add(Dropout(0.3))
        model.add(TimeDistributed(Dense(self.input_dim, activation='linear')))
        model.compile(optimizer='adam', loss='huber')
        return model

    def create_sequences(self, X):
        Xs = []
        for i in range(len(X) - self.window_size):
            Xs.append(X[i:(i + self.window_size)])
        return np.array(Xs)

    def train(self, X_train):
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_seq = self.create_sequences(X_train_scaled)
        X_t, X_v = train_test_split(X_seq, test_size=0.1, random_state=42)
        
        with st.spinner("Training LSTM (this might take a while)..."):
            self.model.fit(
                X_t, X_t,
                epochs=10, 
                batch_size=512, 
                validation_data=(X_v, X_v),
                verbose=0,
                callbacks=[EarlyStopping(monitor='val_loss', patience=3)]
            )
            
        # Threshold
        val_preds = self.model.predict(X_v, verbose=0, batch_size=512)
        val_errors = np.mean(np.abs(val_preds - X_v), axis=(1, 2))
        self.threshold = np.percentile(val_errors, 95)

    def predict_anomaly_score(self, X):
        # Handle single live batch vs bulk test
        X_scaled = self.scaler.transform(X)
        
        # If we have less data than window size, pad or error (simple handling here: need at least window_size)
        if len(X_scaled) <= self.window_size:
             # Basic fallback for demo: return zeros
             return np.zeros(len(X)), np.zeros(len(X))

        X_seq = self.create_sequences(X_scaled)
        preds = self.model.predict(X_seq, verbose=0)
        errors = np.mean(np.abs(preds - X_seq), axis=(1, 2))
        
        # Pad beginning to match index
        padded_errors = np.pad(errors, (self.window_size, 0), mode='edge')
        return padded_errors, (padded_errors > self.threshold).astype(int)

# --- MAIN APP ---

def main():
    st.title("🛡️ Unified Network Traffic Analyzer")
    st.markdown("### Real-time Anomaly Detection & Model Benchmarking")

    # --- SIDEBAR: Config ---
    st.sidebar.header("Configuration")
    
    # Dataset Selection
    dataset_options = ["02-14-2018.csv", "03-02-2018.csv"]
    # Check if files exist
    available_datasets = [f for f in dataset_options if os.path.exists(f)]
    if not available_datasets:
        st.error("No CSV files found (02-14-2018.csv or 03-02-2018.csv). Please make sure they are in the directory.")
        return

    selected_file = st.sidebar.selectbox("Select Dataset", available_datasets)
    
    # Model Selection
    model_type = st.sidebar.selectbox("Select Model", ["Autoencoder", "Isolation Forest", "LSTM"])
    
    # Params
    st.sidebar.subheader("Parameters")
    train_size = st.sidebar.slider("Training Size (Rows)", 1000, 50000, 10000)
    
    # --- DATA LOADING ---
    loader = DataLoader(selected_file)
    # Load separate subsample for "Live" simulation to avoid data leakage conceptually (though we just stream from file)
    
    if 'model' not in st.session_state:
        st.session_state.model = None
    if 'is_trained' not in st.session_state:
        st.session_state.is_trained = None

    # --- TABS ---
    tab1, tab2 = st.tabs(["📊 Training & Benchmark", "📡 Live Monitor"])

    with tab1:
        st.header(f"Train {model_type}")
        
        if st.button("Initialize & Train Model"):
            # Load Data
            with st.spinner("Loading and Cleaning Data..."):
                X, y = loader.load_raw_data(selected_file, nrows=train_size*2) # Load enough for train + test
                
            # Split
            st.write(f"Data Loaded: {X.shape}")
            X_train, X_test, y_test = loader.preprocess_and_split(X, y, semi_supervised=True)
            
            # Init Model
            input_dim = X_train.shape[1]
            if model_type == "Autoencoder":
                model = AutoencoderModel(input_dim)
            elif model_type == "Isolation Forest":
                model = RobustIsolationForest()
            elif model_type == "LSTM":
                # LSTM needs windowing, careful with dimensions
                model = LSTMModel(input_dim)
            
            # Train
            model.train(X_train)
            st.session_state.model = model
            st.session_state.model_name = model_type
            st.session_state.is_trained = True
            
            st.success(f"{model_type} Trained Successfully!")
            st.info(f"Anomaly Threshold: {model.threshold:.4f}")

        # Evaluation (if trained)
        if st.session_state.get('is_trained') and st.session_state.model_name == model_type:
            st.subheader("Static Evaluation")
            # We need test data again if we didn't persist it. 
            # For simplicity, let's just reload small chunk to eval or assume user just trained.
            # In a real app, cache X_test.
            
            # Re-load for eval view (Quick & dirty for single file simplicity)
            X, y = loader.load_raw_data(selected_file, nrows=train_size*2)
            _, X_test, y_test = loader.preprocess_and_split(X, y, semi_supervised=True)
            
            scores, y_pred = st.session_state.model.predict_anomaly_score(X_test)
            
            # Metrics
            cols = st.columns(4)
            cols[0].metric("Accuracy", f"{accuracy_score(y_test, y_pred):.4f}")
            cols[1].metric("Precision", f"{precision_score(y_test, y_pred):.4f}")
            cols[2].metric("Recall", f"{recall_score(y_test, y_pred):.4f}")
            cols[3].metric("F1 Score", f"{f1_score(y_test, y_pred):.4f}")
            
            # Confusion Matrix
            cm = confusion_matrix(y_test, y_pred)
            fig_cm = px.imshow(cm, text_auto=True, labels=dict(x="Predicted", y="Actual"), x=['Benign', 'Attack'], y=['Benign', 'Attack'], title="Confusion Matrix")
            st.plotly_chart(fig_cm, use_container_width=True)

    with tab2:
        st.header("Live Traffic Simulation")
        
        if not st.session_state.get('is_trained'):
            st.warning("Please train a model in the 'Training' tab first.")
        else:
            st.write("This module simulates real-time traffic by streaming rows from the dataset.")
            
            col_start, col_stop = st.columns(2)
            start_btn = col_start.button("▶️ Start Monitoring")
            stop_btn = col_stop.button("⏹️ Stop")
            
            if start_btn:
                # Setup Live Plot
                placeholder = st.empty()
                metrics_ph = st.empty()
                
                # Load "Fresh" data for streaming (skip the training rows)
                # In real life this would be a socket.
                chunk_size = 50
                stream_start_idx = train_size * 2
                
                # Buffer for plotting
                history_scores = []
                history_timestamps = []
                
                # Stream loop
                X_stream_load, y_stream_load = loader.load_raw_data(selected_file, nrows=stream_start_idx + 2000)
                # Slice the "unseen" part
                X_stream = X_stream_load.iloc[stream_start_idx:]
                y_stream = y_stream_load.iloc[stream_start_idx:]
                
                st.session_state.streaming = True
                
                for i in range(0, len(X_stream), chunk_size):
                    if stop_btn: # This check is tricky in Streamlit loops, usually requires rerun. 
                        # relying on UI stop which resets script.
                        break
                        
                    batch_X = X_stream.iloc[i : i+chunk_size]
                    batch_y = y_stream.iloc[i : i+chunk_size]
                    
                    if batch_X.empty:
                        break
                        
                    # Predict
                    scores, preds = st.session_state.model.predict_anomaly_score(batch_X)
                    
                    # Update History
                    history_scores.extend(scores.tolist())
                    history_timestamps.extend(range(len(history_scores) - len(scores), len(history_scores)))
                    
                    # Keep window fixed size
                    window = 200
                    if len(history_scores) > window:
                        plot_scores = history_scores[-window:]
                        plot_idx = history_timestamps[-window:]
                    else:
                        plot_scores = history_scores
                        plot_idx = history_timestamps
                    
                    # Live Plot
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=plot_idx, y=plot_scores, mode='lines', name='Anomaly Score', line=dict(color='#00CC96')))
                    fig.add_trace(go.Scatter(x=plot_idx, y=[st.session_state.model.threshold]*len(plot_scores), mode='lines', name='Threshold', line=dict(color='#EF553B', dash='dash')))
                    
                    fig.update_layout(
                        title="Real-time Anomaly Score Stream",
                        xaxis_title="Packet Index",
                        yaxis_title="Reconstruction Error / Anomaly Score",
                        height=400,
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    
                    with placeholder.container():
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Real-time alerting
                        current_anomalies = np.sum(preds)
                        if current_anomalies > 0:
                            st.error(f"⚠️ DETECTED {current_anomalies} ANOMALIES IN LAST BATCH!")
                        else:
                            st.success("✅ Traffic Normal")

                    # Sleep for effect
                    time.sleep(0.5)

if __name__ == "__main__":
    main()
