"""Comprehensive Model Evolution Benchmark and Comparative Visualizer for AGAR-RL.

Implements academic benchmarking metrics from GoBigger (ICLR 2023) and AgarCL:
1. Longitudinal Evolution Curves: Evaluates all checkpoints from a version folder.
2. Metrics:
   - Mass Progression (Peak, Mean, Final).
   - Predation Efficiency (Kills/1000 steps, Split Accuracy % on Prey).
   - Action Distribution & Split Discipline (Move vs Split vs Eject).
   - Survival Dynamics (Episode Length, Deaths).
   - Engine Performance Benchmark (True FPS, SPS, Step Latency in ms).
3. Matplotlib multi-panel visualization ready for Google Colab and reports.
"""

from __future__ import annotations
import os
import sys
import time
import glob
import re
import math
import argparse
import json
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import matplotlib.pyplot as plt

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.env.gym_wrapper import AgarEnv
from src.training.policy_arch import load_trained_model, predict_action


def extract_step(path: str) -> int:
    """Extract step integer from checkpoint filename."""
    fname = os.path.basename(path)
    m = re.search(r"step_(\d+)", fname)
    if m:
        return int(m.group(1))
    if fname in ("ppo_final.zip", "ppo_latest.zip", "ppo_last.zip"):
        manifest = os.path.join(os.path.dirname(path), "v10_manifest.json")
        if os.path.exists(manifest):
            try:
                with open(manifest, encoding="utf-8") as handle:
                    return int(json.load(handle).get("timesteps", 0))
            except (OSError, ValueError, TypeError):
                pass
    return 0


def benchmark_engine_speed(env: AgarEnv, num_steps: int = 1500) -> Dict[str, float]:
    """Measure exact raw engine throughput and latency without neural net overhead."""
    env.reset(seed=42)
    action = np.array([0, 0])  # angle 0, idle
    t0 = time.perf_counter()
    for _ in range(num_steps):
        env.step(action)
    total_time = time.perf_counter() - t0

    fps = num_steps / max(1e-6, total_time)
    ms_per_step = (total_time / max(1, num_steps)) * 1000.0
    return {
        "engine_fps": fps,
        "engine_ms_per_step": ms_per_step,
        "total_time_sec": total_time,
    }


def evaluate_single_checkpoint(
    model_path: str,
    env_config_path: str = "config/env_config.yaml",
    eval_steps: int = 1500,
    seed: int = 42,
) -> Dict[str, Any]:
    """Evaluate a single checkpoint on standardized academic game metrics."""
    step_num = extract_step(model_path)
    tag = os.path.basename(model_path).replace(".zip", "")

    env = AgarEnv(seed=seed)
    model = load_trained_model(model_path, device="cpu")

    obs, info = env.reset(seed=seed)

    masses: List[float] = []
    subcell_counts: List[int] = []
    kills_total = 0
    pellets_total = 0
    splits_total = 0
    splits_aimed_prey = 0
    deaths_total = 0
    ep_lengths: List[int] = []
    cur_ep_len = 0
    peak_mass = 20.0

    trigger_counts = np.zeros(3, dtype=int)  # 0: move, 1: split, 2: eject

    t0 = time.perf_counter()
    for _ in range(eval_steps):
        action = predict_action(model, obs, action_masks=env.action_masks(), deterministic=False)
        trig = int(action[1])
        trigger_counts[trig] += 1

        if trig == 1:
            splits_total += 1
            prey_dx = obs[24]
            prey_dy = obs[25]
            prey_dist = math.hypot(prey_dx, prey_dy)
            if 0.001 < prey_dist < 0.40:
                splits_aimed_prey += 1

        obs, reward, terminated, truncated, info = env.step(action)
        cur_ep_len += 1

        curr_mass = float(info.get("player_mass", 20.0))
        masses.append(curr_mass)
        if curr_mass > peak_mass:
            peak_mass = curr_mass

        kills_total += info.get("cells_eaten", 0)
        pellets_total += info.get("pellets_eaten", 0)
        subcell_counts.append(info.get("num_subcells", 1))

        if terminated or truncated:
            if terminated:
                deaths_total += 1
            ep_lengths.append(cur_ep_len)
            cur_ep_len = 0
            obs, info = env.reset()

    if cur_ep_len > 0:
        ep_lengths.append(cur_ep_len)

    total_eval_time = time.perf_counter() - t0
    eval_fps = eval_steps / max(1e-6, total_eval_time)
    eval_ms_step = (total_eval_time / max(1, eval_steps)) * 1000.0

    total_trig = max(1, int(np.sum(trigger_counts)))
    split_acc = (splits_aimed_prey / max(1, splits_total)) * 100.0

    return {
        "tag": tag,
        "step": step_num,
        "path": model_path,
        "peak_mass": float(peak_mass),
        "mean_mass": float(np.mean(masses)),
        "kills": int(kills_total),
        "kills_per_1k": float(kills_total / max(1, eval_steps) * 1000.0),
        "pellets": int(pellets_total),
        "pellets_per_1k": float(pellets_total / max(1, eval_steps) * 1000.0),
        "splits_total": int(splits_total),
        "split_rate_pct": float(trigger_counts[1] / total_trig * 100.0),
        "split_accuracy_pct": float(split_acc),
        "move_rate_pct": float(trigger_counts[0] / total_trig * 100.0),
        "eject_rate_pct": float(trigger_counts[2] / total_trig * 100.0),
        "mean_subcells": float(np.mean(subcell_counts)),
        "max_subcells": int(np.max(subcell_counts)),
        "deaths": int(deaths_total),
        "mean_survival_steps": float(np.mean(ep_lengths)) if ep_lengths else float(eval_steps),
        "eval_fps": float(eval_fps),
        "eval_ms_per_step": float(eval_ms_step),
    }


def compare_checkpoints_in_directory(
    target_dir: str,
    max_models: int = 8,
    eval_steps: int = 1200,
    output_plot: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Scan directory, benchmark all checkpoints in chronological order, and generate comparison graphs."""
    zips = glob.glob(os.path.join(target_dir, "*.zip"))
    valid = [
        z for z in zips
        if os.path.getsize(z) > 1000
        and not os.path.basename(z).startswith("._")
        and "bc_pretrained" not in z
        and "ppo_latest" not in z
    ]

    if not valid:
        print(f"⚠️ No intermediate checkpoints found in {target_dir}")
        return []

    valid.sort(key=extract_step)
    # If too many models, sample evenly
    if len(valid) > max_models:
        indices = np.linspace(0, len(valid) - 1, max_models, dtype=int)
        valid = [valid[i] for i in indices]

    print("=" * 80)
    print(f"📈 AGAR-RL MODEL EVOLUTION AUDIT: {len(valid)} Checkpoints in {target_dir}")
    print(f"   Evaluation steps per model: {eval_steps}")
    print("=" * 80)

    results: List[Dict[str, Any]] = []
    for idx, cp in enumerate(valid):
        step = extract_step(cp)
        print(f"[{idx+1}/{len(valid)}] Evaluating {os.path.basename(cp)} (Step: {step:,})...", end="", flush=True)
        res = evaluate_single_checkpoint(cp, eval_steps=eval_steps)
        results.append(res)
        print(f" -> Peak: {res['peak_mass']:.0f} | Kills: {res['kills']} | Split Acc: {res['split_accuracy_pct']:.1f}% | FPS: {res['eval_fps']:.0f}")

    # Generate Matplotlib Multi-Panel Graph
    if output_plot and len(results) > 0:
        generate_evolution_plots(results, output_plot, title_suffix=os.path.basename(target_dir))

    return results


def generate_evolution_plots(results: List[Dict[str, Any]], output_path: str, title_suffix: str = ""):
    """Generate high-resolution 6-panel academic evolution dashboard."""
    steps = [r["step"] for r in results]
    labels = [f"{r['step']//1000}k" if r['step'] < 999_999_999 else "Final" for r in results]
    x_indices = np.arange(len(results))

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10), dpi=150)
    fig.suptitle(f"AGAR-RL Model Evolution Benchmark ({title_suffix})", fontsize=16, fontweight="bold")

    # Panel 1: Peak & Mean Mass
    ax1 = axes[0, 0]
    ax1.plot(x_indices, [r["peak_mass"] for r in results], marker="o", color="#2ca02c", linewidth=2.5, label="Peak Mass")
    ax1.plot(x_indices, [r["mean_mass"] for r in results], marker="s", color="#1f77b4", linewidth=2, linestyle="--", label="Mean Mass")
    ax1.set_title("Mass Scaling Progression", fontweight="bold")
    ax1.set_xlabel("Training Steps")
    ax1.set_ylabel("Player Mass")
    ax1.set_xticks(x_indices)
    ax1.set_xticklabels(labels, rotation=35)
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # Panel 2: Combat & Kills per 1k Steps
    ax2 = axes[0, 1]
    ax2.bar(x_indices, [r["kills_per_1k"] for r in results], color="#d62728", alpha=0.8, edgecolor="black")
    ax2.set_title("Combat Efficiency (Kills per 1,000 steps)", fontweight="bold")
    ax2.set_xlabel("Training Steps")
    ax2.set_ylabel("Kills / 1k Steps")
    ax2.set_xticks(x_indices)
    ax2.set_xticklabels(labels, rotation=35)
    ax2.grid(True, alpha=0.3)

    # Panel 3: Split Discipline & Target Accuracy
    ax3 = axes[0, 2]
    ax3.plot(x_indices, [r["split_accuracy_pct"] for r in results], marker="^", color="#9467bd", linewidth=2.5, label="Split Accuracy on Prey (%)")
    ax3.plot(x_indices, [r["split_rate_pct"] for r in results], marker="v", color="#ff7f0e", linewidth=2, linestyle=":", label="Overall Split Trigger %")
    ax3.set_title("Tactical Split Accuracy & Frequency", fontweight="bold")
    ax3.set_xlabel("Training Steps")
    ax3.set_ylabel("Percentage (%)")
    ax3.set_xticks(x_indices)
    ax3.set_xticklabels(labels, rotation=35)
    ax3.legend(loc="upper left")
    ax3.grid(True, alpha=0.3)

    # Panel 4: Survival Steps Horizon
    ax4 = axes[1, 0]
    ax4.plot(x_indices, [r["mean_survival_steps"] for r in results], marker="D", color="#17becf", linewidth=2.5)
    ax4.set_title("Survival Longevity (Mean Steps Alive)", fontweight="bold")
    ax4.set_xlabel("Training Steps")
    ax4.set_ylabel("Steps per Episode")
    ax4.set_xticks(x_indices)
    ax4.set_xticklabels(labels, rotation=35)
    ax4.grid(True, alpha=0.3)

    # Panel 5: Subcell Fragmentation Control
    ax5 = axes[1, 1]
    ax5.plot(x_indices, [r["mean_subcells"] for r in results], marker="o", color="#8c564b", linewidth=2, label="Mean Subcells")
    ax5.plot(x_indices, [r["max_subcells"] for r in results], marker="x", color="#e377c2", linewidth=1.5, linestyle="--", label="Max Subcells")
    ax5.set_title("Multi-Cell Fragmentation Control", fontweight="bold")
    ax5.set_xlabel("Training Steps")
    ax5.set_ylabel("Subcell Count")
    ax5.set_xticks(x_indices)
    ax5.set_xticklabels(labels, rotation=35)
    ax5.legend(loc="upper left")
    ax5.grid(True, alpha=0.3)

    # Panel 6: Engine Throughput (FPS & Step Latency)
    ax6 = axes[1, 2]
    ax6.plot(x_indices, [r["eval_fps"] for r in results], marker="s", color="#333333", linewidth=2.5, label="End-to-End FPS")
    ax6.set_title("Inference Throughput (Steps Per Second)", fontweight="bold")
    ax6.set_xlabel("Training Steps")
    ax6.set_ylabel("Frames / Steps Per Sec")
    ax6.set_xticks(x_indices)
    ax6.set_xticklabels(labels, rotation=35)
    ax6.legend(loc="lower left")
    ax6.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"📊 Evolution dashboard successfully saved to: {output_path}")


def print_evolution_summary_table(results: List[Dict[str, Any]]):
    """Print a clean Markdown table summarizing checkpoint evolution."""
    print("\n" + "=" * 90)
    print("📊 CHECKPOINT EVOLUTION SUMMARY TABLE (SOTA ACADEMIC BENCHMARK)")
    print("=" * 90)
    header = f"{'Step':>12} | {'Peak Mass':>10} | {'Mean Mass':>10} | {'Kills/1k':>9} | {'Split Acc':>10} | {'Split Rate':>10} | {'Survival':>9} | {'FPS':>6}"
    print(header)
    print("-" * len(header))
    for r in results:
        step_str = f"{r['step']:,}" if r['step'] < 999_999_999 else "FINAL"
        print(
            f"{step_str:>12} | "
            f"{r['peak_mass']:10.1f} | "
            f"{r['mean_mass']:10.1f} | "
            f"{r['kills_per_1k']:9.2f} | "
            f"{r['split_accuracy_pct']:9.1f}% | "
            f"{r['split_rate_pct']:9.1f}% | "
            f"{r['mean_survival_steps']:9.0f} | "
            f"{r['eval_fps']:6.0f}"
        )
    print("=" * 90)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark and Compare AGAR-RL Models")
    parser.add_argument("--dir", type=str, required=True, help="Directory containing .zip checkpoints")
    parser.add_argument("--max-models", type=int, default=8, help="Max checkpoints to evaluate")
    parser.add_argument("--steps", type=int, default=1200, help="Steps per model evaluation")
    parser.add_argument("--output", type=str, default="recordings/evolution_benchmark.png", help="Output plot path")
    args = parser.parse_args()

    results = compare_checkpoints_in_directory(
        args.dir,
        max_models=args.max_models,
        eval_steps=args.steps,
        output_plot=args.output,
    )
    if results:
        print_evolution_summary_table(results)
