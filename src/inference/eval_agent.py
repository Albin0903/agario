"""Quantitative multi-episode evaluation script for AGAR-RL policies.

Runs in the EXACT training AgarEnv environment to produce authentic benchmarks:
- Mean and Peak Mass
- Mean Episode Reward
- Mean Pellets Eaten per Episode
- Mean Cells Eaten (Kills) per Episode
- Mean Survival Duration (Steps)
- Win / Truncation rate
"""

from __future__ import annotations
import os
import sys
import argparse
from typing import Optional, Dict, Any, List
import numpy as np

# Ensure repository root is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import yaml
from src.env.gym_wrapper import AgarEnv, HeuristicBot
from src.training.policy_arch import load_trained_model, predict_action


def load_policy(model_path: Optional[str], env: AgarEnv):
    """Load SB3 PPO (.zip) or ONNX (.onnx) policy or fallback to Heuristic."""
    if not model_path or not os.path.exists(model_path):
        print(f"[eval_agent] Modèle introuvable à '{model_path}'. Utilisation du bot Heuristique.")
        bot = HeuristicBot(env.learning_player_id)
        return lambda obs: bot.get_action(env.engine)

    if model_path.endswith(".zip"):
        try:
            print(f"[eval_agent] Chargement du modèle PyTorch Stable-Baselines3 : {model_path}")
            sb3_model = load_trained_model(model_path, device="cpu")
            return lambda obs: predict_action(
                sb3_model, obs, action_masks=env.action_masks(), deterministic=True
            )
        except Exception as e:
            print(f"[eval_agent] Erreur chargement SB3 : {e}")

    if model_path.endswith(".onnx"):
        try:
            import onnxruntime as ort
            print(f"[eval_agent] Chargement du modèle ONNX (ONNXRuntime CPU) : {model_path}")
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            session = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])
            input_name = session.get_inputs()[0].name
            return lambda obs: np.clip(session.run(None, {input_name: obs[np.newaxis, :]})[0][0], -1.0, 1.0)
        except Exception as e:
            print(f"[eval_agent] Erreur chargement ONNX : {e}")

    bot = HeuristicBot(env.learning_player_id)
    return lambda obs: bot.get_action(env.engine)


def evaluate(
    model_path: str,
    n_episodes: int = 5,
    seed: int = 42,
    num_bots: Optional[int] = None,
) -> Dict[str, Any]:
    """Run `n_episodes` of evaluation in the exact training AgarEnv."""
    cfg_path = os.path.join(ROOT_DIR, "config/env_config.yaml")
    env_cfg: Dict[str, Any] = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            env_cfg = yaml.safe_load(f) or {}

    if num_bots is not None:
        env_cfg.setdefault("simulation", {})["num_bots"] = num_bots

    actual_bots = int(env_cfg.get("simulation", {}).get("num_bots", 20))
    env = AgarEnv(config=env_cfg, seed=seed)
    policy_fn = load_policy(model_path, env)

    ep_final_masses: List[float] = []
    ep_peak_masses: List[float] = []
    ep_rewards: List[float] = []
    ep_pellets: List[int] = []
    ep_kills: List[int] = []
    ep_lengths: List[int] = []

    print("\n" + "=" * 78)
    print(f"  AGAR-RL : ÉVALUATION SCIENTIFIQUE DU MODÈLE")
    print(f"  Modèle testé        : {model_path}")
    print(f"  Arène               : {env.width:.0f}x{env.height:.0f} | Bots: {actual_bots} | Pellets: {env.engine.num_pellets}")
    print(f"  Épisodes d'évaluation: {n_episodes} parties complètes")
    print("=" * 78)

    for ep in range(1, n_episodes + 1):
        obs, info = env.reset(seed=seed + ep * 100)
        total_rew = 0.0
        peak_mass = float(info.get("player_mass", 20.0))
        steps = 0
        done = False

        while not done:
            action = policy_fn(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            total_rew += reward
            m = float(info.get("player_mass", 0.0))
            if m > peak_mass:
                peak_mass = m
            steps += 1
            done = terminated or truncated

        final_mass = float(info.get("player_mass", 0.0))
        pellets = int(info.get("episode_pellets", 0))
        kills = int(info.get("episode_kills", 0))

        ep_final_masses.append(final_mass)
        ep_peak_masses.append(peak_mass)
        ep_rewards.append(total_rew)
        ep_pellets.append(pellets)
        ep_kills.append(kills)
        ep_lengths.append(steps)

        status_str = "SURVIE MAX (TIMEOUT)" if truncated else "MORT"
        print(
            f"  [Épisode {ep:02d}/{n_episodes:02d}] "
            f"Pic Masse: {peak_mass:5.1f} | "
            f"Finale: {final_mass:5.1f} | "
            f"Pellets: {pellets:3d} | "
            f"Kills: {kills:2d} | "
            f"Score: {total_rew:6.1f} | "
            f"Durée: {steps:4d} pas ({status_str})"
        )

    results = {
        "model_path": model_path,
        "n_episodes": n_episodes,
        "mean_peak_mass": float(np.mean(ep_peak_masses)),
        "max_peak_mass": float(np.max(ep_peak_masses)),
        "mean_final_mass": float(np.mean(ep_final_masses)),
        "mean_reward": float(np.mean(ep_rewards)),
        "mean_pellets": float(np.mean(ep_pellets)),
        "mean_kills": float(np.mean(ep_kills)),
        "mean_survival_steps": float(np.mean(ep_lengths)),
    }

    print("-" * 78)
    print("  📈 MOYENNES GLOBALES DU MODÈLE :")
    print(f"  • Pic de Masse Moyen       : {results['mean_peak_mass']:.1f} (Record sur la session : {results['max_peak_mass']:.1f})")
    print(f"  • Masse Moyenne Finale     : {results['mean_final_mass']:.1f}")
    print(f"  • Récompense d'Épisode     : {results['mean_reward']:.1f}")
    print(f"  • Pellets ingérés / partie : {results['mean_pellets']:.1f}")
    print(f"  • Kills / partie           : {results['mean_kills']:.2f}")
    print(f"  • Durée moyenne de survie  : {results['mean_survival_steps']:.1f} pas")
    print("=" * 78 + "\n")
    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate AGAR-RL policy")
    parser.add_argument("--model", type=str, required=True, help="Path to .zip or .onnx model")
    parser.add_argument("--episodes", type=int, default=5, help="Number of evaluation episodes")
    parser.add_argument("--bots", type=int, default=None, help="Number of bot opponents")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    evaluate(
        model_path=args.model,
        n_episodes=args.episodes,
        seed=args.seed,
        num_bots=args.bots,
    )


if __name__ == "__main__":
    main()
