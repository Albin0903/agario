"""Export trained Stable-Baselines3 PPO models to optimized ONNX graphs for low-latency inference."""

from __future__ import annotations
import os
import sys
import time
import argparse
import math
import numpy as np
import torch
import onnx
import onnxruntime as ort
from stable_baselines3 import PPO

# Ensure repository root is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


class OnnxPolicyWrapper(torch.nn.Module):
    """Wrapper exposing deterministic actor forward pass with static [1, 3] signature."""

    def __init__(self, policy: torch.nn.Module):
        super().__init__()
        self.policy = policy
        self.action_space = getattr(policy, "action_space", None)
        self.is_multidiscrete = hasattr(self.action_space, "nvec")

    def forward(self, observation: torch.Tensor) -> torch.Tensor:
        """Compute action from observation with guaranteed signature (1, 84) -> (1, 3)."""
        features = self.policy.extract_features(observation)
        latent_pi, _ = self.policy.mlp_extractor(features)
        logits = self.policy.action_net(latent_pi)

        if self.is_multidiscrete:
            # MultiDiscrete([24, 3]): 24 angle logits + 3 trigger logits = 27 logits
            angle_logits = logits[:, :24]
            trig_logits = logits[:, 24:]
            angle_idx = torch.argmax(angle_logits, dim=-1, keepdim=True).to(torch.float32)
            trig_idx = torch.argmax(trig_logits, dim=-1, keepdim=True)

            theta = angle_idx * (2.0 * math.pi / 24.0)
            dx = torch.cos(theta)
            dy = torch.sin(theta)
            # trig: 0 -> -1.0 (idle), 1 -> 0.8 (split), 2 -> 0.4 (eject)
            trig = torch.where(trig_idx == 1, torch.tensor(0.8, device=logits.device),
                   torch.where(trig_idx == 2, torch.tensor(0.4, device=logits.device),
                                              torch.tensor(-1.0, device=logits.device)))
            return torch.cat([dx, dy, trig], dim=-1)
        else:
            return torch.clamp(logits, -1.0, 1.0)



def export_to_onnx(
    model_path: str,
    output_path: str = "models/model.onnx",
    device: str = "cpu",
    opset_version: int = 17,
    verify: bool = True,
) -> str:
    """Export an SB3 PPO model to ONNX with static (1, 84) -> (1, 3) signature."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print(f"[ONNX Export] Loading PyTorch model from: {model_path}")
    model = PPO.load(model_path, device=device)
    policy = model.policy
    policy.eval()

    wrapper = OnnxPolicyWrapper(policy).to(device)
    wrapper.eval()

    dummy_input = torch.zeros((1, 84), dtype=torch.float32, device=device)

    print(f"[ONNX Export] Exporting policy to: {output_path} (opset {opset_version})")
    torch.onnx.export(
        wrapper,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["observation"],
        output_names=["action"],
        dynamo=False,
    )

    # Validate ONNX graph structure
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print("[ONNX Export] Model validation passed successfully!")

    if verify:
        benchmark_onnx_model(output_path, wrapper)

    return output_path


def benchmark_onnx_model(
    onnx_path: str,
    pytorch_wrapper: Optional[torch.nn.Module] = None,
    num_runs: int = 1000,
) -> float:
    """Benchmark ONNX model CPU inference latency and verify output parity."""
    # Set thread count for low latency single-instance CPU inference
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    session = ort.InferenceSession(onnx_path, sess_options=opts, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    # Check input and output signatures
    in_shape = session.get_inputs()[0].shape
    out_shape = session.get_outputs()[0].shape
    print(f"[Benchmark] Graph Signature: Input {in_shape} -> Output {out_shape}")

    # Random test observations
    test_obs = np.random.uniform(-1.0, 1.0, size=(1, 84)).astype(np.float32)

    # Output verification against PyTorch if provided
    if pytorch_wrapper is not None:
        with torch.no_grad():
            torch_out = pytorch_wrapper(torch.from_numpy(test_obs)).cpu().numpy()
        onnx_out = session.run(None, {input_name: test_obs})[0]
        max_diff = float(np.max(np.abs(torch_out - onnx_out)))
        print(f"[Verification] PyTorch vs ONNX Max Absolute Difference: {max_diff:.2e}")
        assert max_diff < 1e-4, f"Discrepancy too high: {max_diff}"

    # Latency benchmark
    # Warmup
    for _ in range(50):
        session.run(None, {input_name: test_obs})

    t0 = time.perf_counter()
    for _ in range(num_runs):
        session.run(None, {input_name: test_obs})
    t1 = time.perf_counter()

    avg_latency_ms = ((t1 - t0) / num_runs) * 1000.0
    fps = 1000.0 / avg_latency_ms
    print(f"[Benchmark] Average CPU Latency: {avg_latency_ms:.3f} ms | Throughput: {fps:.0f} inferences/sec")
    if avg_latency_ms < 2.0:
        print("[Benchmark] PASS: CPU latency is strictly under 2.0 ms threshold.")
    else:
        print("[Benchmark] WARNING: CPU latency exceeds 2.0 ms threshold.")

    return avg_latency_ms


def main():
    parser = argparse.ArgumentParser(description="Export SB3 PPO model to ONNX")
    parser.add_argument("--model", type=str, default="checkpoints/ppo/ppo_final.zip", help="Path to SB3 .zip model")
    parser.add_argument("--output", type=str, default="models/model.onnx", help="Target ONNX file path")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"Error: Model file '{args.model}' not found.")
        sys.exit(1)

    export_to_onnx(model_path=args.model, output_path=args.output, opset_version=args.opset)


if __name__ == "__main__":
    main()
