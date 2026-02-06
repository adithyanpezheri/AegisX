import pandas as pd
import os

# Path to the file
filepath = r"C:\Users\Adithyan\Downloads\prg\uploads\02-14-2018.csv"

try:
    # Check file size
    file_size = os.path.getsize(filepath)
    print(f"File size: {file_size / (1024**2):.2f} MB")
    
    # Read CSV
    print("Reading CSV...")
    df = pd.read_csv(filepath)
    
    print(f"\nTotal rows: {len(df)}")
    print(f"Total columns: {len(df.columns)}")
    print(f"\nColumn names: {df.columns.tolist()}")
    
    # Check for Label column
    if 'Label' in df.columns:
        label_counts = df['Label'].value_counts()
        print(f"\nLabel distribution:")
        print(label_counts)
        
        total = len(df)
        benign = (df['Label'] == 'Benign').sum()
        anomaly = total - benign
        
        benign_pct = (benign / total) * 100
        anomaly_pct = (anomaly / total) * 100
        
        print(f"\n=== SUMMARY ===")
        print(f"Total samples: {total}")
        print(f"Benign: {benign} ({benign_pct:.2f}%)")
        print(f"Anomalies/Attacks: {anomaly} ({anomaly_pct:.2f}%)")
    else:
        print("\nNo 'Label' column found. Available columns:", df.columns.tolist())
        print("\nFirst few rows:")
        print(df.head())
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
