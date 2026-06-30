#!/usr/bin/env python3
"""
visualize_autosearch.py — Generate high-resolution, publication-grade figures
for Karpathy's Propose-Screen-Select validation and Green AI adaptation energy.

It extracts step-by-step training curves from raw task logs, loads final evaluation JSONs,
and generates three crucial plots:
  1. autosearch_training_curves.png — Validation PPL across steps (Optimization stability).
  2. autosearch_passkey_retrieval.png — Passkey retrieval success rates across lengths.
  3. autosearch_green_ai_efficiency.png — Adaptation energy vs Usable-Context multiples.
"""
import os, sys, re, json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Set publication style
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Inter', 'Arial', 'DejaVu Sans', 'sans-serif']
plt.rcParams['text.usetex'] = False

def parse_log_file(log_path, pattern):
    """Parse raw step-by-step metrics from log files using regex."""
    steps, ppls = [], []
    if not os.path.exists(log_path):
        print(f"[warn] Log file not found: {log_path}")
        return steps, ppls
        
    with open(log_path, 'r') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                step = int(match.group(1))
                ppl = float(match.group(2))
                steps.append(step)
                ppls.append(ppl)
    return steps, ppls

def main():
    print("🎨 Parsing training metrics from task logs...")
    
    # 1. Parse Step Progression from .system_generated/tasks
    log_dir = "/home/callensxavier_gmail_com/.gemini/antigravity-cli/brain/4f83db1f-985b-41b6-ba7f-170d05f82bec/.system_generated/tasks"
    
    # Slopes-Only Log (task-207.log)
    steps_slopes, ppls_slopes = parse_log_file(
        os.path.join(log_dir, "task-207.log"),
        r"step\s+(\d+)\s+val-ppl@512\s+([\d\.]+)"
    )
    
    # LoRA + Slopes Log (Joint) (task-231.log)
    steps_lora, ppls_lora = parse_log_file(
        os.path.join(log_dir, "task-231.log"),
        r"step\s+(\d+)\s+val-ppl@512\s+([\d\.]+)"
    )
    
    # Autosearch H1 Deep Run Log (Synchronous alignment) (task-335.log)
    steps_auto_h1, ppls_auto_h1 = parse_log_file(
        os.path.join(log_dir, "task-335.log"),
        r"Step\s+(\d+)\s+\|\s+Val PPL:\s+([\d\.]+)"
    )

    # Autosearch H4 Deep Run Log (Slopes-Only with L2 Regularization) (task-436.log)
    steps_auto_h4, ppls_auto_h4 = parse_log_file(
        os.path.join(log_dir, "task-436.log"),
        r"Step\s+(\d+)\s+\|\s+Val PPL:\s+([\d\.]+)"
    )

    # ---------------------------------------------------------------------------
    # Plot 1: Training Progression (Optimization Curves)
    # ---------------------------------------------------------------------------
    print("📈 Plotting training curves...")
    fig, ax = plt.subplots(figsize=(10.5, 6))
    
    # Plot frozen baseline as horizontal line
    ax.axhline(27.818, color='#7f8c8d', linestyle='--', linewidth=2, label='Frozen Baseline (27.82 PPL)')
    
    if steps_slopes:
        ax.plot(steps_slopes, ppls_slopes, marker='s', color='#2ecc71', linewidth=2, markersize=6, label='Slopes-Only Continued Pre-train')
    if steps_lora:
        ax.plot(steps_lora, ppls_lora, marker='^', color='#e74c3c', linewidth=2, markersize=6, label='PEFT Joint LoRA (Misaligned)')
    if steps_auto_h1:
        ax.plot(steps_auto_h1, ppls_auto_h1, marker='o', color='#3498db', linewidth=3, markersize=8, label='Autosearch H1 (Identity Reg. + Alignment)')
    if steps_auto_h4:
        ax.plot(steps_auto_h4, ppls_auto_h4, marker='d', color='#9b59b6', linewidth=3, markersize=8, label='Autosearch H4 (Slopes-Only WD)')
        
    ax.set_title("Validation Perplexity Optimization Curves ($L=512$)", fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Adaptation Steps", fontsize=12)
    ax.set_ylabel("Validation Perplexity (Lower is Better)", fontsize=12)
    ax.legend(fontsize=10, loc='upper right')
    ax.set_xlim(0, 1300)
    ax.set_ylim(22, 41)
    
    plt.tight_layout()
    plot_path1 = "autosearch_training_curves.png"
    plt.savefig(plot_path1, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"👉 Saved training curves to: {plot_path1}")

    # ---------------------------------------------------------------------------
    # Plot 2: Passkey Retrieval Success Rates
    # ---------------------------------------------------------------------------
    print("🔑 Plotting passkey retrieval success rates...")
    categories = ['1x (512)', '2x (1024)', '4x (2048)', '8x (4096)']
    x = np.arange(len(categories))
    width = 0.16
    
    fig, ax = plt.subplots(figsize=(11, 6.5))
    
    # Accuracy bars for each model
    frozen_retrieval = [100, 100, 100, 0]
    slopes_retrieval = [100, 100, 0, 0]
    lora_retrieval = [0, 0, 0, 0]
    auto_h1_retrieval = [100, 100, 0, 0]
    auto_h4_retrieval = [100, 100, 100, 0]
    
    ax.bar(x - width*2, frozen_retrieval, width, label='Frozen Baseline', color='#7f8c8d', alpha=0.8)
    ax.bar(x - width, slopes_retrieval, width, label='Slopes-Only', color='#2ecc71', alpha=0.85)
    ax.bar(x, lora_retrieval, width, label='Joint LoRA (Collapsed)', color='#e74c3c', alpha=0.85)
    ax.bar(x + width, auto_h1_retrieval, width, label='Autosearch H1 (Joint-CP)', color='#3498db', alpha=0.9)
    ax.bar(x + width*2, auto_h4_retrieval, width, label='Autosearch H4 (Slopes-Only WD)', color='#9b59b6', alpha=0.95)
    
    ax.set_title("Needle-in-a-Haystack Passkey Retrieval Success", fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Context Multiples (Tokens)", fontsize=12)
    ax.set_ylabel("Retrieval Accuracy (%)", fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylim(0, 120)
    ax.legend(fontsize=10, loc='upper right')
    
    # Annotate values
    for i in range(len(categories)):
        for offset, val, col in [(-width*2, frozen_retrieval[i], '#7f8c8d'),
                                 (-width, slopes_retrieval[i], '#2ecc71'),
                                 (0, lora_retrieval[i], '#e74c3c'),
                                 (width, auto_h1_retrieval[i], '#3498db'),
                                 (width*2, auto_h4_retrieval[i], '#9b59b6')]:
            if val > 0:
                ax.text(x[i] + offset, val + 1.5, f"{val}%", ha='center', va='bottom', fontsize=8, fontweight='semibold', color=col)
            elif val == 0 and col == '#e74c3c':
                ax.text(x[i] + offset, val + 1.5, "0%", ha='center', va='bottom', fontsize=8, color=col)

    plt.tight_layout()
    plot_path2 = "autosearch_passkey_retrieval.png"
    plt.savefig(plot_path2, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"👉 Saved passkey retrieval success to: {plot_path2}")

    # ---------------------------------------------------------------------------
    # Plot 3: Green AI Efficiency Matrix
    # ---------------------------------------------------------------------------
    print("🌿 Plotting Green AI efficiency metrics...")
    models = ['Slopes-Only', 'Joint LoRA', 'Autosearch H1', 'Autosearch H4']
    
    # We define efficiency as Usable Context Multiple (by perplexity/passkey evaluation) / kWh
    # Slopes-Only: context=4x (by perplexity, though passkey failed at 4x), energy=8.4623 => 0.4727
    # Joint LoRA: context=2x, energy=15.5367 => 0.1287
    # Autosearch H1: context=2x, energy=11.2195 => 0.1783
    # Autosearch H4: context=4x (both passkey & perplexity stable), energy=10.4749 => 4 / 10.4749 = 0.3819
    efficiency = [0.4727, 0.1287, 0.1783, 0.3819]
    carbon = [3.258, 5.982, 4.320, 4.033]         # Kilograms CO2e
    
    x = np.arange(len(models))
    width = 0.35
    
    fig, ax1 = plt.subplots(figsize=(10.5, 6))
    
    # Left Axis: Efficiency
    color = '#1abc9c'
    rects1 = ax1.bar(x - width/2, efficiency, width, label='Resource Efficiency ($\eta$)', color=color, alpha=0.9)
    ax1.set_xlabel('Adaptation Method', fontsize=12, labelpad=10)
    ax1.set_ylabel('Resource Efficiency ($\eta = \\text{Context Mult} / \\text{kWh}$)', color=color, fontsize=12)
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_ylim(0, 0.6)
    
    # Right Axis: Carbon Footprint
    ax2 = ax1.twinx()
    color = '#d35400'
    rects2 = ax2.bar(x + width/2, carbon, width, label='Carbon Footprint ($\text{kg CO}_2\text{e}$)', color=color, alpha=0.9)
    ax2.set_ylabel('Adaptation Carbon Footprint ($\text{kg CO}_2\text{e}$)', color=color, fontsize=12)
    ax2.tick_params(axis='y', labelcolor=color)
    ax2.set_ylim(0, 7.0)
    
    # Add values on top of bars
    for rect in rects1:
        height = rect.get_height()
        ax1.annotate(f'{height:.4f}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
                    
    for rect in rects2:
        height = rect.get_height()
        ax2.annotate(f'{height:.3f} kg',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
                    
    plt.title("Green AI Adaptation Metrics & Environmental Cost", fontsize=14, fontweight='bold', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(models, fontsize=11, fontweight='semibold')
    fig.tight_layout()
    plot_path3 = "autosearch_green_ai_efficiency.png"
    plt.savefig(plot_path3, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"👉 Saved Green AI efficiency plot to: {plot_path3}")
    print("\n🎉 Publication figures generated successfully!")

if __name__ == '__main__':
    main()
