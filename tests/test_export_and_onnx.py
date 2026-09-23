"""Unit tests for ONNX export, static signature compliance, and latency thresholds."""

import os
import time
import numpy as np
import pytest
import onnx
import onnxruntime as ort
import torch
from stable_baselines3 import PPO

from src.env.gym_wrapper import AgarEnv
from src.inference.export_onnx import export_to_onnx, benchmark_onnx_model, OnnxPolicyWrapper


def test_onnx_export_and_benchmark(tmp_path):
    """Verify that export creates valid ONNX with static (1, 84) -> (1, 3) signature and < 2ms latency."""
    # 1. Create and save a small dummy PPO model
    env = AgarEnv()
    model = PPO("MlpPolicy", env, n_steps=64, batch_size=32, n_epochs=1, verbose=0)
    model.learn(total_timesteps=64)

    dummy_model_path = str(tmp_path / "test_model.zip")
    model.save(dummy_model_path)

    # 2. Export to ONNX
    onnx_path = str(tmp_path / "test_model.onnx")
    export_to_onnx(model_path=dummy_model_path, output_path=onnx_path, verify=False)

    assert os.path.exists(onnx_path)

    # 3. Check ONNX graph validity
    onnx_proto = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_proto)

    # 4. Verify static signature with onnxruntime
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    in_meta = session.get_inputs()[0]
    out_meta = session.get_outputs()[0]

    assert in_meta.shape == [1, 84], f"Expected [1, 84], got {in_meta.shape}"
    assert out_meta.shape == [1, 3], f"Expected [1, 3], got {out_meta.shape}"

    # 5. Verify numeric parity against PyTorch wrapper
    wrapper = OnnxPolicyWrapper(model.policy)
    wrapper.eval()

    test_obs = np.random.uniform(-1.0, 1.0, size=(1, 84)).astype(np.float32)
    with torch.no_grad():
        torch_res = wrapper(torch.from_numpy(test_obs)).cpu().numpy()

    onnx_res = session.run(None, {in_meta.name: test_obs})[0]
    np.testing.assert_allclose(torch_res, onnx_res, atol=1e-4)

    # 6. Benchmark latency (< 2.0 ms)
    # Warmup
    for _ in range(50):
        session.run(None, {in_meta.name: test_obs})

    runs = 500
    t0 = time.perf_counter()
    for _ in range(runs):
        session.run(None, {in_meta.name: test_obs})
    t1 = time.perf_counter()

    avg_ms = ((t1 - t0) / runs) * 1000.0
    print(f"\n[Test ONNX Latency] {avg_ms:.4f} ms per inference on CPU")
    assert avg_ms < 2.0, f"Latency {avg_ms:.4f} ms exceeds 2.0 ms threshold!"

