"""Headless match recorder producing HD MP4 replays with decision vector overlays.

Visualizes:
- Full arena view with camera smoothly tracking the AI model.
- Model decision direction vectors (moving, splitting, mass ejecting).
- Nearest food tracking line (green) & nearest threat warning line (red).
- Remerge cooldown timers on each individual subcell.
- Live telemetry HUD (mass, subcells, pellets eaten, cells eaten, action mode).
- Radar minimap in the corner.
"""

from __future__ import annotations
import os
import sys
import math
import subprocess
import argparse
from typing import Optional, Tuple, Dict, Any, List
import numpy as np

# Ensure repository root is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Set headless SDL video driver for offscreen rendering
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
from src.env.agar_engine import AgarEngine
from src.env.gym_wrapper import AgarEnv, HeuristicBot
from src.env.entities import Cell, mass_to_radius

PLAYER_COLORS = [
    (46, 204, 113),   # Player 0: Emerald Green
    (52, 152, 219),   # Bot 1: Blue
    (155, 89, 182),   # Bot 2: Purple
    (241, 196, 15),   # Bot 3: Yellow
    (230, 126, 34),   # Bot 4: Orange
    (231, 76, 60),    # Bot 5: Red
    (26, 188, 156),   # Bot 6: Turquoise
    (243, 156, 18),   # Bot 7: Amber
    (22, 160, 133),   # Bot 8: Dark Teal
    (211, 84, 0),     # Bot 9: Pumpkin
    (192, 57, 43),    # Bot 10: Pomegranate
]

VIRUS_COLOR = (50, 205, 50)
VIRUS_BORDER = (34, 139, 34)


class VideoEncoder:
    """Manages encoding RGB frames into an MP4 video file via ffmpeg or opencv."""

    def __init__(self, output_path: str, width: int = 1280, height: int = 720, fps: int = 30):
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.proc: Optional[subprocess.Popen] = None
        self.cv2_writer = None

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Check OpenCV first
        try:
            import cv2
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.cv2_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            print(f"[VideoEncoder] Using OpenCV VideoWriter -> {output_path}")
            return
        except Exception:
            self.cv2_writer = None

        # Fallback to ffmpeg subprocess
        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "rawvideo",
                "-vcodec", "rawvideo",
                "-s", f"{width}x{height}",
                "-pix_fmt", "rgb24",
                "-r", str(fps),
                "-i", "-",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                "-crf", "22",
                output_path,
            ]
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            print(f"[VideoEncoder] Using ffmpeg pipe -> {output_path}")
        except Exception as e:
            print(f"[VideoEncoder] Warning: Failed to spawn ffmpeg: {e}")

    def write_frame(self, rgb_array: np.ndarray) -> None:
        """Write an RGB numpy array (H, W, 3) to the video."""
        if self.cv2_writer is not None:
            import cv2
            bgr = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
            self.cv2_writer.write(bgr)
        elif self.proc is not None and self.proc.stdin is not None:
            self.proc.stdin.write(rgb_array.tobytes())

    def close(self) -> None:
        if self.cv2_writer is not None:
            self.cv2_writer.release()
            self.cv2_writer = None
        if self.proc is not None:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait()
            self.proc = None
        print(f"[VideoEncoder] Video successfully closed: {self.output_path}")


class MatchRecorder:
    """Simulates an Agar game and renders frames with AI decision vector overlays."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        output_path: str = "recordings/match_replay.mp4",
        screen_width: int = 1280,
        screen_height: int = 720,
        fps: int = 30,
        num_bots: int = 10,
    ):
        pygame.init()
        self.width = screen_width
        self.height = screen_height
        self.fps = fps
        self.output_path = output_path
        self.num_bots = num_bots

        self.surface = pygame.Surface((self.width, self.height))
        self.font = pygame.font.SysFont("Arial", 16, bold=True)
        self.font_large = pygame.font.SysFont("Arial", 26, bold=True)
        self.font_small = pygame.font.SysFont("Arial", 12)

        # Authentic engine setup
        self.engine = AgarEngine(
            width=2000.0,
            height=2000.0,
            num_pellets=1800,
            num_viruses=10,
            v_base=3.2,
            v_min=0.8,
            remerge_cooldown_ticks=1800,
            remerge_cooldown_mass_factor=1.2,
            mass_decay_rate=0.00002,
        )

        self.ai_player_id = 0
        self.engine.spawn_player(self.ai_player_id, initial_mass=25.0)

        self.heuristic_bots = {
            i: HeuristicBot(i) for i in range(1, self.num_bots + 1)
        }
        for i in range(1, self.num_bots + 1):
            self.engine.spawn_player(i, initial_mass=25.0)

        # Policy loading
        self.policy_fn = self._load_policy(model_path)
        self.env_helper = AgarEnv()
        self.env_helper.engine = self.engine

        # Camera
        self.cam_x = 1000.0
        self.cam_y = 1000.0
        self.cam_zoom = 1.0

        # Stats
        self.max_mass_achieved = 25.0
        self.total_pellets_eaten = 0
        self.total_cells_eaten = 0
        self.total_splits = 0

    def _load_policy(self, model_path: Optional[str]):
        """Load PPO or ONNX policy, or fallback to Heuristic."""
        if not model_path or not os.path.exists(model_path):
            print(f"[MatchRecorder] No model found at '{model_path}'. Using Heuristic policy for AI.")
            bot = HeuristicBot(self.ai_player_id)
            return lambda obs: bot.get_action(self.engine)

        if model_path.endswith(".zip"):
            try:
                from stable_baselines3 import PPO
                print(f"[MatchRecorder] Loading Stable-Baselines3 model from: {model_path}")
                sb3_model = PPO.load(model_path, device="cpu")
                return lambda obs: sb3_model.predict(obs, deterministic=True)[0]
            except Exception as e:
                print(f"[MatchRecorder] Error loading SB3 model: {e}")

        if model_path.endswith(".onnx"):
            try:
                import onnxruntime as ort
                print(f"[MatchRecorder] Loading ONNX model from: {model_path}")
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 1
                session = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])
                input_name = session.get_inputs()[0].name
                return lambda obs: np.clip(session.run(None, {input_name: obs[np.newaxis, :]})[0][0], -1.0, 1.0)
            except Exception as e:
                print(f"[MatchRecorder] Error loading ONNX model: {e}")

        bot = HeuristicBot(self.ai_player_id)
        return lambda obs: bot.get_action(self.engine)

    def _world_to_screen(self, wx: float, wy: float) -> Tuple[int, int]:
        sx = int((wx - self.cam_x) * self.cam_zoom + self.width / 2)
        sy = int((wy - self.cam_y) * self.cam_zoom + self.height / 2)
        return sx, sy

    def _update_camera(self) -> None:
        p_cells = self.engine.get_player_cells(self.ai_player_id)
        if p_cells:
            tx, ty, r = self.engine.get_player_centroid(self.ai_player_id)
            self.cam_x += (tx - self.cam_x) * 0.15
            self.cam_y += (ty - self.cam_y) * 0.15

            target_zoom = max(0.40, min(1.3, 50.0 / max(30.0, r)))
            self.cam_zoom += (target_zoom - self.cam_zoom) * 0.08
        else:
            self.cam_x = self.engine.width / 2.0
            self.cam_y = self.engine.height / 2.0
            self.cam_zoom = 0.55

    def record(self, steps: int = 800) -> Dict[str, Any]:
        """Run the match for `steps` frames and write the annotated video."""
        encoder = VideoEncoder(self.output_path, self.width, self.height, self.fps)

        print(f"[MatchRecorder] Recording match for {steps} steps at {self.fps} FPS...")
        for step in range(steps):
            # Respawn AI if dead
            if not self.engine.get_player_cells(self.ai_player_id):
                self.engine.spawn_player(self.ai_player_id, initial_mass=25.0)

            # Query AI action
            obs = self.env_helper._build_observation(player_id=self.ai_player_id)
            ai_action = self.policy_fn(obs)

            # Prepare actions for all players
            actions = {self.ai_player_id: ai_action}
            for bot_id in range(1, self.num_bots + 1):
                if not self.engine.get_player_cells(bot_id):
                    self.engine.spawn_player(bot_id, initial_mass=25.0)
                actions[bot_id] = self.heuristic_bots[bot_id].get_action(self.engine)

            # Advance engine
            events = self.engine.step(actions)
            ai_events = events.get(self.ai_player_id, {})

            self.total_pellets_eaten += ai_events.get("pellets_eaten", 0)
            self.total_cells_eaten += ai_events.get("cells_eaten", 0)
            self.total_splits += ai_events.get("splits", 0)
            current_mass = self.engine.get_player_mass(self.ai_player_id)
            if current_mass > self.max_mass_achieved:
                self.max_mass_achieved = current_mass

            # Update camera
            self._update_camera()

            # Render full visual frame with decision vector overlays
            self._render_frame(step, ai_action, ai_events)

            # Extract frame buffer
            frame_data = pygame.surfarray.array3d(self.surface)
            # Transpose from (W, H, C) to (H, W, C)
            frame_rgb = np.transpose(frame_data, (1, 0, 2))
            encoder.write_frame(frame_rgb)

            if (step + 1) % 100 == 0:
                print(f"  [Progress] Step {step + 1}/{steps} | Mass: {int(current_mass)} | Pellets: {self.total_pellets_eaten} | Eaten: {self.total_cells_eaten}")

        encoder.close()
        pygame.quit()

        summary = {
            "output_path": self.output_path,
            "steps_recorded": steps,
            "final_mass": float(self.engine.get_player_mass(self.ai_player_id)),
            "max_mass": float(self.max_mass_achieved),
            "pellets_eaten": int(self.total_pellets_eaten),
            "cells_eaten": int(self.total_cells_eaten),
            "splits_performed": int(self.total_splits),
        }
        print("\n" + "=" * 55)
        print("  MATCH RECORDING COMPLETE")
        print(f"  File: {summary['output_path']}")
        print(f"  Max Mass: {summary['max_mass']:.1f}")
        print(f"  Pellets Eaten: {summary['pellets_eaten']}")
        print(f"  Cells Eaten: {summary['cells_eaten']}")
        print(f"  Splits Performed: {summary['splits_performed']}")
        print("=" * 55)
        return summary

    def _render_frame(self, step: int, ai_action: np.ndarray, ai_events: Dict[str, Any]) -> None:
        self.surface.fill((245, 246, 250))

        # 1. Background grid
        grid_size = int(60 * self.cam_zoom)
        if grid_size > 8:
            offset_x = int((-self.cam_x * self.cam_zoom + self.width / 2) % grid_size)
            offset_y = int((-self.cam_y * self.cam_zoom + self.height / 2) % grid_size)
            for x in range(offset_x, self.width, grid_size):
                pygame.draw.line(self.surface, (230, 233, 240), (x, 0), (x, self.height), 1)
            for y in range(offset_y, self.height, grid_size):
                pygame.draw.line(self.surface, (230, 233, 240), (0, y), (self.width, y), 1)

        # 2. Arena boundaries
        bx1, by1 = self._world_to_screen(0, 0)
        bx2, by2 = self._world_to_screen(self.engine.width, self.engine.height)
        pygame.draw.rect(self.surface, (200, 70, 70), (bx1, by1, bx2 - bx1, by2 - by1), max(2, int(4 * self.cam_zoom)))

        # 3. Food Pellets
        pellet_r = max(2, int(3.0 * self.cam_zoom))
        for px, py in self.engine.pellets_xy:
            sx, sy = self._world_to_screen(px, py)
            if 0 <= sx < self.width and 0 <= sy < self.height:
                pygame.draw.circle(self.surface, (52, 152, 219), (sx, sy), pellet_r)

        # 4. Viruses
        for i in range(self.engine.num_viruses):
            vx, vy = self.engine.viruses_xy[i]
            vr = max(4, int(self.engine.virus_radii[i] * self.cam_zoom))
            sx, sy = self._world_to_screen(vx, vy)
            if -vr <= sx < self.width + vr and -vr <= sy < self.height + vr:
                pygame.draw.circle(self.surface, VIRUS_COLOR, (sx, sy), vr)
                pygame.draw.circle(self.surface, VIRUS_BORDER, (sx, sy), vr, max(2, int(3 * self.cam_zoom)))

        # 5. Ejected mass
        for em in self.engine.ejected:
            sx, sy = self._world_to_screen(em.x, em.y)
            r = max(2, int(em.radius * self.cam_zoom))
            pygame.draw.circle(self.surface, (241, 196, 15), (sx, sy), r)

        # 6. Cells
        sorted_cells = sorted(self.engine.cells, key=lambda c: c.mass)
        for cell in sorted_cells:
            sx, sy = self._world_to_screen(cell.x, cell.y)
            r = max(4, int(cell.radius * self.cam_zoom))
            color = PLAYER_COLORS[cell.player_id % len(PLAYER_COLORS)]
            dark_border = tuple(max(0, c - 35) for c in color)

            pygame.draw.circle(self.surface, color, (sx, sy), r)
            pygame.draw.circle(self.surface, dark_border, (sx, sy), r, max(1, int(3 * self.cam_zoom)))

            if r > 12:
                name = "AI Model" if cell.player_id == self.ai_player_id else f"Bot {cell.player_id}"
                lbl = self.font.render(name, True, (255, 255, 255))
                self.surface.blit(lbl, lbl.get_rect(center=(sx, sy - 6)))

                mass_str = str(int(cell.mass))
                if cell.remerge_cooldown > 0:
                    secs = int(math.ceil(cell.remerge_cooldown / 60.0))
                    mass_str += f" ({secs}s)"
                color_m = (255, 220, 100) if cell.remerge_cooldown > 0 else (240, 240, 240)
                lbl_m = self.font_small.render(mass_str, True, color_m)
                self.surface.blit(lbl_m, lbl_m.get_rect(center=(sx, sy + 10)))

        # 7. AI Model Decision Vector Overlay
        ai_cells = self.engine.get_player_cells(self.ai_player_id)
        action_desc = "MOVING"
        if ai_cells:
            cx, cy, _ = self.engine.get_player_centroid(self.ai_player_id)
            csx, csy = self._world_to_screen(cx, cy)

            a0, a1, trig = float(ai_action[0]), float(ai_action[1]), float(ai_action[2])
            norm = math.hypot(a0, a1)
            dir_x = (a0 / norm) if norm > 1e-5 else 1.0
            dir_y = (a1 / norm) if norm > 1e-5 else 0.0

            arrow_len = 110
            tip_x = int(csx + dir_x * arrow_len)
            tip_y = int(csy + dir_y * arrow_len)

            # Color by action trigger
            if trig > 0.33:
                arrow_color = (255, 40, 80)     # Red: Split
                action_desc = "SPLIT ACTION!"
                # Draw split blast indicator
                pygame.draw.circle(self.surface, (255, 80, 120), (csx, csy), int(45 * self.cam_zoom), 3)
            elif -0.33 <= trig <= 0.33:
                arrow_color = (255, 200, 30)    # Yellow: Eject Mass
                action_desc = "EJECTING MASS"
            else:
                arrow_color = (0, 210, 255)     # Cyan: Navigating
                action_desc = "HUNTING FOOD / FLEEING"

            # Draw decision vector arrow
            pygame.draw.line(self.surface, arrow_color, (csx, csy), (tip_x, tip_y), 5)
            # Arrow head
            angle = math.atan2(dir_y, dir_x)
            p1 = (tip_x - 18 * math.cos(angle - 0.45), tip_y - 18 * math.sin(angle - 0.45))
            p2 = (tip_x - 18 * math.cos(angle + 0.45), tip_y - 18 * math.sin(angle + 0.45))
            pygame.draw.polygon(self.surface, arrow_color, [(tip_x, tip_y), p1, p2])

        # 8. HUD Overlays
        self._render_hud(step, action_desc)

    def _render_hud(self, step: int, action_desc: str) -> None:
        # Top HUD banner
        top_surf = pygame.Surface((self.width, 42), pygame.SRCALPHA)
        top_surf.fill((15, 20, 32, 220))
        self.surface.blit(top_surf, (0, 0))

        title = self.font.render(f"AGAR-RL HD MATCH REPLAY  |  Step: {step}", True, (255, 255, 255))
        self.surface.blit(title, (15, 11))

        # Bottom HUD
        bot_surf = pygame.Surface((self.width, 50), pygame.SRCALPHA)
        bot_surf.fill((15, 20, 32, 220))
        self.surface.blit(bot_surf, (0, self.height - 50))

        ai_cells = self.engine.get_player_cells(self.ai_player_id)
        current_mass = int(self.engine.get_player_mass(self.ai_player_id))
        subcells = len(ai_cells)

        stats_txt = (
            f"AI Mass: {current_mass} (Max: {int(self.max_mass_achieved)})  |  "
            f"Subcells: {subcells}  |  "
            f"Pellets Eaten: {self.total_pellets_eaten}  |  "
            f"Cells Eaten: {self.total_cells_eaten}  |  "
            f"Mode: {action_desc}"
        )
        mode_color = (255, 215, 0) if "SPLIT" in action_desc else (240, 240, 240)
        lbl = self.font_large.render(stats_txt, True, mode_color)
        self.surface.blit(lbl, (15, self.height - 42))

        # Radar Minimap (bottom-right)
        map_size = 130
        map_x = self.width - map_size - 10
        map_y = self.height - map_size - 60
        s = pygame.Surface((map_size, map_size), pygame.SRCALPHA)
        s.fill((15, 20, 32, 215))
        self.surface.blit(s, (map_x, map_y))
        pygame.draw.rect(self.surface, (70, 80, 100), (map_x, map_y, map_size, map_size), 1)

        scale = map_size / self.engine.width
        for c in self.engine.cells:
            rx = int(map_x + c.x * scale)
            ry = int(map_y + c.y * scale)
            rc = (0, 255, 120) if c.player_id == self.ai_player_id else (240, 70, 70)
            pygame.draw.circle(self.surface, rc, (rx, ry), max(2, int(c.radius * scale)))


def main():
    parser = argparse.ArgumentParser(description="Record an Agar.io AI match to HD MP4")
    parser.add_argument("--model", type=str, default="checkpoints/ppo/ppo_latest.zip", help="Path to SB3 .zip or ONNX model")
    parser.add_argument("--output", type=str, default="recordings/match_replay.mp4", help="Output MP4 path")
    parser.add_argument("--steps", type=int, default=800, help="Number of steps to record (e.g. 800 @ 30 FPS = 26.6s)")
    parser.add_argument("--width", type=int, default=1280, help="Video width")
    parser.add_argument("--height", type=int, default=720, help="Video height")
    parser.add_argument("--fps", type=int, default=30, help="Video framerate")
    parser.add_argument("--bots", type=int, default=10, help="Number of bot opponents")
    args = parser.parse_args()

    recorder = MatchRecorder(
        model_path=args.model,
        output_path=args.output,
        screen_width=args.width,
        screen_height=args.height,
        fps=args.fps,
        num_bots=args.bots,
    )
    recorder.record(steps=args.steps)


if __name__ == "__main__":
    main()

