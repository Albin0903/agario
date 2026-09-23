"""Interactive real-time Agar.io visual game client for testing and human vs AI matches."""

from __future__ import annotations
import os
import sys
import math
import argparse
from typing import List, Tuple, Dict, Optional
import numpy as np
import pygame

# Ensure repository root is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.env.agar_engine import AgarEngine
from src.env.gym_wrapper import HeuristicBot

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False


# Aesthetic color palettes
COLOR_BG = (245, 247, 250)
COLOR_GRID = (225, 230, 238)
COLOR_BORDER = (180, 190, 205)
COLOR_VIRUS = (50, 205, 50)
COLOR_VIRUS_OUTLINE = (34, 139, 34)
COLOR_FOOD = [
    (244, 67, 54), (233, 30, 99), (156, 39, 176), (103, 58, 183),
    (63, 81, 181), (33, 150, 243), (0, 188, 212), (0, 150, 136),
    (76, 175, 80), (139, 195, 74), (255, 193, 7), (255, 152, 0),
]
PLAYER_COLORS = [
    (41, 128, 185), (231, 76, 60), (39, 174, 96), (142, 68, 173),
    (243, 156, 18), (22, 160, 133), (211, 84, 0), (192, 57, 43),
    (44, 62, 80), (127, 140, 141), (52, 73, 94),
]


class AgarGameVisualizer:
    """Interactive visual client running AgarEngine with smooth camera, HUD, and AI opponents."""

    def __init__(
        self,
        onnx_model_path: Optional[str] = None,
        screen_width: int = 1280,
        screen_height: int = 720,
        num_bots: int = 10,
    ):
        pygame.init()
        pygame.display.set_caption("AGAR-RL: Interactive Arena (Human vs Bots / AI)")
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 16, bold=True)
        self.font_large = pygame.font.SysFont("Arial", 28, bold=True)
        self.font_small = pygame.font.SysFont("Arial", 12)

        # Initialize engine
        self.engine = AgarEngine(width=2000.0, height=2000.0, num_pellets=500, num_viruses=10)
        self.human_id = 0
        self.num_bots = num_bots

        # Spawn human and bots
        self.engine.spawn_player(self.human_id, initial_mass=25.0)
        self.heuristic_bots = {
            i: HeuristicBot(i) for i in range(1, self.num_bots + 1)
        }
        for i in range(1, self.num_bots + 1):
            self.engine.spawn_player(i, initial_mass=25.0)

        # Optional ONNX policy for bots
        self.onnx_session = None
        if onnx_model_path and os.path.exists(onnx_model_path) and HAS_ONNX:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            self.onnx_session = ort.InferenceSession(onnx_model_path, sess_options=opts, providers=["CPUExecutionProvider"])
            self.onnx_input_name = self.onnx_session.get_inputs()[0].name
            print(f"[Visualizer] Loaded ONNX policy from {onnx_model_path} for opponent bots.")

        # Camera state
        self.cam_x = 1000.0
        self.cam_y = 1000.0
        self.cam_zoom = 1.0

        # Names
        self.names = {0: "YOU"}
        bot_names = ["Titan", "Blaze", "Apex", "Phantom", "Vortex", "Nebula", "Shadow", "Nova", "Cyber", "Echo"]
        for i in range(1, self.num_bots + 1):
            self.names[i] = bot_names[(i - 1) % len(bot_names)]

    def _world_to_screen(self, wx: float, wy: float) -> Tuple[int, int]:
        sx = int((wx - self.cam_x) * self.cam_zoom + self.screen_width / 2)
        sy = int((wy - self.cam_y) * self.cam_zoom + self.screen_height / 2)
        return sx, sy

    def _screen_to_world(self, sx: int, sy: int) -> Tuple[float, float]:
        wx = (sx - self.screen_width / 2) / self.cam_zoom + self.cam_x
        wy = (sy - self.screen_height / 2) / self.cam_zoom + self.cam_y
        return wx, wy

    def run(self) -> None:
        """Main game loop running at 60 FPS."""
        running = True

        while running:
            # Handle user input
            split_trigger = False
            eject_trigger = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen_width, self.screen_height = event.w, event.h
                    self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        split_trigger = True
                    elif event.key == pygame.K_w:
                        eject_trigger = True
                    elif event.key == pygame.K_r:
                        # Respawn
                        if not self.engine.get_player_cells(self.human_id):
                            self.engine.spawn_player(self.human_id, initial_mass=25.0)

            # Get mouse world direction
            mx, my = pygame.mouse.get_pos()
            target_wx, target_wy = self._screen_to_world(mx, my)

            human_cells = self.engine.get_player_cells(self.human_id)
            if human_cells:
                cx, cy, cr = self.engine.get_player_centroid(self.human_id)
                dx = target_wx - cx
                dy = target_wy - cy
                dist = math.hypot(dx, dy)
                if dist > 1e-4:
                    tx, ty = dx / dist, dy / dist
                else:
                    tx, ty = 0.0, 0.0

                trigger_val = -1.0
                if split_trigger:
                    trigger_val = 0.8
                elif eject_trigger:
                    trigger_val = 0.0

                human_action = np.array([tx, ty, trigger_val], dtype=np.float32)
            else:
                human_action = np.array([0.0, 0.0, -1.0], dtype=np.float32)

            # Build action dictionary for all agents
            actions = {self.human_id: human_action}

            for bot_id in range(1, self.num_bots + 1):
                if not self.engine.get_player_cells(bot_id):
                    self.engine.spawn_player(bot_id, initial_mass=25.0)

                bot_act = self.heuristic_bots[bot_id].get_action(self.engine)
                actions[bot_id] = bot_act

            # Advance engine physics
            self.engine.step(actions)

            # Update camera
            if human_cells:
                cx, cy, cr = self.engine.get_player_centroid(self.human_id)
                self.cam_x += (cx - self.cam_x) * 0.1
                self.cam_y += (cy - self.cam_y) * 0.1
                target_zoom = max(0.4, min(1.2, 50.0 / max(30.0, cr)))
                self.cam_zoom += (target_zoom - self.cam_zoom) * 0.05

            # Render scene
            self._render()
            self.clock.tick(60)

        pygame.quit()

    def _render(self) -> None:
        self.screen.fill(COLOR_BG)

        # Draw grid
        grid_step = int(100 * self.cam_zoom)
        if grid_step > 15:
            start_x = int(-self.cam_x * self.cam_zoom + self.screen_width / 2) % grid_step
            start_y = int(-self.cam_y * self.cam_zoom + self.screen_height / 2) % grid_step
            for x in range(start_x, self.screen_width, grid_step):
                pygame.draw.line(self.screen, COLOR_GRID, (x, 0), (x, self.screen_height), 1)
            for y in range(start_y, self.screen_height, grid_step):
                pygame.draw.line(self.screen, COLOR_GRID, (0, y), (self.screen_width, y), 1)

        # Draw Arena borders
        tl_x, tl_y = self._world_to_screen(0, 0)
        br_x, br_y = self._world_to_screen(self.engine.width, self.engine.height)
        border_rect = pygame.Rect(tl_x, tl_y, br_x - tl_x, br_y - tl_y)
        pygame.draw.rect(self.screen, COLOR_BORDER, border_rect, max(2, int(4 * self.cam_zoom)))

        # Draw Pellets
        for i in range(self.engine.num_pellets):
            px, py = self.engine.pellets_xy[i]
            sx, sy = self._world_to_screen(px, py)
            if 0 <= sx <= self.screen_width and 0 <= sy <= self.screen_height:
                color = COLOR_FOOD[i % len(COLOR_FOOD)]
                r = max(2, int(3.0 * self.cam_zoom))
                pygame.draw.circle(self.screen, color, (sx, sy), r)

        # Draw Ejected Mass
        for em in self.engine.ejected:
            sx, sy = self._world_to_screen(em.x, em.y)
            r = max(3, int(em.radius * self.cam_zoom))
            pygame.draw.circle(self.screen, (100, 100, 100), (sx, sy), r)

        # Draw Viruses (spiky outline)
        for vx, vy in self.engine.viruses_xy:
            sx, sy = self._world_to_screen(vx, vy)
            r = max(6, int(self.engine.virus_radius * self.cam_zoom))
            # Spiky circle points
            pts = []
            num_spikes = 16
            for k in range(num_spikes):
                ang = k * (2 * math.pi / num_spikes)
                rad = r if (k % 2 == 0) else int(r * 1.15)
                pts.append((sx + int(rad * math.cos(ang)), sy + int(rad * math.sin(ang))))
            pygame.draw.polygon(self.screen, COLOR_VIRUS, pts)
            pygame.draw.polygon(self.screen, COLOR_VIRUS_OUTLINE, pts, 2)

        # Draw Cells (sorted by mass for correct occlusion)
        sorted_cells = sorted(self.engine.cells, key=lambda c: c.mass)
        for cell in sorted_cells:
            sx, sy = self._world_to_screen(cell.x, cell.y)
            r = max(4, int(cell.radius * self.cam_zoom))
            color = PLAYER_COLORS[cell.player_id % len(PLAYER_COLORS)]

            # Outer border & filled circle
            pygame.draw.circle(self.screen, color, (sx, sy), r)
            dark_border = tuple(max(0, c - 30) for c in color)
            pygame.draw.circle(self.screen, dark_border, (sx, sy), r, max(1, int(3 * self.cam_zoom)))

            # Player name and mass label
            if r > 12:
                name = self.names.get(cell.player_id, f"Bot {cell.player_id}")
                lbl_name = self.font.render(name, True, (255, 255, 255))
                lbl_rect = lbl_name.get_rect(center=(sx, sy - 6))
                self.screen.blit(lbl_name, lbl_rect)

                lbl_mass = self.font_small.render(str(int(cell.mass)), True, (240, 240, 240))
                lbl_m_rect = lbl_mass.get_rect(center=(sx, sy + 10))
                self.screen.blit(lbl_mass, lbl_m_rect)

        # Draw HUD & Leaderboard
        self._render_hud()

        pygame.display.flip()

    def _render_hud(self) -> None:
        # Leaderboard (Top 10)
        leaderboard = []
        for pid in set(c.player_id for c in self.engine.cells):
            total_m = self.engine.get_player_mass(pid)
            name = self.names.get(pid, f"Bot {pid}")
            leaderboard.append((name, total_m, pid == self.human_id))

        leaderboard.sort(key=lambda x: x[1], reverse=True)

        # Leaderboard box
        box_w, box_h = 220, 30 + min(10, len(leaderboard)) * 22
        box_x = self.screen_width - box_w - 15
        box_y = 15
        s = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        s.fill((20, 25, 35, 200))
        self.screen.blit(s, (box_x, box_y))

        title = self.font.render("LEADERBOARD", True, (255, 215, 0))
        self.screen.blit(title, (box_x + 15, box_y + 8))

        for idx, (name, mass, is_me) in enumerate(leaderboard[:10]):
            color = (255, 100, 100) if is_me else (220, 220, 220)
            txt = f"{idx + 1}. {name[:10]}: {int(mass)}"
            lbl = self.font_small.render(txt, True, color)
            self.screen.blit(lbl, (box_x + 15, box_y + 32 + idx * 20))

        # Bottom-left stats
        human_mass = self.engine.get_player_mass(self.human_id)
        alive = len(self.engine.get_player_cells(self.human_id)) > 0

        fps = int(self.clock.get_fps())
        fps_lbl = self.font_small.render(f"FPS: {fps}", True, (100, 110, 130))
        self.screen.blit(fps_lbl, (15, 15))

        if alive:
            mass_txt = f"Mass: {int(human_mass)} | Controls: Mouse=Move, Space=Split, W=Eject"
            mass_lbl = self.font_large.render(mass_txt, True, (40, 50, 70))
            self.screen.blit(mass_lbl, (15, self.screen_height - 45))
        else:
            dead_txt = "YOU DIED! Press 'R' to Respawn"
            dead_lbl = self.font_large.render(dead_txt, True, (220, 40, 40))
            self.screen.blit(dead_lbl, (15, self.screen_height - 45))


def main():
    parser = argparse.ArgumentParser(description="AGAR-RL Interactive Visual Client")
    parser.add_argument("--model", type=str, default="models/model.onnx", help="Path to ONNX policy model")
    parser.add_argument("--bots", type=int, default=10, help="Number of opponents in the arena")
    args = parser.parse_args()

    game = AgarGameVisualizer(onnx_model_path=args.model, num_bots=args.bots)
    game.run()


if __name__ == "__main__":
    main()

