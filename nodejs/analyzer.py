import json
import glob
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np
import os
import sys
from textwrap import wrap

# Configuration
RESULTS_DIR = './results'
PLOTS_DIR = './plots'
os.makedirs(PLOTS_DIR, exist_ok=True)

plt.style.use('default')
sns.set_theme(style="whitegrid", palette="deep")

METRIC_NAMES = {
    'throughput': 'Throughput (msg/sec)',
    'avgLatency': 'Avg Client Latency (ms)',
    'server_latency': 'Avg Server Latency (ms)',
    'packetLoss': 'Packet Loss (%)',
    'avgJitter': 'Avg Jitter (ms)',
    'cpu_usage': 'CPU Usage (%)',
    'memory_usage': 'Memory Usage (MB)',
    'response_time': 'Response Time (ms)'
}

def load_data():
    """Load all JSON results into a DataFrame with enhanced metrics"""
    records = []
    
    if not os.path.exists(RESULTS_DIR):
        print(f"Error: Results directory '{RESULTS_DIR}' not found!")
        sys.exit(1)
        
    for client_file in glob.glob(f"{RESULTS_DIR}/client_metrics_*.json"):
        try:
            with open(client_file) as f:
                data = json.load(f)
                
                # Skip invalid files
                if not all(k in data for k in ['stats', 'system']):
                    continue
                
                # Calculate additional metrics
                duration = int(client_file.split('_')[2].replace('min.json', ''))
                server_latency = data.get('server_metrics', {}).get('avg_processing_time', 0)
                response_time = data['stats'].get('avgLatency', 0) + server_latency
                
                records.append({
                    'duration': duration,
                    'timestamp': datetime.fromisoformat(data.get('startTime', datetime.now().isoformat())),
                    **data['stats'],
                    'server_latency': server_latency,
                    'response_time': response_time,
                    'cpu_usage': data['system']['cpu']['user'] + data['system']['cpu']['system'],
                    'memory_usage': data['system']['memory']['rss'] / (1024 * 1024),
                    'test_id': os.path.basename(client_file).replace('.json', '')
                })
                
        except Exception as e:
            print(f"Error loading {client_file}: {str(e)}")
            continue
    
    if not records:
        print("No valid test data found!")
        sys.exit(1)
    
    return pd.DataFrame(records)

def create_comprehensive_report(df, filename):
    """Generate detailed report with all metrics"""
    with open(filename, 'w') as f:
        f.write("# Comprehensive Network Test Report\n\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total tests analyzed: {len(df)}\n\n")
        
        f.write("## Performance Summary\n")
        f.write(df[['duration', 'throughput', 'avgLatency', 'server_latency', 
                   'response_time', 'packetLoss', 'cpu_usage', 'memory_usage']]
               .describe().round(2).to_markdown())
        f.write("\n\n")
        
        f.write("## Key Observations\n")
        if len(df) > 1:
            f.write(f"- Max Throughput: {df['throughput'].max():.2f} msg/sec\n")
            f.write(f"- Min Response Time: {df['response_time'].min():.2f} ms\n")
            f.write(f"- Peak CPU Usage: {df['cpu_usage'].max():.2f}%\n")
            f.write(f"- Highest Memory Usage: {df['memory_usage'].max():.2f} MB\n")
        else:
            f.write("- Single test detected - run multiple tests for comparative analysis\n")

def create_detailed_plots(df):
    """Generate all visualizations with enhanced metrics"""
    try:
        # 1. System Metrics Dashboard
        plt.figure(figsize=(15, 10))
        
        # CPU Usage
        plt.subplot(2, 2, 1)
        sns.lineplot(x='duration', y='cpu_usage', data=df, marker='o')
        plt.title('CPU Usage by Test Duration')
        plt.xlabel('Duration (minutes)')
        plt.ylabel(METRIC_NAMES['cpu_usage'])
        
        # Memory Usage
        plt.subplot(2, 2, 2)
        sns.lineplot(x='duration', y='memory_usage', data=df, marker='o')
        plt.title('Memory Usage by Test Duration')
        plt.xlabel('Duration (minutes)')
        plt.ylabel(METRIC_NAMES['memory_usage'])
        
        # Response Times Comparison
        plt.subplot(2, 2, 3)
        df_melt = df.melt(id_vars=['duration'], 
                         value_vars=['avgLatency', 'server_latency', 'response_time'],
                         var_name='metric', value_name='time')
        sns.barplot(x='duration', y='time', hue='metric', data=df_melt)
        plt.title('Response Time Components')
        plt.xlabel('Duration (minutes)')
        plt.ylabel('Time (ms)')
        plt.legend(title='Metric')
        
        # Throughput vs CPU
        plt.subplot(2, 2, 4)
        sns.scatterplot(x='cpu_usage', y='throughput', hue='duration', 
                        size='memory_usage', data=df)
        plt.title('Throughput vs System Resources')
        plt.xlabel(METRIC_NAMES['cpu_usage'])
        plt.ylabel(METRIC_NAMES['throughput'])
        
        plt.tight_layout()
        plt.savefig(f"{PLOTS_DIR}/system_dashboard.png")
        plt.close()
        
        # 2. Time Series Analysis (if timestamps available)
        if 'timestamp' in df.columns and len(df) > 3:
            plt.figure(figsize=(12, 8))
            df['time'] = df['timestamp'].dt.strftime('%H:%M')
            
            plt.subplot(2, 1, 1)
            sns.lineplot(x='time', y='throughput', hue='duration', data=df)
            plt.title('Throughput Over Time')
            plt.xticks(rotation=45)
            
            plt.subplot(2, 1, 2)
            sns.lineplot(x='time', y='response_time', hue='duration', data=df)
            plt.title('Response Time Over Time')
            plt.xticks(rotation=45)
            
            plt.tight_layout()
            plt.savefig(f"{PLOTS_DIR}/timeseries_analysis.png")
            plt.close()
            
    except Exception as e:
        print(f"Plot generation warning: {str(e)}")

def main():
    print("Starting comprehensive analysis...")
    
    # Load and clean data
    df = load_data()
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    print(f"Analyzing {len(df)} test records")
    
    # Generate outputs
    create_comprehensive_report(df, f"{PLOTS_DIR}/full_report.md")
    
    if len(df) > 1:
        create_detailed_plots(df)
        print("Generated comparative visualizations")
    else:
        print("Single test detected - basic report generated")
    
    # Console summary
    print("\n=== Key Metrics ===")
    print(df[['duration', 'throughput', 'response_time', 'cpu_usage', 'memory_usage']]
          .groupby('duration').agg(['mean', 'std']).round(2).to_string())
    
    print("\nAnalysis complete. Results saved to:", PLOTS_DIR)

if __name__ == "__main__":
    main()