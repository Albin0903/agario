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

The physics engine is **CPU-only**. Its hot kernels are Numba `njit` functions
compiled to native CPU code; none use `parallel=True`/`prange`, and there is no
CUDA physics backend. The environment workers therefore parallelize across
processes: one CPU worker and one BLAS/OpenMP/Numba thread per environment.
This avoids nested thread oversubscription. `effective_cpu_count()` caps the
worker sweep using process affinity and cgroup CPU quota. The learner also
uses one PyTorch intra-op and inter-op CPU thread.

PPO policy updates can run on CPU or CUDA. The first-run Colab profile compares
both devices and worker counts using end-to-end SB3 steps/s with fixed rollout,
batch, and epoch settings; it writes the measured winner to the V11 manifest.
During training the logs record a GPU utilization snapshot and allocated/used
memory. These are samples, not interval averages. A raw engine tick rate is
not an end-to-end training FPS. No A100/L4 result is claimed until the notebook
has run on that actual Colab runtime.

SB3 says compute-bound `SubprocVecEnv` worker count should not exceed the
logical CPU cores available to the process. Numba supports thread masks for
parallel kernels, but this engine uses serial kernels inside each worker, so
turning up Numba's thread pool would not accelerate the current workload.
PyTorch's `high` float32 matmul mode permits TensorFloat-32 on Ampere-class
GPUs while retaining float32 tensors; the profile measures whether this helps
the PPO update on the active device. A CUDA rewrite of the physics would add
transfers and kernel-launch overhead to a small per-environment workload; only
a measured end-to-end win would justify adding it.

References: [SB3 vectorized environments](https://stable-baselines3.readthedocs.io/en/v2.4.0/guide/vec_envs.html), [SB3 PPO](https://stable-baselines3.readthedocs.io/en/v2.5.0/modules/ppo.html), [Numba threading layers](https://numba.readthedocs.io/en/stable/user/threading-layer.html), [PyTorch matmul precision](https://docs.pytorch.org/docs/stable/generated/torch.set_float32_matmul_precision.html).

Numba kernels are compiled native code and remain the first optimization
target. A separate C/C++ extension is justified only if profiling identifies
a stable hotspot and the extension beats the Numba path end to end, including
compile/install cost and supported Colab Python versions.

The first V11 engine change is a Numba uniform-grid broadphase for pellet
collisions. The old quadratic Numba kernel remains available as a differential
reference. On this Windows CPU, one isolated kernel microbenchmark with 2,000
pellets and 40 cells measured 32.92 microseconds/call for the old broadphase
and 10.59 microseconds/call for the grid version (3.11x median speedup across
seven batches of 500 calls). The latest integrated profile command is
`python -m src.analysis.profile_engine --steps 4000 --warmup-steps 250 --json`;
it measured 4,131 engine ticks/s with 99.15% phase coverage (pellets 25.07%,
remerge 19.61%, integration/centroids 19.15%, movement 16.60%) in the earlier
recorded run. The latest verification run measured 1,899 ticks/s with 98.99%
coverage (pellets 25.82%, remerge 20.46%, integration/centroids 19.32%,
movement 13.93%). The whole-env
profile `python -m src.analysis.profile_env --steps 2000 --warmup-steps 200
--json` most recently measured 824 decisions/s, or 2,472 physics ticks/s, with
20 bots and 2,000 pellets (an earlier run measured 2,055 decisions/s). These
single-machine CPU measurements vary with host load and do not predict Colab
A100/L4 training throughput.

`src/analysis/profile_env.py` measures one whole `AgarEnv.step`, including bot
actions, observations, and all three physics ticks. Its first local 300-step
smoke measurement was 1,067 decisions/s (3,201 engine ticks/s) with 20 bots
and 2,000 pellets. The Colab notebook runs this alongside the phase profiler
and the actual CPU/CUDA SB3 profile so each throughput number has a clear scope.

## Training telemetry and scenario checks

Every 100k timesteps, `metrics.jsonl` records current mass and peak-mass p50/p90/max,
kills/pellets per 100k, reward components, episode return and length, death
rate, longest completed episode and longest survived episode, plus the
longest live streak observed since process start. It also records requested
split actions, actual split cells, ejects, rolling training FPS, normalized
host load, and GPU utilization/memory snapshots.

Split efficiency uses a fixed, inspectable attribution: each split action is
held open for 30 agent decisions; the next kill credits the most recent open
split; unresolved splits count as without a kill when the window expires or
the episode ends. This metric is logged only and does not alter the reward.

At every million-step milestone, the saved checkpoint is evaluated on five
held-out seeds in three deterministic scenario families: standard, half the
pellets, and 150% of the configured bot count. `scenario_evaluations.jsonl`
stores each episode's peak/final mass, survival, kills, pellets, split outcome,
reward components, and simulated duration. The fixed seeds are reused across
milestones. The test is resumable by scenario and seed if Colab is interrupted.
The evaluation notebook plots peak mass, survival, and split-to-kill rate by
scenario so reward alone is not mistaken for policy improvement.

## Checkpointing and stopping

V11 checkpoints are written locally first, then mirrored to Drive with a
manifest containing the actual model timestep and the matching immutable model
and VecNormalize filenames. The manifest is published last; resume checks the
checkpoint's internal timestep against it and stops on a mismatch. Drive restore
copies only the manifest checkpoint and active self-play league, not every
historical archive. A normal notebook interrupt requests a final save and sync.
The evaluation notebook uses each checkpoint's matching normalizer and compares
checkpoints on the same fixed seeds.

## Verification record

- The replay import path no longer eagerly imports the entire training
  package.
- Headless replay initializes fonts without opening an audio device.
- Replays disable SB3's optional TensorBoard writer, avoiding an unnecessary
  TensorFlow probe in hosted environments.
- The full suite passed 59 tests after installing the project's declared
  `onnx` dependency; five warnings come from the existing Torch ONNX exporter.
- Both notebook files' code cells parse successfully, and `compileall` passes.
- V11 policy-only warm-start transfer: 4 focused tests pass, including a
  synthetic MaskablePPO archive that proves optimizer state stays fresh.
