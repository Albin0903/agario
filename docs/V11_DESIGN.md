# AGAR-RL V11: design and verification record

## Objective

Train a policy that grows its mass, reaches new mass records, and avoids losing
its run. A training restart should be explicit and auditable: V11 starts at
step zero with a new optimizer and training state, while importing only the
policy weights from one selected V10 `MaskablePPO` checkpoint.

## What “official rules” can be verified

Miniclip's public help page says the objective is to gain mass by eating agar
and smaller cells, avoid larger cells, and split a cell after it reaches a
sufficient mass. It describes Classic, Battle Royale, Rush, Burst, and
Experimental modes. It does **not** publish Classic mode's numeric radius
curve, eat ratio, mass decay formula/rate, virus thresholds, split cooldown,
or ejection values. Consequently, this project does not label those numbers
as official. They are explicit, configurable approximations that require
in-game measurements before they can be called faithful.

Reference: [Miniclip, “How to start playing Agar.io!”](https://support.miniclip.com/hc/en-us/articles/4404685562641-How-to-start-playing-Agar-io)

The environment remains a single-player training simulation with heuristic
and self-play opponents. It is not an official Miniclip server implementation.
Any values copied from open-source server clones are community
implementations, not authoritative game rules.

## Reward decision

The task metric is mass growth and survival, not elapsed time by itself.
Positive and negative mass change already rewards growth and penalizes losses,
including configured passive decay. A record bonus should be paid only when a
new peak is reached; paying it each step while holding a peak creates a
time-based survival reward and can teach passive hiding. Death receives a
bounded terminal penalty. Reward components must be logged separately and
evaluated on held-out seeds. V11 must not add an always-on “stay alive” bonus
without an ablation showing that it increases final/peak mass rather than
passive survival.

Current V10 reward values are a baseline, not a claim of optimality. V11
selection requires a fixed-seed comparison of reward ablations using peak
mass, final mass, survival fraction, and growth per simulated minute.

## Research comparison

The recent AgarCL benchmark defines reward as the change in agent mass. Its
task is non-episodic: death respawns the player instead of ending the run, so
the authors deliberately do not add an episodic death penalty. That supports
mass delta as the primary growth signal, but its death mechanics differ from
this project. It does not establish that an extra peak bonus improves policy
quality. Because V11 explicitly values a per-episode peak, a **one-time**
bonus for crossing that peak is a testable shaping term; it should be compared
against zero and lower weights. Repeatedly paying for remaining below/at the
peak would turn elapsed time into a direct reward and over-weight passive
survival. Current mass delta already penalizes actual loss and passive decay.

GoBigger is a larger cooperative/competitive Agar-like benchmark where teams
seek higher final rank and can split/eject. It is useful for ideas about
multi-agent evaluation and league diversity, but it is not a source for
Miniclip's exact physics or a directly transferable reward result.

References: [AgarCL: The Cell Must Go On](https://arxiv.org/abs/2505.18347), [GoBigger (ICLR 2023)](https://openreview.net/forum?id=NnOZT_CR26Z).

## V10 warm start contract

`src/training/warm_start.py` checks observation/action spaces and exact policy
state-dict names and tensor shapes, then copies only `policy.state_dict()`.
It does not restore V10's optimizer, timestep counter, LR schedule progress,
VecNormalize state, rollout buffer, replay/pool state, or callbacks. The new
V11 run therefore begins at step 0. A V10 checkpoint that does not load as
`MaskablePPO` or does not match the V11 policy is rejected; there is no
fallback search through older model versions.

## Performance policy

The simulator is CPU work; PPO updates use the GPU. The A100 profile must be
measured in the target Colab runtime and includes end-to-end environment
throughput, PPO update time, peak allocated VRAM, and CPU utilization. A raw
engine FPS number is not an end-to-end training FPS number. Candidate
`n_envs`, rollout length, batch size, and epochs are benchmarked on the actual
GPU before training; the notebook records the selected profile and results.
No A100 performance result is claimed from this CPU-only development machine.
SB3 advises against running more `SubprocVecEnv` workers than logical CPU
cores for compute-bound environments, so the V11 notebook records both core
count and measured throughput instead of hard-coding the old 16-worker profile.
For CUDA, PyTorch's `high` float32 matmul mode permits TensorFloat-32 on
Ampere-class GPUs while preserving float32 tensors and outputs; it trades some
mantissa precision for matrix-multiply speed and must be measured with PPO's
losses and throughput.

References: [SB3 vectorized environments](https://stable-baselines3.readthedocs.io/en/master/guide/vec_envs.html), [SB3 PPO](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html), [PyTorch matmul precision](https://docs.pytorch.org/docs/main/generated/torch.set_float32_matmul_precision.html).

Numba kernels are compiled native code and remain the first optimization
target. A separate C/C++ extension is justified only if profiling identifies
a stable hotspot and the extension beats the Numba path end to end, including
compile/install cost and supported Colab Python versions.

The first V11 engine change is a Numba uniform-grid broadphase for pellet
collisions. The old quadratic Numba kernel remains available as a differential
reference. On this Windows CPU, one isolated kernel microbenchmark with 2,000
pellets and 40 cells measured 32.92 microseconds/call for the old broadphase
and 10.59 microseconds/call for the grid version (3.11x median speedup across
seven batches of 500 calls). The integrated synthetic profile command is
`python -m src.analysis.profile_engine --steps 4000 --warmup-steps 250 --json`;
five post-change runs measured 3,797–4,041 engine ticks/s, with 25.6–26.3% of
profiled wall time in pellet handling. These CPU numbers do not predict Colab
A100 training throughput.

`src/analysis/profile_env.py` measures one whole `AgarEnv.step`, including bot
actions, observations, and all three physics ticks. Its first local 300-step
smoke measurement was 1,067 decisions/s (3,201 engine ticks/s) with 20 bots
and 2,000 pellets. The Colab notebook runs this alongside the phase profiler
and the actual SB3 profile so each throughput number has a clear scope.

## Checkpointing and stopping

V11 checkpoints are written locally first, then mirrored to Drive with a
manifest containing the actual model timestep. The checkpoint and manifest
are replaced atomically where the filesystem permits. A normal notebook
interrupt requests a final save and sync. The evaluation notebook only reads
the V11 output directory and compares checkpoints on the same fixed seeds.

## Current verified milestone

- The replay import path no longer eagerly imports the entire training
  package.
- Headless replay initializes fonts without opening an audio device.
- Replays disable SB3's optional TensorBoard writer, avoiding an unnecessary
  TensorFlow probe in hosted environments.
- Local baseline suite: 41 tests passed before these changes; 41 tests passed
  after the replay fix.
- V11 policy-only warm-start transfer: 4 focused tests pass, including a
  synthetic MaskablePPO archive that proves optimizer state stays fresh.
