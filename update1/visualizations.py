"""
NetSurf Visualization Module
Generate charts and reports for model performance
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime
import os

# Set style
sns.set_style("darkgrid")
plt.rcParams['figure.facecolor'] = '#0a0e17'
plt.rcParams['axes.facecolor'] = '#151b2b'
plt.rcParams['text.color'] = '#e0e6f0'
plt.rcParams['axes.labelcolor'] = '#e0e6f0'
plt.rcParams['xtick.color'] = '#8891a8'
plt.rcParams['ytick.color'] = '#8891a8'
plt.rcParams['grid.color'] = '#2a3548'

class Visualizer:
    """Generate visualizations for IDS results"""
    
    def __init__(self, output_dir='static/reports'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def plot_training_history(self, history, model_name):
        """Plot training and validation loss"""
        if history is None:
            return None
        
        plt.figure(figsize=(10, 6))
        
        plt.plot(history.history['loss'], label='Training Loss', 
                color='#00ff9d', linewidth=2)
        plt.plot(history.history['val_loss'], label='Validation Loss', 
                color='#0099ff', linewidth=2)
        
        plt.title(f'{model_name} Training History', 
                 fontsize=16, color='#00ff9d', fontweight='bold')
        plt.xlabel('Epoch', fontsize=12)
        plt.ylabel('Loss', fontsize=12)
        plt.legend(loc='upper right')
        plt.grid(alpha=0.3)
        
        filename = f'{model_name}_training_history_{int(datetime.now().timestamp())}.png'
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='#0a0e17')
        plt.close()
        
        return filepath
    
    def plot_confusion_matrix(self, cm, model_name):
        """Plot confusion matrix"""
        plt.figure(figsize=(8, 6))
        
        sns.heatmap(cm, annot=True, fmt='d', cmap='RdYlGn_r',
                   xticklabels=['Normal', 'Attack'],
                   yticklabels=['Normal', 'Attack'],
                   cbar_kws={'label': 'Count'})
        
        plt.title(f'{model_name} Confusion Matrix', 
                 fontsize=16, color='#00ff9d', fontweight='bold')
        plt.ylabel('True Label', fontsize=12)
        plt.xlabel('Predicted Label', fontsize=12)
        
        filename = f'{model_name}_confusion_matrix_{int(datetime.now().timestamp())}.png'
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='#0a0e17')
        plt.close()
        
        return filepath
    
    def plot_roc_curve(self, fpr, tpr, auc_score, model_name):
        """Plot ROC curve"""
        plt.figure(figsize=(8, 6))
        
        plt.plot(fpr, tpr, color='#00ff9d', linewidth=2, 
                label=f'ROC Curve (AUC = {auc_score:.3f})')
        plt.plot([0, 1], [0, 1], color='#ff0055', linestyle='--', linewidth=2)
        
        plt.title(f'{model_name} ROC Curve', 
                 fontsize=16, color='#00ff9d', fontweight='bold')
        plt.xlabel('False Positive Rate', fontsize=12)
        plt.ylabel('True Positive Rate', fontsize=12)
        plt.legend(loc='lower right')
        plt.grid(alpha=0.3)
        
        filename = f'{model_name}_roc_curve_{int(datetime.now().timestamp())}.png'
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='#0a0e17')
        plt.close()
        
        return filepath
    
    def plot_anomaly_scores(self, normal_scores, anomaly_scores, threshold, model_name):
        """Plot distribution of anomaly scores"""
        plt.figure(figsize=(12, 6))
        
        # Histogram
        plt.hist(normal_scores, bins=50, alpha=0.7, label='Normal Traffic', 
                color='#00ff9d', edgecolor='#00ff9d')
        plt.hist(anomaly_scores, bins=50, alpha=0.7, label='Attack Traffic', 
                color='#ff0055', edgecolor='#ff0055')
        
        # Threshold line
        plt.axvline(x=threshold, color='#ffaa00', linestyle='--', 
                   linewidth=2, label=f'Threshold ({threshold:.4f})')
        
        plt.title(f'{model_name} Anomaly Score Distribution', 
                 fontsize=16, color='#00ff9d', fontweight='bold')
        plt.xlabel('Anomaly Score', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)
        plt.legend(loc='upper right')
        plt.grid(alpha=0.3)
        
        filename = f'{model_name}_score_distribution_{int(datetime.now().timestamp())}.png'
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='#0a0e17')
        plt.close()
        
        return filepath
    
    def plot_metrics_comparison(self, metrics_dict):
        """Compare metrics across different models"""
        models = list(metrics_dict.keys())
        metrics = ['accuracy', 'precision', 'recall', 'f1_score']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Model Performance Comparison', 
                    fontsize=18, color='#00ff9d', fontweight='bold')
        
        for idx, metric in enumerate(metrics):
            ax = axes[idx // 2, idx % 2]
            
            values = [metrics_dict[model].get(metric, 0) for model in models]
            colors = ['#00ff9d', '#0099ff', '#ffaa00'][:len(models)]
            
            bars = ax.bar(models, values, color=colors, edgecolor='white', linewidth=1.5)
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.3f}',
                       ha='center', va='bottom', fontsize=10, color='#e0e6f0')
            
            ax.set_title(metric.replace('_', ' ').title(), 
                        fontsize=14, color='#00ff9d', fontweight='bold')
            ax.set_ylabel('Score', fontsize=11)
            ax.set_ylim(0, 1.1)
            ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        filename = f'model_comparison_{int(datetime.now().timestamp())}.png'
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='#0a0e17')
        plt.close()
        
        return filepath
    
    def plot_prediction_distribution(self, predictions, labels=None):
        """Plot prediction distribution (pie chart)"""
        fig, ax = plt.subplots(figsize=(8, 8))
        
        normal_count = np.sum(predictions == 0)
        anomaly_count = np.sum(predictions == 1)
        
        sizes = [normal_count, anomaly_count]
        labels_pie = ['Normal Traffic', 'Anomalies Detected']
        colors = ['#00ff9d', '#ff0055']
        explode = (0, 0.1)
        
        wedges, texts, autotexts = ax.pie(sizes, explode=explode, labels=labels_pie,
                                          colors=colors, autopct='%1.1f%%',
                                          shadow=True, startangle=90,
                                          textprops={'fontsize': 12, 'color': '#e0e6f0'})
        
        for autotext in autotexts:
            autotext.set_color('#0a0e17')
            autotext.set_fontweight('bold')
        
        ax.set_title('Prediction Distribution', 
                    fontsize=16, color='#00ff9d', fontweight='bold', pad=20)
        
        filename = f'prediction_distribution_{int(datetime.now().timestamp())}.png'
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='#0a0e17')
        plt.close()
        
        return filepath
    
    def generate_report(self, model_name, metrics, cm=None, history=None):
        """Generate comprehensive report"""
        report_lines = [
            "=" * 60,
            f"NetSurf IDS - Model Performance Report",
            "=" * 60,
            f"Model: {model_name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "\nPerformance Metrics:",
            "-" * 60,
        ]
        
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                report_lines.append(f"{key.replace('_', ' ').title():<20}: {value:.4f}")
        
        if cm is not None:
            tn, fp, fn, tp = cm.ravel()
            report_lines.extend([
                "\nConfusion Matrix:",
                "-" * 60,
                f"True Positives:  {tp}",
                f"True Negatives:  {tn}",
                f"False Positives: {fp}",
                f"False Negatives: {fn}",
            ])
        
        report_lines.append("=" * 60)
        
        # Save report
        filename = f'{model_name}_report_{int(datetime.now().timestamp())}.txt'
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return filepath
