import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import struct
import numpy as np
import pytest
from src.inference.bot_client import AgarBotClient, OgarNode


@pytest.fixture
def bot_client():
    return AgarBotClient(
        onnx_model_path="models/model.onnx",
        server_url="ws://127.0.0.1:443",
        bot_name="TestBot",
        verbose=False,
    )


def test_packet_builders(bot_client):
    """Verify serialization of handshake, spawn, target, split, and eject packets."""
    # Handshake
    hs = bot_client.build_handshake_packets()
    assert len(hs) == 2
    assert hs[0][0] == 254
    assert hs[1][0] == 255

    # Spawn
    spawn = bot_client.build_spawn_packet("Alpha")
    assert spawn[0] == 0
    assert "Alpha".encode("utf-16le") in spawn

    # Target
    target = bot_client.build_target_packet(1200, 800)
    assert len(target) == 13
    opcode, x, y, flags = struct.unpack("<BiiI", target)
    assert opcode == 16
    assert x == 1200
    assert y == 800

    # Split
    split = bot_client.build_split_packet()
    assert split == b"\x11"

    # Eject
    eject = bot_client.build_eject_packet()
    assert eject == b"\x15"


def test_packet_parsing_and_observation(bot_client):
    """Verify decoding of world state packet 16 and observation construction."""
    # Setup arena bounds
    bot_client.parse_binary_packet(struct.pack("<Bdddd", 64, 0.0, 0.0, 2000.0, 2000.0))

    # Claim ownership of node 1
    bot_client.parse_binary_packet(struct.pack("<BI", 32, 1))
    assert 1 in bot_client.my_node_ids

    # Construct Packet 16 with:
    # 0 eats, node 1 (own, mass 100 -> size 30), node 2 (pellet, size 3), node 3 (prey, size 15), 0 removed
    data = bytearray()
    data.extend(struct.pack("<BH", 16, 0))  # opcode 16, 0 eats
    data.extend(struct.pack("<IiihBBBB", 1, 500, 500, 30, 255, 0, 0, 0))
    data.extend(struct.pack("<IiihBBBB", 2, 520, 500, 3, 0, 255, 0, 0))
    data.extend(struct.pack("<IiihBBBB", 3, 550, 500, 15, 0, 0, 255, 0))
    data.extend(struct.pack("<I", 0))  # End of node update
    data.extend(struct.pack("<I", 0))  # 0 removed

    bot_client.parse_binary_packet(bytes(data))

    assert 1 in bot_client.nodes
    assert 2 in bot_client.nodes
    assert 3 in bot_client.nodes

    # Build observation
    obs = bot_client.build_observation()
    assert obs.shape == (84,)
    assert np.all(obs >= -1.0) and np.all(obs <= 1.0)

    # Test decide and act
    packets = bot_client.decide_and_act()
    assert packets is not None
    assert len(packets) >= 1
    assert packets[0][0] == 16  # Mouse target packet

