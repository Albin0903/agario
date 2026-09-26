import json

from src.training.train_v11 import _restore_drive_files, _resolve_v11_checkpoint


def test_auto_resume_uses_checkpoint_referenced_by_manifest(tmp_path):
    checkpoint_dir = tmp_path / "v11"
    checkpoint_dir.mkdir()
    latest = checkpoint_dir / "ppo_latest.zip"
    immutable = checkpoint_dir / "ppo_step_1000000.zip"
    latest.write_bytes(b"latest alias" * 200)
    immutable.write_bytes(b"immutable checkpoint" * 200)
    (checkpoint_dir / "v11_manifest.json").write_text(json.dumps({
        "version": "v11", "timesteps": 1_000_000,
        "step_checkpoint": immutable.name,
    }), encoding="utf-8")

    assert _resolve_v11_checkpoint("auto", checkpoint_dir, None) == immutable


def test_restore_only_fetches_manifest_checkpoint_and_active_pool(tmp_path):
    drive = tmp_path / "drive"
    local = tmp_path / "local"
    history = local / "pool"
    drive.mkdir()
    current = "ppo_step_1000000.zip"
    opponent = "ppo_step_750000.zip"
    for name in (current, opponent, "ppo_step_500000.zip"):
        (drive / name).write_bytes(b"x" * 2048)
    (drive / "v11_manifest.json").write_text(json.dumps({
        "version": "v11", "timesteps": 1_000_000,
        "step_checkpoint": current,
        "vec_normalize_checkpoint": "vec_normalize_step_1000000.pkl",
    }), encoding="utf-8")
    (drive / "vec_normalize_step_1000000.pkl").write_bytes(b"stats")
    (drive / "pool_state.json").write_text(json.dumps([
        {"path": f"/old/path/{opponent}"},
    ]), encoding="utf-8")

    _restore_drive_files(local, history, drive)

    assert (local / current).is_file()
    assert (local / opponent).is_file()
    assert not (local / "ppo_step_500000.zip").exists()
    assert (local / "vec_normalize_step_1000000.pkl").is_file()
