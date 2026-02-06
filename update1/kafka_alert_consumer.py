#!/usr/bin/env python3
"""
NetSurf Kafka Alert Consumer
Monitors the security_alerts topic and displays/logs alerts
"""

import json
import sys
from datetime import datetime

try:
    from kafka import KafkaConsumer
except ImportError:
    print("Error: kafka-python not installed")
    print("Install with: pip install kafka-python")
    sys.exit(1)

class AlertConsumer:
    def __init__(self, bootstrap_servers='localhost:9092', topic='security_alerts'):
        self.topic = topic
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='netsurf-alert-monitor'
        )
        
    def start_monitoring(self):
        """Start consuming and displaying alerts"""
        print("=" * 60)
        print("NetSurf Alert Monitor - Listening for Security Alerts")
        print("=" * 60)
        print(f"Topic: {self.topic}")
        print("Press Ctrl+C to stop\n")
        
        alert_count = 0
        
        try:
            for message in self.consumer:
                alert = message.value
                alert_count += 1
                
                self.display_alert(alert, alert_count)
                self.log_alert(alert)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
            print(f"Total alerts received: {alert_count}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.consumer.close()
    
    def display_alert(self, alert, count):
        """Display alert in terminal"""
        print(f"\n{'=' * 60}")
        print(f"🚨 ALERT #{count}")
        print(f"{'=' * 60}")
        print(f"Timestamp:    {alert.get('timestamp', 'Unknown')}")
        print(f"Alert Type:   {alert.get('alert_type', 'Unknown')}")
        print(f"Confidence:   {alert.get('confidence', 0):.4f}")
        
        details = alert.get('details', {})
        if details:
            print(f"\nDetails:")
            for key, value in details.items():
                print(f"  {key}: {value}")
        
        print(f"{'=' * 60}")
    
    def log_alert(self, alert):
        """Log alert to file"""
        with open('alerts.log', 'a') as f:
            f.write(json.dumps(alert) + '\n')

def main():
    # Configuration
    KAFKA_SERVERS = 'localhost:9092'
    ALERT_TOPIC = 'security_alerts'
    
    # Start consumer
    consumer = AlertConsumer(
        bootstrap_servers=KAFKA_SERVERS,
        topic=ALERT_TOPIC
    )
    
    consumer.start_monitoring()

if __name__ == '__main__':
    main()
