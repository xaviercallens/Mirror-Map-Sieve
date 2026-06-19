import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Set style
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Inter', 'Arial', 'sans-serif']

def load_results(path):
    with open(path, 'r') as f:
        return json.load(f)

def plot_perplexity(data):
    models = []
    baseline = []
    s20 = []
    
    for k, v in data['perplexity'].items():
        if 'error' in v:
            continue
        models.append(v['model_id'].split('/')[-1])
        baseline.append(v['ppl_baseline'])
        s20.append(v['ppl_s20'])
        
    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    
    # We use a log scale because Qwen blew up
    ax.bar(x - width/2, baseline, width, label='Baseline (SDPA)', color='#3498db')
    ax.bar(x + width/2, s20, width, label='S20 Holonomic SDPA', color='#e74c3c')
    
    ax.set_ylabel('Perplexity (WikiText-2)', fontsize=12)
    ax.set_title('Hypothesis 1: Linguistic Preservation (Lower is Better)', fontsize=14, pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=11)
    ax.legend(fontsize=11)
    ax.set_yscale('log')
    
    # Add labels
    for i, (b, s) in enumerate(zip(baseline, s20)):
        ax.text(i - width/2, b * 1.1, f'{b:.2f}', ha='center', va='bottom', fontsize=10)
        ax.text(i + width/2, s * 1.1, f'{s:.2f}', ha='center', va='bottom', fontsize=10)
        if s > b * 10:
             ax.text(i + width/2, s * 2, f'+{((s-b)/b*100):.0f}%', ha='center', va='bottom', fontsize=10, color='red', fontweight='bold')

    plt.tight_layout()
    plt.savefig('s20_perplexity_benchmark.png', dpi=300, bbox_inches='tight')
    plt.close()

def plot_overhead(data):
    models = []
    seq_lens = []
    overheads = []
    
    for k, v in data['model_benchmarks'].items():
        if 'error' in v:
            continue
        model_name = v['model_id'].split('/')[-1]
        for res in v['results']:
            models.append(model_name)
            seq_lens.append(res['seq_len'])
            overheads.append(res['overhead'])
            
    # Group by seq_len
    unique_seq = sorted(list(set(seq_lens)))
    model_names = sorted(list(set(models)))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    markers = ['o', 's', '^', 'D']
    for i, m in enumerate(model_names):
        m_seq = [seq for seq, mod in zip(seq_lens, models) if mod == m]
        m_over = [over for over, mod in zip(overheads, models) if mod == m]
        
        # Sort by seq_len
        m_seq, m_over = zip(*sorted(zip(m_seq, m_over)))
        ax.plot(m_seq, m_over, marker=markers[i%len(markers)], linewidth=2, markersize=8, label=m)
        
    ax.axhline(1.0, color='black', linestyle='--', alpha=0.5, label='Zero Overhead Baseline')
    ax.fill_between([min(unique_seq), max(unique_seq)], 0.95, 1.05, color='green', alpha=0.1, label='Target Tolerance (±5%)')

    ax.set_xlabel('Sequence Length', fontsize=12)
    ax.set_ylabel('Execution Time Ratio (S20 / Baseline)', fontsize=12)
    ax.set_title('Hypothesis 3: Zero-Cost Injection overhead (< 5%)', fontsize=14, pad=20)
    ax.set_xscale('log', base=2)
    ax.set_xticks(unique_seq)
    ax.set_xticklabels(unique_seq)
    ax.legend(fontsize=11)
    
    plt.tight_layout()
    plt.savefig('s20_overhead_benchmark.png', dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    data = load_results('multi_model_results.json')
    plot_perplexity(data)
    plot_overhead(data)
    print("Visualizations saved as PNGs.")
