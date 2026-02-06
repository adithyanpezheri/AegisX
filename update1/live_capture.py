import time
import numpy as np
import pandas as pd
from datetime import datetime
from collections import defaultdict
import threading

try:
    from scapy.all import sniff, IP, TCP, UDP, ICMP
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    print("Warning: Scapy not available. Install with: pip install scapy")

class NetworkCapture:
    """Live network traffic capture and analysis with real-time callbacks"""
    
    def __init__(self, interface='eth0', model=None, scaler=None, on_alert=None):
        if not SCAPY_AVAILABLE:
            raise ImportError("Scapy is required for live capture")
        
        self.interface = interface
        self.model = model
        self.scaler = scaler
        self.on_alert = on_alert  # Callback for anomalies
        self.packet_buffer = []
        self.flow_stats = defaultdict(lambda: {
            'packet_count': 0,
            'total_bytes': 0,
            'start_time': None,
            'last_time': None,
            'flags': [],
            'protocols': []
        })
        self.running = False
        self.anomaly_threshold = 0.5
        
    def extract_features(self, packet):
        """Extract features from a packet"""
        features = {}
        
        try:
            if IP in packet:
                features['Src IP'] = packet[IP].src
                features['Dst IP'] = packet[IP].dst
                features['Protocol'] = packet[IP].proto
                features['Total Length'] = packet[IP].len
                features['TTL'] = packet[IP].ttl
                
                # Protocol name
                protocol_map = {6: 'TCP', 17: 'UDP', 1: 'ICMP'}
                features['Protocol Name'] = protocol_map.get(packet[IP].proto, 'Other')
                
                # Flow ID
                flow_id = f"{packet[IP].src}->{packet[IP].dst}"
                
                if TCP in packet:
                    features['Src Port'] = packet[TCP].sport
                    features['Dst Port'] = packet[TCP].dport
                    features['Flags'] = packet[TCP].flags
                    flow_id += f":{packet[TCP].sport}->{packet[TCP].dport}:TCP"
                    
                elif UDP in packet:
                    features['Src Port'] = packet[UDP].sport
                    features['Dst Port'] = packet[UDP].dport
                    flow_id += f":{packet[UDP].sport}->{packet[UDP].dport}:UDP"
                
                elif ICMP in packet:
                    flow_id += ":ICMP"
                
                features['Flow ID'] = flow_id
                features['Timestamp'] = datetime.now().isoformat()
                
                # Update flow statistics
                flow = self.flow_stats[flow_id]
                flow['packet_count'] += 1
                flow['total_bytes'] += features['Total Length']
                
                if flow['start_time'] is None:
                    flow['start_time'] = time.time()
                flow['last_time'] = time.time()
                
                # Calculate flow-based features
                duration = flow['last_time'] - flow['start_time']
                if duration > 0:
                    features['Flow Duration'] = duration
                    features['Flow Packets/s'] = flow['packet_count'] / duration
                    features['Flow Bytes/s'] = flow['total_bytes'] / duration
                else:
                    features['Flow Duration'] = 0
                    features['Flow Packets/s'] = 0
                    features['Flow Bytes/s'] = 0
                
                features['Flow Packet Count'] = flow['packet_count']
                features['Flow Total Bytes'] = flow['total_bytes']
                
                return features
                
        except Exception as e:
            print(f"Error extracting features: {e}")
            return None
        
        return None
    
    def packet_callback(self, packet):
        """Callback for each captured packet"""
        if not self.running:
            return
            
        features = self.extract_features(packet)
        
        if features:
            self.packet_buffer.append(features)
            
            # Process when buffer reaches size (every 5 packets for real-time feedback)
            if len(self.packet_buffer) >= 5:
                self.process_buffer()
    
    def process_buffer(self):
        """Process buffered packets and detect anomalies"""
        if not self.packet_buffer:
            return
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame(self.packet_buffer)
            
            # Keep metadata for reporting
            metadata = df[['Src IP', 'Dst IP', 'Flow ID', 'Timestamp', 'Protocol Name']].copy()
            
            # Drop metadata columns for feature engineering
            drop_cols = ['Src IP', 'Dst IP', 'Flow ID', 'Timestamp', 'Protocol Name']
            X = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')
            
            # Fill missing values
            X = X.fillna(0)
            
            # Ensure numeric
            X = X.apply(pd.to_numeric, errors='coerce')
            X = X.fillna(0)
            
            # Clip negatives
            X[X < 0] = 0
            
            # Log transform
            X = np.log1p(X)
            
            # Scale if scaler available
            if self.scaler:
                try:
                    X_scaled = self.scaler.transform(X)
                except:
                    X_scaled = X.values
            else:
                X_scaled = X.values
            
            # Get anomaly scores
            if self.model:
                try:
                    scores = self.model.get_anomaly_scores(X_scaled)
                    
                    # Detect anomalies
                    anomalies = scores > self.anomaly_threshold
                    
                    # Report anomalies in real-time
                    for i, is_anomaly in enumerate(anomalies):
                        if is_anomaly:
                            packet_info = self.packet_buffer[i]
                            alert_data = {
                                'is_anomaly': True,
                                'anomaly_score': float(scores[i]),
                                'src_ip': packet_info.get('Src IP', 'Unknown'),
                                'dst_ip': packet_info.get('Dst IP', 'Unknown'),
                                'src_port': packet_info.get('Src Port', 'N/A'),
                                'dst_port': packet_info.get('Dst Port', 'N/A'),
                                'protocol': packet_info.get('Protocol Name', 'Unknown'),
                                'flow_id': packet_info.get('Flow ID', 'Unknown'),
                                'timestamp': packet_info.get('Timestamp', datetime.now().isoformat()),
                                'packet_size': packet_info.get('Total Length', 0),
                                'flow_packets': packet_info.get('Flow Packet Count', 0)
                            }
                            
                            # Call callback if provided
                            if self.on_alert:
                                self.on_alert(alert_data)
                except Exception as e:
                    print(f"Error during anomaly detection: {e}")
            
            # Clear buffer
            self.packet_buffer.clear()
            
        except Exception as e:
            print(f"Error processing buffer: {e}")
            self.packet_buffer.clear()
    
    def start_capture(self, count=0):
        """Start capturing packets"""
        print(f"Starting capture on interface {self.interface}...")
        self.running = True
        
        try:
            sniff(iface=self.interface, prn=self.packet_callback, count=count, store=False)
        except KeyboardInterrupt:
            print("\nCapture stopped by user")
            self.running = False
        except Exception as e:
            print(f"Capture error: {e}")
            self.running = False
        finally:
            # Process remaining buffer
            if self.packet_buffer:
                self.process_buffer()
    
    def stop_capture(self):
        """Stop capturing packets"""
        self.running = False


# Simulated network capture for testing
class SimulatedNetworkCapture:
    """Simulated network traffic for testing without scapy"""
    
    def __init__(self, model=None, scaler=None, on_alert=None):
        self.model = model
        self.scaler = scaler
        self.on_alert = on_alert
        self.running = False
        self.anomaly_threshold = 0.5
        self.packet_counter = 0
    
    def generate_packet(self, anomaly=False):
        """Generate a simulated network packet"""
        base_values = {
            'Protocol': np.random.choice([6, 17]),  # TCP or UDP
            'Total Length': np.random.randint(40, 1500),
            'TTL': np.random.randint(32, 128),
            'Src Port': np.random.randint(1024, 65535),
            'Dst Port': np.random.choice([80, 443, 22, 3389, 8080, 25, 53]),
            'Flow Duration': np.random.uniform(0, 10),
            'Flow Packets/s': np.random.uniform(1, 100),
            'Flow Bytes/s': np.random.uniform(100, 100000),
            'Flow Packet Count': np.random.randint(1, 100),
            'Flow Total Bytes': np.random.randint(100, 100000)
        }
        
        # Make anomalous packets stand out
        if anomaly:
            base_values['Flow Packets/s'] = np.random.uniform(500, 2000)  # Suspicious rate
            base_values['Src Port'] = np.random.choice([22, 23, 3389, 445])  # Suspicious ports
        
        return base_values
    
    def start_capture(self):
        """Start simulated capture"""
        self.running = True
        self.packet_counter = 0
        print("Starting simulated network capture...")
        
        src_ips = ['192.168.1.100', '192.168.1.101', '10.0.0.50', '172.16.0.10']
        dst_ips = ['8.8.8.8', '1.1.1.1', '208.67.222.222', '1.0.0.1']
        
        while self.running:
            # Generate batch of packets
            packets = []
            for j in range(10):
                # 5% chance of anomaly
                is_anomaly = np.random.random() < 0.05
                packet = self.generate_packet(anomaly=is_anomaly)
                packet['Src IP'] = np.random.choice(src_ips)
                packet['Dst IP'] = np.random.choice(dst_ips)
                packet['Flow ID'] = f"{packet['Src IP']}->{packet['Dst IP']}:{packet['Src Port']}"
                packet['Timestamp'] = datetime.now().isoformat()
                packet['Protocol Name'] = 'TCP' if packet['Protocol'] == 6 else 'UDP'
                packets.append(packet)
            
            df = pd.DataFrame(packets)
            metadata = df[['Src IP', 'Dst IP', 'Flow ID', 'Timestamp', 'Protocol Name']].copy()
            
            # Preprocess
            drop_cols = ['Src IP', 'Dst IP', 'Flow ID', 'Timestamp', 'Protocol Name']
            X = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')
            X = X.apply(pd.to_numeric, errors='coerce').fillna(0)
            X[X < 0] = 0
            X = np.log1p(X)
            
            if self.scaler:
                try:
                    X_scaled = self.scaler.transform(X)
                except:
                    X_scaled = X.values
            else:
                X_scaled = X.values
            
            # Analyze
            if self.model:
                try:
                    scores = self.model.get_anomaly_scores(X_scaled)
                    anomalies = scores > self.anomaly_threshold
                    
                    for i, is_anomaly in enumerate(anomalies):
                        if is_anomaly:
                            packet_info = packets[i]
                            alert_data = {
                                'is_anomaly': True,
                                'anomaly_score': float(scores[i]),
                                'src_ip': packet_info.get('Src IP', 'Unknown'),
                                'dst_ip': packet_info.get('Dst IP', 'Unknown'),
                                'src_port': packet_info.get('Src Port', 'N/A'),
                                'dst_port': packet_info.get('Dst Port', 'N/A'),
                                'protocol': packet_info.get('Protocol Name', 'Unknown'),
                                'flow_id': packet_info.get('Flow ID', 'Unknown'),
                                'timestamp': packet_info.get('Timestamp', datetime.now().isoformat()),
                                'packet_size': packet_info.get('Total Length', 0),
                                'flow_packets': packet_info.get('Flow Packet Count', 0)
                            }
                            
                            if self.on_alert:
                                self.on_alert(alert_data)
                except Exception as e:
                    print(f"Error during anomaly detection: {e}")
            
            self.packet_counter += 10
            time.sleep(2)  # Wait 2 seconds between batches
