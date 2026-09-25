import math
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import numpy as np
import pytest
import torch

from src.env.agar_engine import Cell
from src.env.gym_wrapper import AgarEnv
from src.training.policy_arch import (
    LayerNormExtractor,
    LayerNormMaskablePolicy,
    build_policy_kwargs,
    make_cosine_annealing_lr,
    wrap_action_masker,
)


def test_action_mask_blocks_illegal_split():
    env = AgarEnv()
    env.reset(seed=42)
    mask = env.action_masks()
    assert mask.shape == (env.num_angles + 3,)
    assert mask.dtype == np.bool_
    assert np.all(mask[: env.num_angles])
    assert mask[env.num_angles + 0]  # move
    assert not mask[env.num_angles + 1]  # split illegal at mass 20
    assert mask[env.num_angles + 2]  # eject stays available

    env.engine.cells[0].mass = 80.0
    env.engine._cells_cache_valid = False
    assert env.action_masks()[env.num_angles + 1]

    env.engine.cells.clear()
    for i in range(16):
        env.engine.cells.append(Cell(id=i + 1, player_id=0, x=400.0 + i, y=400.0, mass=80.0))
    env.engine._cells_cache_valid = False
    assert not env.action_masks()[env.num_angles + 1]


def test_cosine_annealing_lr_endpoints():
    schedule = make_cosine_annealing_lr(3e-4, 1e-5)
    assert schedule(1.0) == pytest.approx(3e-4)
    assert schedule(0.0) == pytest.approx(1e-5)
    mid = schedule(0.5)
    expected = 1e-5 + 0.5 * (3e-4 - 1e-5) * (1.0 + math.cos(math.pi * 0.5))
    assert mid == pytest.approx(expected)
    assert 1e-5 < mid < 3e-4


def test_layernorm_extractor_shape():
    env = AgarEnv()
    extractor = LayerNormExtractor(env.observation_space, features_dim=512, norm_type="layernorm")
    x = torch.zeros((4, 84), dtype=torch.float32)
    y = extractor(x)
    assert y.shape == (4, 512)
    has_ln = any(isinstance(m, torch.nn.LayerNorm) for m in extractor.modules())
    assert has_ln


def test_maskable_ppo_never_samples_illegal_split():
    pytest.importorskip("sb3_contrib")
    from sb3_contrib import MaskablePPO

    env = wrap_action_masker(AgarEnv())
    kwargs = build_policy_kwargs({})
    model = MaskablePPO(
        policy=LayerNormMaskablePolicy,
        env=env,
        n_steps=32,
        batch_size=16,
        n_epochs=1,
        policy_kwargs=kwargs,
        verbose=0,
        device="cpu",
    )
    obs, _ = env.reset(seed=0)
    mask = env.action_masks()
    assert not mask[24 + 1]
    for _ in range(40):
        action, _ = model.predict(obs, deterministic=False, action_masks=mask)
        assert int(action[1]) != 1
