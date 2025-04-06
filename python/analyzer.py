import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import glob
import json
import os
from scipy import stats
from matplotlib.ticker import EngFormatter
from datetime import datetime

# ======================
# 1. SETUP & CONFIGURATION
# ======================

# Create output directory
os.makedirs('analysis_results', exist_ok=True)

# Modern matplotlib styling
plt.style.use('seaborn-v0_8')
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
sns.set_palette("deep")

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': 'Times New Roman',
    'font.size': 10,
    'axes.labelsize': 12,
    'axes.titlesize': 14,
    'figure.titlesize': 16,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.format': 'pdf',
    'savefig.bbox': 'tight',
    'lines.linewidth': 1.5,
    'axes.linewidth': 0.8,
    'grid.linewidth': 0.5
})

# ======================
# 2. DATA LOADING (UPDATED FOR NESTED TEST_DATA)
# ======================

def safe_convert(values):
    """Robust conversion that handles various numeric formats"""
    if values is None:
        return [np.nan]
    if not isinstance(values, (list, np.ndarray)):
        values = [values]
    
    converted = []
    for x in values:
        try:
            if x is None:
                converted.append(np.nan)
                continue
                
            if isinstance(x, str):
                x = x.replace(',', '').strip()
                if x.lower() in ['nan', 'null', 'none', '']:
                    converted.append(np.nan)
                    continue
                    
            converted.append(float(x))
        except (ValueError, TypeError):
            converted.append(np.nan)
    return converted

def parse_timestamp(ts):
    """Parse timestamp whether it's string or numeric"""
    try:
        if isinstance(ts, str):
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f").timestamp() * 1000
        return float(ts)
    except:
        return np.nan

def load_data():
    """Load test data with proper handling of nested test_data structure"""
    print("\nLoading data...")
    
    try:
        files = sorted(glob.glob('test-*.json'))
        if not files:
            raise FileNotFoundError("No test-*.json files found")
            
        print(f"Found {len(files)} JSON files to process")
        dfs = []
        
        for file in files:
            print(f"Processing file: {file}")
            with open(file) as f:
                data = json.load(f)
                
                try:
                    run_num = int(os.path.basename(file).split('-')[1].split('.')[0])
                except:
                    run_num = len(dfs) + 1
                
                if 'tests' not in data:
                    print(f"Warning: No 'tests' key in {file}")
                    continue
                    
                for test in data['tests']:
                    test_type = test.get('type')
                    duration = test.get('durationSec', 0)
                    size = test.get('messageSize', 0)
                    test_data = test.get('test_data', {})
                    
                    # Get measurements from test_data
                    latencies = safe_convert(test_data.get('latencies'))
                    throughputs = safe_convert(test_data.get('throughputs'))
                    raw_timestamps = test_data.get('timestamps', [])
                    
                    # Convert throughput from bytes to Mbps
                    throughputs = [x/125000 for x in throughputs]  # bytes to Mbps
                    
                    # Process timestamps
                    timestamps = [parse_timestamp(ts) for ts in raw_timestamps]
                    
                    # Calculate max length needed
                    max_len = max(
                        len(latencies) if latencies else 0,
                        len(throughputs) if throughputs else 0,
                        len(timestamps) if timestamps else 1
                    )
                    
                    # Pad arrays to max_len
                    def pad_array(arr, length):
                        if not arr or len(arr) == 0:
                            return [np.nan] * length
                        return list(arr) + [np.nan] * (length - len(arr))
                    
                    latencies = pad_array(latencies, max_len)
                    throughputs = pad_array(throughputs, max_len)
                    timestamps = pad_array(timestamps, max_len)
                    
                    # Calculate jitter for latency tests
                    jitter = [np.nan] * max_len
                    if test_type == 'latency' and len(latencies) > 1:
                        jitter = [np.nan]  # First value has no jitter
                        for i in range(1, len(latencies)):
                            if not np.isnan(latencies[i]) and not np.isnan(latencies[i-1]):
                                jitter.append(abs(latencies[i] - latencies[i-1]))
                            else:
                                jitter.append(np.nan)
                        jitter = pad_array(jitter, max_len)
                    
                    # Create DataFrame for this test
                    test_df = pd.DataFrame({
                        'run': [run_num] * max_len,
                        'type': [test_type] * max_len,
                        'duration': [duration] * max_len,
                        'size': [size] * max_len,
                        'latency_ms': latencies,
                        'throughput_mbps': throughputs,
                        'timestamp': timestamps,
                        'jitter_ms': jitter
                    })
                    
                    # Add system metrics
                    metrics = test.get('metrics', {})
                    for metric in ['cpuAvg', 'memAvg', 'tempAvg', 'rxTotal', 'txTotal', 'clockAvg']:
                        value = metrics.get(metric, np.nan)
                        try:
                            test_df[metric] = [float(value) if value is not None else np.nan] * max_len
                        except (ValueError, TypeError):
                            test_df[metric] = [np.nan] * max_len
                    
                    dfs.append(test_df)
        
        if not dfs:
            raise ValueError("No valid test data found in any files")
            
        df = pd.concat(dfs, ignore_index=True)
        
        # Clean data - keep rows with either latency or throughput
        initial_count = len(df)
        df = df[~df[['latency_ms', 'throughput_mbps']].isnull().all(axis=1)]
        final_count = len(df)
        print(f"\nData cleaning: Kept {final_count} of {initial_count} records after NaN removal")
        
        # Create size labels
        size_labels = {
            64: "64B", 1024: "1KB", 10240: "10KB", 
            102400: "100KB", 1048576: "1MB"
        }
        df['size_label'] = df['size'].map(size_labels)
        df['size_label'] = pd.Categorical(
            df['size_label'], 
            categories=["64B", "1KB", "10KB", "100KB", "1MB"],
            ordered=True
        )
        
        print("\nData sample:")
        print(df.head())
        print("\nData summary:")
        print(df.describe())
        
        return df
        
    except Exception as e:
        print(f"\nError loading data: {str(e)}")
        raise

# ======================
# 3. STATISTICAL ANALYSIS
# ======================

def calculate_stats(df):
    """Calculate statistics with proper grouping"""
    print("\nCalculating statistics...")
    
    try:
        stats_df = df.groupby(
            ['type', 'size', 'duration', 'size_label'], 
            observed=True
        ).agg({
            'latency_ms': ['mean', 'std', 'median', 'min', 'max', 
                          lambda x: np.nanpercentile(x, 95)],
            'jitter_ms': ['mean', 'std', 'median', 'max', 
                         lambda x: np.nanpercentile(x, 95)],
            'throughput_mbps': ['mean', 'std', 'median', 'max'],
            'cpuAvg': 'mean',
            'memAvg': 'mean',
            'tempAvg': 'mean',
            'rxTotal': 'sum',
            'txTotal': 'sum',
            'clockAvg': 'mean'
        }).reset_index()

        # Flatten columns
        stats_df.columns = [
            'type', 'size', 'duration', 'size_label',
            'latency_mean', 'latency_std', 'latency_median', 'latency_min', 
            'latency_max', 'latency_p95',
            'jitter_mean', 'jitter_std', 'jitter_median', 'jitter_max', 'jitter_p95',
            'throughput_mean', 'throughput_std', 'throughput_median', 
            'throughput_max',
            'cpu_avg', 'mem_avg', 'temp_avg',
            'rx_total', 'tx_total', 'clock_avg'
        ]
        
        print("\nStatistics sample:")
        print(stats_df.head())
        
        return stats_df
        
    except Exception as e:
        print(f"Error calculating statistics: {str(e)}")
        raise

# ======================
# 4. VISUALIZATION FUNCTIONS
# ======================

def plot_latency(df, stats_df):
    """Generate latency plots"""
    print("\nGenerating latency plots...")
    
    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        
        # Boxplot
        sns.boxplot(
            data=df[df['type'] == 'latency'],
            x='size_label',
            y='latency_ms',
            hue='duration',
            ax=ax1,
            showfliers=False,
            width=0.6
        )
        ax1.set_title('(a) Latency Distribution')
        ax1.set_yscale('log')
        ax1.set_xlabel('Message Size')
        ax1.set_ylabel('Latency (ms)')
        ax1.yaxis.set_major_formatter(EngFormatter(unit='s', places=1))
        
        # Mean with CI
        sns.barplot(
            data=stats_df[stats_df['type'] == 'latency'],
            x='size_label',
            y='latency_mean',
            hue='duration',
            ax=ax2,
            errorbar=('ci', 95),
            capsize=0.1,
            width=0.6
        )
        ax2.set_title('(b) Mean Latency with 95% CI')
        ax2.set_yscale('log')
        ax2.set_xlabel('Message Size')
        ax2.set_ylabel('Mean Latency (ms)')
        ax2.yaxis.set_major_formatter(EngFormatter(unit='s', places=1))
        
        # Adjust legend
        handles, labels = ax2.get_legend_handles_labels()
        ax2.legend(handles=handles, labels=labels, title='Duration (s)')
        ax1.get_legend().remove()
        
        plt.tight_layout()
        output_path = 'analysis_results/latency.pdf'
        plt.savefig(output_path)
        plt.close()
        print(f"Saved latency plot to {output_path}")
        
    except Exception as e:
        print(f"Error plotting latency: {str(e)}")

def plot_jitter(df, stats_df):
    """Generate jitter plots"""
    print("\nGenerating jitter plots...")
    
    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        
        # Jitter over time (example for first run)
        sample = df[
            (df['type'] == 'latency') & 
            (df['size'] == 1024) & 
            (df['run'] == 1)
        ].copy()
        if not sample.empty:
            sample['time'] = (sample['timestamp'] - sample['timestamp'].min()) / 1000
            sns.lineplot(
                data=sample,
                x='time',
                y='jitter_ms',
                ax=ax1,
                linewidth=1.5
            )
        ax1.set_title('(a) Jitter Over Time (1KB)')
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Jitter (ms)')
        ax1.yaxis.set_major_formatter(EngFormatter(unit='s', places=1))
        
        # Jitter comparison
        sns.boxplot(
            data=df[df['type'] == 'latency'],
            x='size_label',
            y='jitter_ms',
            hue='duration',
            ax=ax2,
            showfliers=False,
            width=0.6
        )
        ax2.set_title('(b) Jitter Distribution by Message Size')
        ax2.set_yscale('log')
        ax2.set_xlabel('Message Size')
        ax2.set_ylabel('Jitter (ms)')
        ax2.yaxis.set_major_formatter(EngFormatter(unit='s', places=1))
        
        plt.tight_layout()
        output_path = 'analysis_results/jitter.pdf'
        plt.savefig(output_path)
        plt.close()
        print(f"Saved jitter plot to {output_path}")
        
    except Exception as e:
        print(f"Error plotting jitter: {str(e)}")

def plot_throughput(df, stats_df):
    """Generate throughput plots"""
    print("\nGenerating throughput plots...")
    
    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        
        # Time series
        sample = df[
            (df['type'] == 'throughput') & 
            (df['size'] == 1048576) & 
            (df['run'] == 1)
        ].copy()
        if not sample.empty:
            sample['time'] = (sample['timestamp'] - sample['timestamp'].min()) / 1000
            sns.lineplot(
                data=sample,
                x='time',
                y='throughput_mbps',
                ax=ax1,
                linewidth=1.5
            )
        ax1.set_title('(a) Throughput Time Series (1MB)')
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Throughput (Mbps)')
        ax1.yaxis.set_major_formatter(EngFormatter(unit='bps', places=1))
        
        # Comparison plot
        sns.barplot(
            data=stats_df[stats_df['type'] == 'throughput'],
            x='size_label',
            y='throughput_mean',
            hue='duration',
            ax=ax2,
            errorbar=('ci', 95),
            capsize=0.1,
            width=0.6
        )
        ax2.set_title('(b) Mean Throughput Comparison')
        ax2.set_xlabel('Message Size')
        ax2.set_ylabel('Throughput (Mbps)')
        ax2.yaxis.set_major_formatter(EngFormatter(unit='bps', places=1))
        
        # Adjust legend
        handles, labels = ax2.get_legend_handles_labels()
        ax2.legend(handles=handles, labels=labels, title='Duration (s)')
        
        plt.tight_layout()
        output_path = 'analysis_results/throughput.pdf'
        plt.savefig(output_path)
        plt.close()
        print(f"Saved throughput plot to {output_path}")
        
    except Exception as e:
        print(f"Error plotting throughput: {str(e)}")

def plot_resource_usage(stats_df):
    """Generate resource usage plots"""
    print("\nGenerating resource usage plots...")
    
    try:
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
        
        # CPU Usage
        sns.lineplot(
            data=stats_df,
            x='size',
            y='cpu_avg',
            hue='type',
            style='type',
            markers=True,
            ax=ax1,
            linewidth=1.5
        )
        ax1.set_title('(a) CPU Usage by Message Size')
        ax1.set_xlabel('Message Size (bytes)')
        ax1.set_ylabel('CPU Utilization (%)')
        ax1.set_xscale('log')
        ax1.set_xticks([64, 1024, 10240, 102400, 1048576])
        ax1.set_xticklabels(["64B", "1KB", "10KB", "100KB", "1MB"])
        
        # Temperature
        sns.lineplot(
            data=stats_df,
            x='duration',
            y='temp_avg',
            hue='type',
            style='size_label',
            markers=True,
            ax=ax2,
            linewidth=1.5
        )
        ax2.set_title('(b) Temperature by Test Duration')
        ax2.set_xlabel('Test Duration (s)')
        ax2.set_ylabel('Temperature (°C)')
        
        # Network Activity
        stats_df['total_network'] = stats_df['rx_total'] + stats_df['tx_total']
        sns.barplot(
            data=stats_df,
            x='size_label',
            y='total_network',
            hue='type',
            ax=ax3
        )
        ax3.set_title('(c) Total Network Activity')
        ax3.set_xlabel('Message Size')
        ax3.set_ylabel('Total Bytes Transferred')
        ax3.yaxis.set_major_formatter(EngFormatter(unit='B'))
        
        plt.tight_layout()
        output_path = 'analysis_results/resource_usage.pdf'
        plt.savefig(output_path)
        plt.close()
        print(f"Saved resource usage plot to {output_path}")
        
    except Exception as e:
        print(f"Error plotting resource usage: {str(e)}")

def generate_latex_tables(stats_df):
    """Generate LaTeX tables of results"""
    print("\nGenerating LaTeX tables...")
    
    try:
        def format_float(x):
            if pd.isna(x):
                return "-"
            if x < 1:
                return f"{x:.3f}"
            if x < 10:
                return f"{x:.2f}"
            if x < 100:
                return f"{x:.1f}"
            return f"{int(round(x))}"
        
        # Latency table
        latency_table = stats_df[
            stats_df['type'] == 'latency'
        ].pivot_table(
            index='size_label',
            columns='duration',
            values=['latency_mean', 'latency_p95', 'jitter_mean', 'jitter_p95'],
            aggfunc='first'
        ).map(format_float).to_latex(
            caption="Latency and Jitter measurements (ms) across different message sizes and test durations",
            label="tab:latency_jitter",
            position='htbp'
        )
        
        # Throughput table
        throughput_table = stats_df[
            stats_df['type'] == 'throughput'
        ].pivot_table(
            index='size_label',
            columns='duration',
            values=['throughput_mean', 'throughput_max'],
            aggfunc='first'
        ).map(format_float).to_latex(
            caption="Throughput measurements (Mbps) across different message sizes",
            label="tab:throughput",
            position='htbp'
        )
        
        # Resource usage table
        resource_table = stats_df.pivot_table(
            index=['type', 'size_label'],
            columns='duration',
            values=['cpu_avg', 'mem_avg', 'temp_avg'],
            aggfunc='first'
        ).map(format_float).to_latex(
            caption="System resource usage during tests",
            label="tab:resource_usage",
            position='htbp'
        )
        
        # Save tables
        with open('analysis_results/latency_jitter_table.tex', 'w') as f:
            f.write(latency_table)
        with open('analysis_results/throughput_table.tex', 'w') as f:
            f.write(throughput_table)
        with open('analysis_results/resource_table.tex', 'w') as f:
            f.write(resource_table)
            
        print("Saved LaTeX tables to analysis_results/")
        
    except Exception as e:
        print(f"Error generating LaTeX tables: {str(e)}")

# ======================
# 5. MAIN EXECUTION
# ======================

def main():
    print("Analyzer starting...")
    print(f"Output will be saved to: {os.path.abspath('analysis_results')}")
    
    try:
        # Load data
        df = load_data()
        
        if df.empty:
            print("\nERROR: No valid data loaded. Check your JSON files.")
            return
        
        # Calculate statistics
        stats_df = calculate_stats(df)
        
        # Generate visualizations
        plot_latency(df, stats_df)
        plot_jitter(df, stats_df)
        plot_throughput(df, stats_df)
        plot_resource_usage(stats_df)
        
        # Generate LaTeX tables
        generate_latex_tables(stats_df)
        
        # Save statistics
        stats_df.to_csv('analysis_results/test_statistics.csv', index=False)
        print("\nSaved statistics to analysis_results/test_statistics.csv")
        
        print("\nAnalysis complete! Results saved to analysis_results/")
        
    except Exception as e:
        print(f"\nError during analysis: {str(e)}")

if __name__ == '__main__':
    main()