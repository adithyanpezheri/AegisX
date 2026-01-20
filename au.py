import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

class AutoTunedAutoencoder:
    def __init__(self, input_dim):
        self.input_dim = input_dim
        self.model = self._build_model()
        # RobustScaler is better for anomaly separation than MinMax
        self.scaler = RobustScaler()

    def _build_model(self):
        input_layer = Input(shape=(self.input_dim,))

        # Encoder
        x = Dense(64, activation='relu')(input_layer)
        x = BatchNormalization()(x)
        x = Dropout(0.2)(x)
        x = Dense(32, activation='relu')(x)
        x = BatchNormalization()(x)
        
        # Bottleneck (Compression)
        encoded = Dense(16, activation='relu')(x)

        # Decoder
        x = Dense(32, activation='relu')(encoded)
        x = BatchNormalization()(x)
        x = Dense(64, activation='relu')(x)
        x = BatchNormalization()(x)
        
        # Linear activation because RobustScaler output isn't bounded to [0,1]
        decoded = Dense(self.input_dim, activation='linear')(x)

        autoencoder = Model(inputs=input_layer, outputs=decoded)
        # Huber loss handles remaining outliers gracefully
        autoencoder.compile(optimizer='adam', loss='huber') 
        return autoencoder

    def preprocess_and_split(self, filepath):
        print(f"Loading {filepath}...")
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        
        # Drop metadata
        drop_cols = ['Label', 'Timestamp', 'Dst IP', 'Src IP', 'Flow ID'] 
        cols_to_drop = [c for c in drop_cols if c in df.columns]
        X = df.drop(columns=cols_to_drop)
        y = df['Label']

        # Cleaning
        X = X.apply(pd.to_numeric, errors='coerce')
        X.replace([np.inf, -np.inf], np.nan, inplace=True)
        X.fillna(0, inplace=True)
        X[X < 0] = 0 # Clip negatives

        # Log Transform
        print("Applying Log-Transform...")
        X = np.log1p(X)

        # Labels
        y_binary = y.apply(lambda x: 0 if x == 'Benign' else 1)

        # Split
        benign_indices = y_binary[y_binary == 0].index
        attack_indices = y_binary[y_binary == 1].index

        train_idx, test_benign_idx = train_test_split(benign_indices, test_size=0.2, random_state=42)
        
        X_train = X.loc[train_idx]
        test_idx = np.concatenate([test_benign_idx, attack_indices])
        X_test = X.loc[test_idx]
        y_test = y_binary.loc[test_idx]

        return X_train, X_test, y_test

    def train(self, X_train):
        print("Fitting RobustScaler...")
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        X_t, X_v = train_test_split(X_train_scaled, test_size=0.1, random_state=42)

        callbacks = [
            EarlyStopping(monitor='val_loss', patience=6, restore_best_weights=True),
            ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3)
        ]

        print("Starting Training...")
        self.model.fit(
            X_t, X_t,
            epochs=40,
            batch_size=1024,
            shuffle=True,
            validation_data=(X_v, X_v),
            callbacks=callbacks,
            verbose=1
        )
        
        # Store validation data for threshold calculation
        self.val_data = X_v

    def evaluate_sensitivity(self, X_test, y_test):
        print("\n--- SENSITIVITY ANALYSIS ---")
        X_test_scaled = self.scaler.transform(X_test)
        
        # 1. Get Reconstruction Errors
        # Validation Errors (Clean)
        val_preds = self.model.predict(self.val_data, verbose=0)
        val_errors = np.mean(np.abs(val_preds - self.val_data), axis=1)
        
        # Test Errors (Mixed)
        test_preds = self.model.predict(X_test_scaled, verbose=0)
        test_errors = np.mean(np.abs(test_preds - X_test_scaled), axis=1)

        # 2. Test different Percentiles
        percentiles = [90, 92, 95, 98, 99]
        
        print(f"{'Percentile':<12} | {'Threshold':<10} | {'Recall':<10} | {'Precision':<10} | {'F1-Score':<10} | {'FPR':<10}")
        print("-" * 80)

        for p in percentiles:
            # Set threshold based on NORMAL traffic
            threshold = np.percentile(val_errors, p)
            
            # Predict
            y_pred = (test_errors > threshold).astype(int)
            
            # Metrics
            rec = recall_score(y_test, y_pred)
            prec = precision_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred)
            
            tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
            fpr = fp / (fp + tn)
            
            print(f"{p:<12} | {threshold:.6f}   | {rec:.4f}     | {prec:.4f}     | {f1:.4f}     | {fpr:.4f}")

if __name__ == "__main__":
    FILENAME = "02-14-2018.csv"
    import os
    if os.path.exists(FILENAME):
        # Initial read
        temp_df = pd.read_csv(FILENAME, nrows=1)
        
        # Instantiate
        ae = AutoTunedAutoencoder(input_dim=1)
        X_train, X_test, y_test = ae.preprocess_and_split(FILENAME)
        
        # Re-init and Train
        ae = AutoTunedAutoencoder(input_dim=X_train.shape[1])
        ae.train(X_train)
        
        # Run the Sensitivity Table
        ae.evaluate_sensitivity(X_test, y_test)
    else:
        print(f"File {FILENAME} not found.")