"""Real-time WebSocket inference client connecting trained ONNX agents to Ogar servers."""

from __future__ import annotations
import os
import sys
import time
import struct
import math
import argparse
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
import onnxruntime as ort

# Ensure repository root is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@dataclass
class OgarNode:
    """World entity tracked from Ogar binary updates."""
    id: int
    x: float
    y: float
    size: float  # radius
    is_virus: bool = False
    is_ejected: bool = False
    is_food: bool = False
    vx: float = 0.0
    vy: float = 0.0

    @property
    def mass(self) -> float:
        # r = sqrt(m) * 3 => m = (r / 3)^2
        return float((self.size / 3.0) ** 2)


class AgarBotClient:
    """Autonomous Agar.io bot communicating with Ogar servers over WebSocket using ONNX inference."""

    def __init__(
        self,
        onnx_model_path: str = "models/model.onnx",
        server_url: str = "ws://127.0.0.1:443",
        bot_name: str = "AGAR-RL-Bot",
        arena_width: float = 2000.0,
        arena_height: float = 2000.0,
        verbose: bool = True,
    ):
        self.server_url = server_url
        self.bot_name = bot_name
        self.arena_width = arena_width
        self.arena_height = arena_height
        self.verbose = verbose

        # Initialize ONNX inference session
        self._init_onnx(onnx_model_path)

        # Entity tracking
        self.nodes: Dict[int, OgarNode] = {}
        self.my_node_ids: Set[int] = set()

        # Connection handle
        self.ws = None
        self.is_running = False
        self.last_spawn_time = 0.0
        self.last_action_time = 0.0
        self.action_interval = 0.04  # 25 Hz control loop

    def _init_onnx(self, model_path: str) -> None:
        """Load and prepare ONNX Runtime session."""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"ONNX model file not found at: {model_path}")

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        if self.verbose:
            print(f"[BotClient] Loaded ONNX model from {model_path}")

    # =========================================================================
    # Packet Builders (Client -> Server)
    # =========================================================================

    def build_handshake_packets(self) -> List[bytes]:
        """Generate initial handshake packets for Ogar protocol."""
        # Packet 254 (Protocol Version 5)
        p1 = struct.pack("<BI", 254, 5)
        # Packet 255 (Client Key)
        p2 = struct.pack("<BI", 255, 1)
        return [p1, p2]

    def build_spawn_packet(self, name: Optional[str] = None) -> bytes:
        """Packet 0: Join game and set nickname (null-terminated UTF-16LE)."""
        nick = (name or self.bot_name).encode("utf-16le") + b"\x00\x00"
        return b"\x00" + nick

    def build_target_packet(self, target_x: float, target_y: float) -> bytes:
        """Packet 16: Mouse position target coordinates."""
        return struct.pack("<BiiI", 16, int(target_x), int(target_y), 0)

    def build_split_packet(self) -> bytes:
        """Packet 17: Split action (Space)."""
        return struct.pack("<B", 17)

    def build_eject_packet(self) -> bytes:
        """Packet 21: Eject mass action (W)."""
        return struct.pack("<B", 21)

    # =========================================================================
    # Packet Parsers (Server -> Client)
    # =========================================================================

    def parse_binary_packet(self, data: bytes) -> None:
        """Parse incoming binary WebSocket packet from Ogar server."""
        if not data:
            return

        opcode = data[0]

        if opcode == 16:  # Update Nodes
            self._parse_packet_16(data)
        elif opcode == 32:  # Add Node (My Cell)
            self._parse_packet_32(data)
        elif opcode == 64:  # Update Arena Bounds
            self._parse_packet_64(data)
        elif opcode == 20:  # Clear all nodes
            self.nodes.clear()
            self.my_node_ids.clear()

    def _parse_packet_32(self, data: bytes) -> None:
        """Packet 32: Server notifies client of owned node ID."""
        if len(data) >= 5:
            node_id = struct.unpack_from("<I", data, 1)[0]
            self.my_node_ids.add(node_id)
            if self.verbose:
                print(f"[BotClient] Claimed ownership of cell ID: {node_id}")

    def _parse_packet_64(self, data: bytes) -> None:
        """Packet 64: Arena boundaries."""
        if len(data) >= 33:
            min_x, min_y, max_x, max_y = struct.unpack_from("<dddd", data, 1)
            self.arena_width = float(max_x - min_x)
            self.arena_height = float(max_y - min_y)

    def _parse_packet_16(self, data: bytes) -> None:
        """Packet 16: Main world update packet containing entity moves, eats, and removes."""
        offset = 1
        # Eat records
        if len(data) < offset + 2:
            return
        eat_count = struct.unpack_from("<H", data, offset)[0]
        offset += 2

        # Skip eat pairs (eater_id: uint32, victim_id: uint32)
        for _ in range(eat_count):
            if len(data) < offset + 8:
                return
            eater_id, victim_id = struct.unpack_from("<II", data, offset)
            offset += 8
            if victim_id in self.my_node_ids:
                self.my_node_ids.discard(victim_id)
            if victim_id in self.nodes:
                del self.nodes[victim_id]

        # Updated nodes loop (until node_id == 0)
        while offset + 4 <= len(data):
            node_id = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            if node_id == 0:
                break

            # Need at least x(4) + y(4) + size(2) + color(3) + flags(1) = 14 bytes
            if offset + 14 > len(data):
                break

            x, y, size = struct.unpack_from("<iih", data, offset)
            offset += 10
            r, g, b, flags = struct.unpack_from("<BBBB", data, offset)
            offset += 4

            is_virus = bool(flags & 0x01)
            is_food = size <= 5.0 and not is_virus
            is_ejected = bool(flags & 0x20)

            # Skip skin string if present
            if flags & 0x04:
                while offset < len(data) and data[offset] != 0:
                    offset += 1
                offset += 1

            # Skip name string (null-terminated UTF-16LE) if present
            if flags & 0x08:
                while offset + 2 <= len(data):
                    char = struct.unpack_from("<H", data, offset)[0]
                    offset += 2
                    if char == 0:
                        break

            # Update velocity estimate if node previously known
            vx, vy = 0.0, 0.0
            if node_id in self.nodes:
                prev = self.nodes[node_id]
                vx = float(x - prev.x)
                vy = float(y - prev.y)

            self.nodes[node_id] = OgarNode(
                id=node_id,
                x=float(x),
                y=float(y),
                size=float(size),
                is_virus=is_virus,
                is_ejected=is_ejected,
                is_food=is_food,
                vx=vx,
                vy=vy,
            )

        # Removed nodes
        if offset + 4 <= len(data):
            remove_count = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            for _ in range(remove_count):
                if offset + 4 > len(data):
                    break
                rem_id = struct.unpack_from("<I", data, offset)[0]
                offset += 4
                self.my_node_ids.discard(rem_id)
                if rem_id in self.nodes:
                    del self.nodes[rem_id]

    # =========================================================================
    # Observation Construction & Decision Making
    # =========================================================================

    def build_observation(self) -> np.ndarray:
        """Construct the 84-dimensional egocentric observation from the live world state."""
        obs = np.zeros(84, dtype=np.float32)

        my_cells = [self.nodes[nid] for nid in self.my_node_ids if nid in self.nodes]
        if not my_cells:
            return obs

        total_mass = sum(c.mass for c in my_cells)
        cx = sum(c.x * c.mass for c in my_cells) / max(1.0, total_mass)
        cy = sum(c.y * c.mass for c in my_cells) / max(1.0, total_mass)
        eff_radius = float(math.sqrt(max(1.0, total_mass)) * 3.0)
        view_r = 500.0 + 2.0 * eff_radius

        avg_vx = sum(c.vx for c in my_cells) / len(my_cells)
        avg_vy = sum(c.vy for c in my_cells) / len(my_cells)
        v_max = 2.0

        # 1. Self State (4 floats)
        obs[0] = float(np.tanh(total_mass / 500.0))
        obs[1] = float(np.clip(avg_vx / v_max, -1.0, 1.0))
        obs[2] = float(np.clip(avg_vy / v_max, -1.0, 1.0))
        obs[3] = float(np.clip(len(my_cells) / 16.0, 0.0, 1.0))

        # Classify external entities
        pellets: List[Tuple[float, float, float]] = []  # (dist, dx, dy)
        preys: List[Tuple[float, float, float, float, float]] = []
        predators: List[Tuple[float, float, float, float, float]] = []
        viruses: List[Tuple[float, float, float]] = []

        for nid, node in self.nodes.items():
            if nid in self.my_node_ids:
                continue

            dx = node.x - cx
            dy = node.y - cy
            dist = math.hypot(dx, dy)
            if dist > view_r:
                continue

            if node.is_virus:
                viruses.append((dist, dx, dy))
            elif node.is_food or node.size <= 5.0:
                pellets.append((dist, dx, dy))
            else:
                dm = node.mass - total_mass
                v_rel = math.hypot(node.vx - avg_vx, node.vy - avg_vy)
                if node.mass <= 0.9 * total_mass:
                    preys.append((dist, dx, dy, dm, v_rel))
                elif node.mass >= 1.1 * total_mass:
                    predators.append((dist, dx, dy, dm, v_rel))

        # 2. 10 nearest Pellets (20 floats) -> offset 4 to 24
        pellets.sort(key=lambda x: x[0])
        for i, (_, dx, dy) in enumerate(pellets[:10]):
            base = 4 + i * 2
            obs[base] = float(np.clip(dx / view_r, -1.0, 1.0))
            obs[base + 1] = float(np.clip(dy / view_r, -1.0, 1.0))

        # 3. 5 Prey Cells (20 floats) -> offset 24 to 44
        preys.sort(key=lambda x: x[0])
        for i, (_, dx, dy, dm, v_rel) in enumerate(preys[:5]):
            base = 24 + i * 4
            obs[base] = float(np.clip(dx / view_r, -1.0, 1.0))
            obs[base + 1] = float(np.clip(dy / view_r, -1.0, 1.0))
            obs[base + 2] = float(np.tanh(dm / 100.0))
            obs[base + 3] = float(np.clip(v_rel / v_max, -1.0, 1.0))

        # 4. 5 Predator Cells (20 floats) -> offset 44 to 64
        predators.sort(key=lambda x: x[0])
        for i, (_, dx, dy, dm, v_rel) in enumerate(predators[:5]):
            base = 44 + i * 4
            obs[base] = float(np.clip(dx / view_r, -1.0, 1.0))
            obs[base + 1] = float(np.clip(dy / view_r, -1.0, 1.0))
            obs[base + 2] = float(np.tanh(dm / 100.0))
            obs[base + 3] = float(np.clip(v_rel / v_max, -1.0, 1.0))

        # 5. 4 nearest Viruses (12 floats) -> offset 64 to 76
        viruses.sort(key=lambda x: x[0])
        for i, (dist, dx, dy) in enumerate(viruses[:4]):
            base = 64 + i * 3
            obs[base] = float(np.clip(dx / view_r, -1.0, 1.0))
            obs[base + 1] = float(np.clip(dy / view_r, -1.0, 1.0))
            imminent = 1.0 if (total_mass > 130.0 and dist < (eff_radius + 50.0)) else 0.0
            obs[base + 2] = imminent

        # 6. Distances to Arena Walls (4 floats) -> offset 76 to 80
        obs[76] = float(np.clip((self.arena_height - cy) / view_r, 0.0, 1.0))
        obs[77] = float(np.clip(cy / view_r, 0.0, 1.0))
        obs[78] = float(np.clip(cx / view_r, 0.0, 1.0))
        obs[79] = float(np.clip((self.arena_width - cx) / view_r, 0.0, 1.0))

        # 7. Global properties (4 floats) -> offset 80 to 84
        obs[80] = float(np.clip((cx / max(1.0, self.arena_width)) * 2.0 - 1.0, -1.0, 1.0))
        obs[81] = float(np.clip((cy / max(1.0, self.arena_height)) * 2.0 - 1.0, -1.0, 1.0))
        obs[82] = float(np.clip(eff_radius / view_r, 0.0, 1.0))
        obs[83] = 0.0

        return np.clip(obs, -1.0, 1.0)

    def decide_and_act(self) -> Optional[List[bytes]]:
        """Run ONNX model inference and return list of binary control packets to send."""
        my_cells = [self.nodes[nid] for nid in self.my_node_ids if nid in self.nodes]
        now = time.time()

        # If dead or no cells owned, trigger spawn
        if not my_cells:
            if (now - self.last_spawn_time) > 2.0:
                self.last_spawn_time = now
                if self.verbose:
                    print("[BotClient] Bot dead or not spawned. Sending spawn packet...")
                return [self.build_spawn_packet()]
            return None

        # Build observation
        obs = self.build_observation()
        obs_input = np.expand_dims(obs, axis=0)  # Shape (1, 84)

        # Run ONNX inference (< 0.1 ms)
        outputs = self.session.run(None, {self.input_name: obs_input})
        action = outputs[0][0]  # Shape (3,)

        tx, ty, trigger = float(action[0]), float(action[1]), float(action[2])

        # Centroid
        total_mass = sum(c.mass for c in my_cells)
        cx = sum(c.x * c.mass for c in my_cells) / max(1.0, total_mass)
        cy = sum(c.y * c.mass for c in my_cells) / max(1.0, total_mass)

        # Map directional vector to world cursor coordinate
        target_world_x = cx + tx * 800.0
        target_world_y = cy + ty * 800.0

        packets: List[bytes] = [self.build_target_packet(target_world_x, target_world_y)]

        # Check action triggers
        if trigger > 0.33:
            packets.append(self.build_split_packet())
        elif -0.33 <= trigger <= 0.33:
            packets.append(self.build_eject_packet())

        return packets

    # =========================================================================
    # WebSocket Lifecycle & Connection
    # =========================================================================

    def run(self) -> None:
        """Connect to Ogar server and enter the real-time inference loop."""
        import websocket

        print(f"[BotClient] Connecting to Ogar server: {self.server_url}")

        def on_open(ws):
            print("[BotClient] WebSocket connected. Sending protocol handshake...")
            for pkt in self.build_handshake_packets():
                ws.send(pkt, opcode=websocket.ABNF.OPCODE_BINARY)
            # Send initial spawn
            ws.send(self.build_spawn_packet(), opcode=websocket.ABNF.OPCODE_BINARY)

        def on_message(ws, message):
            if isinstance(message, bytes):
                self.parse_binary_packet(message)

                now = time.time()
                if (now - self.last_action_time) >= self.action_interval:
                    self.last_action_time = now
                    pkts = self.decide_and_act()
                    if pkts:
                        for p in pkts:
                            ws.send(p, opcode=websocket.ABNF.OPCODE_BINARY)

        def on_error(ws, error):
            print(f"[BotClient] WebSocket Error: {error}")

        def on_close(ws, close_status_code, close_msg):
            print(f"[BotClient] Connection closed ({close_status_code}): {close_msg}")

        self.ws = websocket.WebSocketApp(
            self.server_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        try:
            self.ws.run_forever()
        except KeyboardInterrupt:
            print("\n[BotClient] Exiting bot client...")


def main():
    parser = argparse.ArgumentParser(description="AGAR-RL Ogar WebSocket Bot Client")
    parser.add_argument("--model", type=str, default="models/model.onnx", help="Path to ONNX model")
    parser.add_argument("--server", type=str, default="ws://127.0.0.1:443", help="Ogar WebSocket URL")
    parser.add_argument("--name", type=str, default="AGAR-RL-Bot", help="In-game bot name")
    parser.add_argument("--test-mock", action="store_true", help="Run simulated self-test without network")
    args = parser.parse_args()

    client = AgarBotClient(onnx_model_path=args.model, server_url=args.server, bot_name=args.name)

    if args.test_mock:
        print("[BotClient] Running mock self-test...")
        # Simulate Packet 64 (arena size)
        p64 = struct.pack("<Bdddd", 64, 0.0, 0.0, 2000.0, 2000.0)
        client.parse_binary_packet(p64)

        # Simulate Packet 32 (owned node ID)
        p32 = struct.pack("<BI", 32, 101)
        client.parse_binary_packet(p32)

        # Simulate Packet 16 (add owned cell 101, food 102, prey 103, predator 104, virus 105)
        # Construct raw packet 16
        # opcode (1) + eat_count(2) + 0 eats + nodes + node_0 + removed(4)
        nodes_data = bytearray()
        nodes_data.extend(struct.pack("<BH", 16, 0))  # opcode 16, 0 eats

        # Node 101 (own cell at 500, 500, size 30)
        nodes_data.extend(struct.pack("<IiihBBBB", 101, 500, 500, 30, 255, 0, 0, 0))
        # Node 102 (food at 520, 500, size 3)
        nodes_data.extend(struct.pack("<IiihBBBB", 102, 520, 500, 3, 0, 255, 0, 0))
        # Node 103 (prey at 550, 500, size 15)
        nodes_data.extend(struct.pack("<IiihBBBB", 103, 550, 500, 15, 0, 0, 255, 0))
        # Node 104 (predator at 300, 500, size 60)
        nodes_data.extend(struct.pack("<IiihBBBB", 104, 300, 500, 60, 255, 255, 0, 0))
        # Node 105 (virus at 600, 500, size 30, flag 1)
        nodes_data.extend(struct.pack("<IiihBBBB", 105, 600, 500, 30, 0, 255, 0, 1))

        # Terminate node list
        nodes_data.extend(struct.pack("<I", 0))
        # Remove count: 0
        nodes_data.extend(struct.pack("<I", 0))

        client.parse_binary_packet(bytes(nodes_data))

        # Now test decide_and_act
        packets = client.decide_and_act()
        assert packets is not None and len(packets) >= 1
        print(f"[BotClient] Self-test SUCCESS! Generated {len(packets)} control packets.")
    else:
        client.run()


if __name__ == "__main__":
    main()

