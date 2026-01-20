import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.svm import LinearSVC
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score

class BenchmarkLoader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.scaler = RobustScaler()

    def load_and_process(self):
        print(f"Loading {self.filepath}...")
        df = pd.read_csv(self.filepath)
        df.columns = df.columns.str.strip()
        
        # Drop Metadata
        drop_cols = ['Label', 'Timestamp', 'Dst IP', 'Src IP', 'Flow ID'] 
        cols_to_drop = [c for c in drop_cols if c in df.columns]
        X = df.drop(columns=cols_to_drop)
        y = df['Label']

        # --- FIX STARTS HERE ---
        # 1. Force to numeric
        X = X.apply(pd.to_numeric, errors='coerce')
        
        # 2. Explicitly replace Infinity with NaN
        X = X.replace([np.inf, -np.inf], np.nan)
        
        # 3. Fill NaN with 0
        X = X.fillna(0)
        
        # 4. Clip Negatives
        X[X < 0] = 0
        # --- FIX ENDS HERE ---

        # Log Transform
        print("Applying Log-Transform (Consistency Check)...")
        X = np.log1p(X)

        y_binary = y.apply(lambda x: 0 if x == 'Benign' else 1)

        # Split for Supervised (RF/SVM)
        X_train, X_test, y_train, y_test = train_test_split(X, y_binary, test_size=0.3, random_state=42)
        
        # For Isolation Forest (Unsupervised)
        benign_mask = (y_train == 0)
        X_train_benign = X_train[benign_mask]
        
        # Validation Set for thresholding
        X_if_train, X_if_val = train_test_split(X_train_benign, test_size=0.1, random_state=42)
        
        return X_train, X_test, y_train, y_test, X_if_train, X_if_val

def evaluate_model(name, y_true, y_pred, time_taken):
    print(f"\n--- {name} Results ---")
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred)
    rec = recall_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred)
    
    print(f"Inference Time: {time_taken:.4f}s")
    print(f"Accuracy:       {acc:.4f}")
    print(f"Precision:      {prec:.4f}")
    print(f"Recall:         {rec:.4f}")
    print(f"F1-Score:       {f1:.4f}")
    
    return [acc, prec, rec, f1, time_taken]

if __name__ == "__main__":
    import time
    # Update this to your filename
    FILENAME = "03-02-2018.csv" 
    
    import os
    if os.path.exists(FILENAME):
        loader = BenchmarkLoader(FILENAME)
        X_train, X_test, y_train, y_test, X_if_train, X_if_val = loader.load_and_process()
        
        # Scale Data
        print("Fitting Scaler...")
        X_train_scaled = loader.scaler.fit_transform(X_train)
        X_test_scaled = loader.scaler.transform(X_test)
        X_if_train_scaled = loader.scaler.transform(X_if_train)
        X_if_val_scaled = loader.scaler.transform(X_if_val)

        results = {}

        # 1. RANDOM FOREST
        print("\nTraining Random Forest...")
        rf = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=42)
        rf.fit(X_train_scaled, y_train)
        
        start = time.time()
        y_pred_rf = rf.predict(X_test_scaled)
        end = time.time()
        results['Random Forest'] = evaluate_model("Random Forest", y_test, y_pred_rf, end-start)

        # 2. SVM
        print("\nTraining SVM (LinearSVC)...")
        svm = LinearSVC(dual=False, random_state=42) 
        svm.fit(X_train_scaled, y_train)
        
        start = time.time()
        y_pred_svm = svm.predict(X_test_scaled)
        end = time.time()
        results['SVM'] = evaluate_model("SVM", y_test, y_pred_svm, end-start)

        # 3. ISOLATION FOREST
        print("\nTraining Isolation Forest...")
        iso = IsolationForest(n_estimators=100, max_samples=0.8, n_jobs=-1, random_state=42)
        iso.fit(X_if_train_scaled)
        
        print("Calculating Dynamic Threshold for IForest...")
        val_scores = -iso.score_samples(X_if_val_scaled)
        threshold = np.percentile(val_scores, 95)
        
        start = time.time()
        test_scores = -iso.score_samples(X_test_scaled)
        y_pred_iso = (test_scores > threshold).astype(int)
        end = time.time()
        
        results['Isolation Forest'] = evaluate_model("Isolation Forest", y_test, y_pred_iso, end-start)

    else:
        print("File not found.")