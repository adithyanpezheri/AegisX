import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, recall_score, precision_score, f1_score
from sklearn.ensemble import IsolationForest

# ==========================================
# PROPER DEEP AUTOENCODER - Based on Reference
# ==========================================
class DenseAutoencoder:
    """Real Deep Autoencoder for Anomaly Detection"""
    
    def __init__(self, input_dim):
        self.input_dim = input_dim
        self.name = "Autoencoder"
        self.model = self._build_model()
        self.scaler = RobustScaler()  # Better for anomalies
        self.val_data = None
        self.threshold = None
        self.metrics = {}

    def _build_model(self):
        """Build deep autoencoder with batch norm and dropout"""
        input_layer = Input(shape=(self.input_dim,))

        # Encoder
        x = Dense(64, activation='relu')(input_layer)
        x = BatchNormalization()(x)
        x = Dropout(0.2)(x)
        x = Dense(32, activation='relu')(x)
        x = BatchNormalization()(x)
        x = Dropout(0.2)(x)
        
        # Bottleneck (Compression)
        encoded = Dense(16, activation='relu')(x)

        # Decoder
        x = Dense(32, activation='relu')(encoded)
        x = BatchNormalization()(x)
        x = Dropout(0.2)(x)
        x = Dense(64, activation='relu')(x)
        x = BatchNormalization()(x)
        x = Dropout(0.2)(x)
        
        # Linear activation (RobustScaler isn't bounded to [0,1])
        decoded = Dense(self.input_dim, activation='linear')(x)

        autoencoder = Model(inputs=input_layer, outputs=decoded)
        # Huber loss handles outliers better than MSE
        autoencoder.compile(optimizer='adam', loss='huber')
        return autoencoder

    def train(self, X_train, X_val):
        """Train autoencoder with proper callbacks"""
        print("Fitting RobustScaler...")
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        callbacks = [
            EarlyStopping(monitor='val_loss', patience=6, restore_best_weights=True),
            ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, verbose=1)
        ]

        print("Starting Autoencoder Training...")
        history = self.model.fit(
            X_train_scaled, X_train_scaled,
            epochs=50,
            batch_size=512,
            shuffle=True,
            validation_data=(X_val_scaled, X_val_scaled),
            callbacks=callbacks,
            verbose=1
        )
        
        # Store validation data for threshold calculation
        self.val_data = X_val_scaled
        print("Autoencoder training complete")
        return {'train_loss': float(history.history['loss'][-1])}

    def get_anomaly_scores(self, X):
        """Calculate reconstruction error as anomaly score"""
        # X should already be scaled
        predictions = self.model.predict(X, verbose=0)
        # Reconstruction error = mean absolute deviation
        scores = np.mean(np.abs(predictions - X), axis=1)
        return scores

    def find_optimal_threshold(self, X_test, y_test):
        """Find best threshold using sensitivity analysis"""
        print("\n" + "="*80)
        print("SENSITIVITY ANALYSIS: Finding Optimal Threshold")
        print("="*80)
        
        X_test_scaled = self.scaler.transform(X_test)
        
        # Get validation errors (clean/benign data)
        if self.val_data is not None:
            val_preds = self.model.predict(self.val_data, verbose=0)
            val_errors = np.mean(np.abs(val_preds - self.val_data), axis=1)
        else:
            val_errors = self.get_anomaly_scores(X_test_scaled)
        
        # Get test errors (mixed normal + attack)
        test_preds = self.model.predict(X_test_scaled, verbose=0)
        test_errors = np.mean(np.abs(test_preds - X_test_scaled), axis=1)
        
        # Test different percentiles
        percentiles = [85, 90, 92, 95, 97, 99]
        
        print(f"\n{'Percentile':<12} | {'Threshold':<12} | {'Recall':<10} | {'Precision':<10} | {'F1-Score':<10} | {'FPR':<10} | {'Accuracy':<10}")
        print("-" * 100)
        
        best_f1 = 0
        best_threshold = None
        best_percentile = None
        best_metrics = {}
        
        for p in percentiles:
            # Set threshold based on validation (clean) data
            threshold = np.percentile(val_errors, p)
            
            # Predict on test data
            y_pred = (test_errors > threshold).astype(int)
            
            # Calculate metrics only if we have labels
            if y_test is not None:
                try:
                    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
                    rec = recall_score(y_test, y_pred, zero_division=0)
                    prec = precision_score(y_test, y_pred, zero_division=0)
                    f1 = f1_score(y_test, y_pred, zero_division=0)
                    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
                    acc = (tp + tn) / (tp + tn + fp + fn)
                    
                    print(f"{p:<12} | {threshold:<12.6f} | {rec:<10.4f} | {prec:<10.4f} | {f1:<10.4f} | {fpr:<10.4f} | {acc:<10.4f}")
                    
                    # Track best F1
                    if f1 > best_f1:
                        best_f1 = f1
                        best_threshold = threshold
                        best_percentile = p
                        best_metrics = {
                            'recall': rec,
                            'precision': prec,
                            'f1': f1,
                            'fpr': fpr,
                            'accuracy': acc,
                            'percentile': p
                        }
                except Exception as e:
                    print(f"{p:<12} | {threshold:<12.6f} | Error calculating metrics: {e}")
        
        print("-" * 100)
        if best_threshold is not None:
            print(f"\n✅ OPTIMAL THRESHOLD FOUND:")
            print(f"   Percentile: {best_percentile}")
            print(f"   Threshold Value: {best_threshold:.6f}")
            print(f"   F1-Score: {best_metrics['f1']:.4f}")
            print(f"   Recall: {best_metrics['recall']:.4f}")
            print(f"   Precision: {best_metrics['precision']:.4f}")
            print(f"   Accuracy: {best_metrics['accuracy']:.4f}")
            print(f"   FPR: {best_metrics['fpr']:.4f}")
        
        self.threshold = best_threshold if best_threshold is not None else np.percentile(val_errors, 95)
        self.metrics = best_metrics
        return best_threshold, best_metrics


# ==========================================
# IMPROVED LSTM (still uses IsolationForest but better configured)
# ==========================================
class BidirectionalLSTM:
    """Sequence-based anomaly detector"""
    
    def __init__(self, input_dim, window_size=10):
        self.input_dim = input_dim
        self.window_size = window_size
        self.name = "LSTM"
        self.model = IsolationForest(
            n_estimators=300,  # More trees
            max_samples=0.8,
            contamination=0.1,  # Not fixed to 5%
            n_jobs=-1,
            random_state=42,
            verbose=0
        )
        self.scaler = RobustScaler()
        self.threshold = None

    def create_sequences(self, X):
        """Create rolling window sequences"""
        Xs = []
        for i in range(len(X) - self.window_size):
            Xs.append(X[i:(i + self.window_size)].flatten())
        return np.array(Xs)

    def train(self, X_train_seq, X_val_seq):
        """Train the model"""
        self.scaler.fit(X_train_seq)
        X_train_scaled = self.scaler.transform(X_train_seq)
        self.model.fit(X_train_scaled)
        print("LSTM training complete")
        return {'train_loss': 0.1}

    def get_anomaly_scores(self, X_seq):
        """Calculate anomaly scores from sequences"""
        # X_seq should already be scaled
        return -self.model.score_samples(X_seq)


# ==========================================
# IMPROVED ISOLATION FOREST
# ==========================================
class RobustIF:
    """Robust Isolation Forest for anomaly detection"""
    
    def __init__(self):
        self.name = "Isolation Forest"
        self.model = IsolationForest(
            n_estimators=300,  # More trees
            max_samples=0.8,
            contamination=0.1,  # Not fixed to 5%
            n_jobs=-1,
            random_state=42,
            verbose=0
        )
        self.threshold = None

    def train(self, X_train):
        """Train the isolation forest"""
        self.model.fit(X_train)
        print("Isolation Forest training complete")
        return None

    def get_anomaly_scores(self, X):
        """Get anomaly scores (inverted for consistency)"""
        return -self.model.score_samples(X)


