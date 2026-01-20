import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Input, LSTM, Dense, Dropout, RepeatVector, TimeDistributed, BatchNormalization, Bidirectional, GaussianNoise
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.regularizers import l2
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

class HighPerformanceLSTM:
    def __init__(self, input_dim, window_size=10):
        self.input_dim = input_dim
        self.window_size = window_size
        self.model = self._build_model()
        self.scaler = RobustScaler()
        self.val_seqs = None

    def _build_model(self):
        model = Sequential()
        
        # FIX 1: Explicit Input Layer to silence the UserWarning
        model.add(Input(shape=(self.window_size, self.input_dim)))
        
        # 1. HEAVY DENOISING: Corrupt input so model can't just "copy"
        # Increase noise to 0.2 to break the "Identity Trap"
        model.add(GaussianNoise(0.2))
        
        # 2. ENCODER
        # L2 Regularization prevents overfitting to the "easy" repetitive patterns
        model.add(Bidirectional(LSTM(64, activation='tanh', return_sequences=True, kernel_regularizer=l2(0.001))))
        model.add(BatchNormalization())
        model.add(Dropout(0.3))
        
        model.add(Bidirectional(LSTM(16, activation='tanh', return_sequences=False))) # Compress to 16
        model.add(BatchNormalization())
        
        # 3. TIGHT BOTTLENECK
        # Force extreme compression. Model MUST learn "Normal" rules, cannot memorize data.
        model.add(RepeatVector(self.window_size))
        
        # 4. DECODER
        model.add(Bidirectional(LSTM(16, activation='tanh', return_sequences=True)))
        model.add(BatchNormalization())
        
        model.add(Bidirectional(LSTM(64, activation='tanh', return_sequences=True)))
        model.add(BatchNormalization())
        model.add(Dropout(0.3))
        
        # Output
        model.add(TimeDistributed(Dense(self.input_dim, activation='linear')))
        
        model.compile(optimizer='adam', loss='huber') # Huber handles outliers better than MSE
        return model

    def create_sequences(self, X):
        # Rolling window
        Xs = []
        for i in range(len(X) - self.window_size):
            Xs.append(X[i:(i + self.window_size)])
        return np.array(Xs)

    def preprocess_and_split(self, filepath):
        print(f"Loading {filepath}...")
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        
        drop_cols = ['Label', 'Timestamp', 'Dst IP', 'Src IP', 'Flow ID'] 
        cols_to_drop = [c for c in drop_cols if c in df.columns]
        X = df.drop(columns=cols_to_drop)
        y = df['Label']

        # FIX 2: ROBUST CLEANING
        # 1. Force everything to numeric (errors become NaN)
        X = X.apply(pd.to_numeric, errors='coerce')
        
        # 2. Replace Infinity with NaN (Crucial Step!)
        X = X.replace([np.inf, -np.inf], np.nan)
        
        # 3. Fill all NaNs with 0
        X = X.fillna(0)
        
        # 4. Clip Negatives
        X[X < 0] = 0
        
        # 5. Log Transform
        X = np.log1p(X) 

        y_binary = y.apply(lambda x: 0 if x == 'Benign' else 1)

        # Split
        benign_mask = (y_binary == 0)
        X_benign = X[benign_mask]
        
        X_train_raw, X_test_benign_raw = train_test_split(X_benign, test_size=0.2, random_state=42)
        
        X_attack = X[~benign_mask]
        X_test_raw = pd.concat([X_test_benign_raw, X_attack])
        y_test_raw = pd.concat([y_binary[X_test_benign_raw.index], y_binary[X_attack.index]])
        
        return X_train_raw, X_test_raw, y_test_raw

    def train(self, X_train_raw):
        print("Fitting Scaler...")
        X_train_scaled = self.scaler.fit_transform(X_train_raw)
        
        print("Creating Sequences (This takes RAM)...")
        X_train_seq = self.create_sequences(X_train_scaled)
        
        X_t, X_v = train_test_split(X_train_seq, test_size=0.1, random_state=42)

        callbacks = [
            EarlyStopping(monitor='val_loss', patience=4, restore_best_weights=True),
            ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=2)
        ]

        print("Starting Training...")
        self.model.fit(
            X_t, X_t,
            epochs=20, 
            batch_size=512,
            validation_data=(X_v, X_v),
            callbacks=callbacks,
            verbose=1
        )
        self.val_seqs = X_v

    def evaluate(self, X_test_raw, y_test_raw):
        print("\nEvaluating...")
        X_test_scaled = self.scaler.transform(X_test_raw)
        X_test_seq = self.create_sequences(X_test_scaled)
        # Align labels (drop first N rows because sequences consume them)
        y_test_seq = y_test_raw.iloc[self.window_size:].values
        
        # 1. Get Reconstruction Errors
        val_preds = self.model.predict(self.val_seqs, verbose=0, batch_size=512)
        val_errors = np.mean(np.abs(val_preds - self.val_seqs), axis=(1, 2))
        
        test_preds = self.model.predict(X_test_seq, verbose=0, batch_size=512)
        test_errors = np.mean(np.abs(test_preds - X_test_seq), axis=(1, 2))

        # 2. Thresholding: 90th percentile
        threshold = np.percentile(val_errors, 90)
        
        y_pred = (test_errors > threshold).astype(int)
        
        # Metrics
        rec = recall_score(y_test_seq, y_pred)
        prec = precision_score(y_test_seq, y_pred)
        f1 = f1_score(y_test_seq, y_pred)
        tn, fp, fn, tp = confusion_matrix(y_test_seq, y_pred).ravel()
        
        print("\n--- NEW LSTM METRICS ---")
        print(f"Threshold (90th %ile): {threshold:.4f}")
        print(f"Recall (Attacks Detected): {rec:.4f}")
        print(f"Precision:                 {prec:.4f}")
        print(f"F1-Score:                  {f1:.4f}")
        print(f"Confusion Matrix: TP={tp}, FN={fn}, FP={fp}, TN={tn}")

if __name__ == "__main__":
    FILENAME = "03-02-2018.csv"
    import os
    if os.path.exists(FILENAME):
        # Initialize
        temp = pd.read_csv(FILENAME, nrows=1)
        dim = temp.shape[1] - 5 
        lstm = HighPerformanceLSTM(input_dim=dim, window_size=10)
        
        # Run Pipeline
        X_train, X_test, y_test = lstm.preprocess_and_split(FILENAME)
        
        # Re-init with correct dimension just in case
        lstm = HighPerformanceLSTM(input_dim=X_train.shape[1], window_size=10)
        
        lstm.train(X_train)
        lstm.evaluate(X_test, y_test)
    else:
        print("File not found.")