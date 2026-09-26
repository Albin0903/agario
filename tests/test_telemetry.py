import copy
import json
from types import SimpleNamespace

import numpy as np
import yaml

from src.analysis.evaluate_scenarios_v11 import _scenario_configs
from src.env.gym_wrapper import AgarEnv
from src.training.callbacks_v11 import V11TrainingCallback
from src.training.hardware import effective_cpu_count
from src.training.telemetry import SplitKillAttributor


def test_split_kill_attribution_uses_30_decision_horizon():
    tracker = SplitKillAttributor(horizon=30)
    assert tracker.observe(split_requested=True, kills=0) == (0, 0)
    for _ in range(29):
        assert tracker.observe(split_requested=False, kills=0) == (0, 0)
    assert tracker.observe(split_requested=False, kills=1) == (1, 0)
    assert tracker.pending == () or len(tracker.pending) == 0


def test_split_without_kill_expires_and_episode_end_closes_pending():
    tracker = SplitKillAttributor(horizon=3)
    tracker.observe(split_requested=True, kills=0)
    for _ in range(3):
        assert tracker.observe(split_requested=False, kills=0) == (0, 0)
    assert tracker.observe(split_requested=False, kills=0) == (0, 1)

    tracker.observe(split_requested=True, kills=0)
    assert tracker.observe(split_requested=False, kills=0, done=True) == (0, 1)
    assert tracker.step == 0


def test_scenario_profiles_change_only_declared_pressure_inputs():
    base = {"entities": {"num_pellets": 2000}, "simulation": {"num_bots": 20}}
    original = copy.deepcopy(base)
    scenarios = _scenario_configs(base)
    assert set(scenarios) == {"standard", "sparse_food_50pct", "high_pressure_150pct_bots"}
    assert scenarios["standard"]["entities"]["num_pellets"] == 2000
    assert scenarios["sparse_food_50pct"]["entities"]["num_pellets"] == 1000
    assert scenarios["high_pressure_150pct_bots"]["simulation"]["num_bots"] == 30
    assert base == original


def test_env_reports_split_and_eject_behavior_fields():
    with open("config/env_config.yaml", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    config["simulation"]["num_bots"] = 0
    config["entities"]["num_pellets"] = 0
    config["physics"]["initial_player_mass"] = 100.0
    env = AgarEnv(config=config, seed=4)
    env.reset(seed=4)
    _, _, _, _, split_info = env.step(np.array([0, 1], dtype=np.int64))
    assert split_info["split_requested"] is True
    assert split_info["splits"] == 1

    env.reset(seed=5)
    _, _, _, _, eject_info = env.step(np.array([0, 2], dtype=np.int64))
    assert eject_info["eject_requested"] is True
    assert eject_info["ejects"] == 1
    env.close()


def test_effective_cpu_count_is_positive():
    assert effective_cpu_count() >= 1


def test_100k_metrics_persist_training_behavior_and_hardware_fields(tmp_path):
    callback = V11TrainingCallback(
        pool=[], save_dir=str(tmp_path), backup_dir=None, config={}, source_v10=None,
    )
    callback.model = SimpleNamespace(
        num_timesteps=100_000,
        logger=SimpleNamespace(name_to_value={"time/fps": 123.0}),
    )
    callback.num_timesteps = 100_000
    callback.window.update({
        "samples": 10, "mass_sum": 500.0, "peak_sum": 700.0, "peak_max": 100.0,
        "kills": 3, "split_actions": 4, "split_with_kill_30": 1,
        "split_without_kill_30": 2,
    })
    callback.window_masses.extend([50.0] * 10)
    callback.window_peaks.extend([70.0] * 10)
    callback._log_metrics()
    row = json.loads((tmp_path / "metrics.jsonl").read_text(encoding="utf-8"))
    assert row["timesteps"] == 100_000
    assert row["mass_mean"] == 50.0
    assert row["mass_p50"] == 50.0
    assert row["peak_mass_p90"] == 70.0
    assert row["kills"] == 3
    assert row["split_actions_with_kill_30"] == 1
    assert row["split_actions_without_kill_30"] == 2
    assert "gpu_utilization_percent" in row
    assert "longest_survived_episode_seconds" in row


def test_resume_retries_incomplete_million_step_scenario_suite(tmp_path):
    path = tmp_path / "scenario_evaluations.jsonl"
    rows = [
        {"evaluation_milestone": 1_000_000, "scenario": scenario, "seed": 90_000}
        for scenario in ("standard", "sparse_food_50pct")
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    callback = V11TrainingCallback(
        pool=[], save_dir=str(tmp_path), backup_dir=None, config={}, source_v10=None,
        evaluation_episodes=1,
    )
    callback.prepare_resume(1_024_000)
    assert callback.resume_evaluation_milestone == 1_000_000
