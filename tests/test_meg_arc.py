import csv

import pytest
from arcengine import GameAction, GameState

from meg_arc import codes
from meg_arc.display import pos_to_cell
from meg_arc.eventlog import EventLog
from meg_arc.game import GameRunner, frame_to_rgb, make_arcade
from meg_arc.triggers import TriggerSender


class FakePort:
    def __init__(self, clock):
        self.clock = clock
        self.history = []  # (time, value)

    def set(self, code):
        self.history.append((self.clock(), code))

    def close(self):
        self.set(0)


def test_codes_unique_and_8bit():
    all_codes = (
        list(codes.INPUT.values())
        + list(codes.RESPONSE_ONSET.values())
        + [codes.ANIMATION_END, codes.LEVEL_COMPLETE, codes.GAME_OVER, codes.GAME_WIN,
           codes.INPUT_IGNORED, codes.GAME_END, codes.SESSION_START, codes.SESSION_END,
           codes.REST_START, codes.REST_END, codes.game_start(1), codes.game_start(25)]
    )
    assert len(all_codes) == len(set(all_codes))
    assert all(1 <= c <= 255 for c in all_codes)


def test_pulse_width_and_gap():
    import time

    port = FakePort(time.perf_counter)
    trig = TriggerSender([port], pulse_s=0.010, min_gap_s=0.005)
    trig.pulse(11)
    trig.pulse(30)
    (t1, a), (t2, z1), (t3, b), (t4, z2) = port.history
    assert (a, z1, b, z2) == (11, 0, 30, 0)
    assert 0.0095 <= t2 - t1 < 0.013
    assert t3 - t2 >= 0.005  # zero gap so the two codes stay separate
    with pytest.raises(ValueError):
        trig.pulse(0)


@pytest.mark.parametrize(
    "x,y,cell",
    [(-384, 384, (0, 0)), (383.9, -383.9, (63, 63)), (0, 0, (32, 32)), (400, 0, None), (0, -384, None)],
)
def test_pos_to_cell(x, y, cell):
    assert pos_to_cell(x, y, 768) == cell


def test_frame_to_rgb_matches_toolkit():
    import numpy as np
    from arc_agi.rendering import frame_to_rgb_array

    frame = np.arange(64 * 64).reshape(64, 64) % 16
    assert (frame_to_rgb(frame) == frame_to_rgb_array(0, frame, scale=1)).all()


@pytest.fixture
def arcade(tmp_path):
    return make_arcade("environment_files", str(tmp_path / "rec"), offline=True)


def test_runner_codes_on_level_complete_and_reset(arcade):
    # vc33 only uses ACTION6. Click every cell until a level is won.
    runner = GameRunner(arcade, "vc33", save_recording=False)
    resp = runner.apply(GameAction.RESET)
    assert resp.onset_codes[0] == codes.RESPONSE_ONSET[GameAction.RESET]
    seen = set()
    for y in range(64):
        for x in range(64):
            if runner.last.state is GameState.GAME_OVER:
                runner.apply(GameAction.RESET)
            r = runner.apply(GameAction.ACTION6, {"x": x, "y": y})
            assert r.onset_codes[0] == 16
            seen.update(r.onset_codes)
    assert {codes.LEVEL_COMPLETE, codes.GAME_OVER} <= seen
    assert runner.is_allowed(GameAction.RESET)
    assert not runner.is_allowed(GameAction.ACTION1)


def test_animation_end_code(arcade):
    runner = GameRunner(arcade, "ls20", save_recording=False)
    for action in [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4] * 30:
        r = runner.apply(action)
        assert (r.end_code == codes.ANIMATION_END) == (len(r.frames) > 1)


def test_eventlog(tmp_path):
    log = EventLog(tmp_path / "e.tsv", clock=lambda: 1.5)
    log.context = {"game_id": "ls20"}
    log.write("trigger", code=11)
    log.close()
    rows = list(csv.DictReader(open(tmp_path / "e.tsv"), delimiter="\t"))
    assert rows[1]["code"] == "11" and rows[1]["game_id"] == "ls20" and rows[1]["t"] == "1.500000"


def test_bridge_shapes(tmp_path):
    from meg_arc.bridge import Bridge

    b = Bridge("environment_files", str(tmp_path / "rec"))
    s = b.start_game("ls20")
    assert s["frames"].shape == (1, 64, 64, 3) and s["frames"].dtype.name == "uint8"
    assert list(s["available_actions"]) == [1, 2, 3, 4]
    assert b.is_allowed(1) and not b.is_allowed(6)
    r = b.apply(1)
    assert r["frames"].shape[1:] == (64, 64, 3) and r["n_frames"] == r["frames"].shape[0]
    assert r["onset_codes"][0] == codes.RESPONSE_ONSET[GameAction.ACTION1]
    b.start_game("vc33")
    r = b.apply(6, 10, 20)
    assert r["onset_codes"][0] == 16
    assert Bridge.input_code(0) == 9 and Bridge.input_code(6) == 6
    assert Bridge.codes()["GAME_END"] == codes.GAME_END


def test_grid_overlay_matches_web_player():
    import numpy as np

    from meg_arc.display import check_grid_px, grid_overlay, level_text

    ov = grid_overlay(640)
    assert ov.shape == (640, 640, 4) and ov.dtype == np.uint8
    a = ov[..., 3] / 255
    # one 1-px line at each inner boundary of the 10-px squares, none at the outer edge
    assert a[5, 0] == 0 and a[0, 5] == 0 and a[5, 10] == 0.2 and a[5, 9] == 0 and a[5, 11] == 0
    assert int((a[5] > 0).sum()) == 63
    # blended colours equal the web player's line colours (sampled from arcprize.org) within 1
    web = {0x33: 0x37, 0x66: 0x60, 0x00: 0x0F, 0xFF: 0xDB, 0xDC: 0xBF, 0x1E: 0x27, 0x93: 0x84}
    for cell, line in web.items():
        blended = cell * (1 - 0.2) + ov[5, 10, 0] * 0.2
        assert abs(blended - line) <= 1, (hex(cell), blended, hex(line))
    with pytest.raises(ValueError):
        check_grid_px(700)
    assert level_text(0, 7) == "LEVEL 1 / 7" and level_text(7, 7) == "LEVEL 7 / 7"


def test_game_over_then_reset(arcade):
    # Play ls20 until GAME_OVER: then only RESET is allowed, and frames never run out.
    runner = GameRunner(arcade, "ls20", save_recording=False)
    for i in range(400):
        if runner.last.state is GameState.GAME_OVER:
            break
        runner.apply([GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4][i % 4])
    assert runner.last.state is GameState.GAME_OVER
    assert runner.current_frame.shape == (64, 64)
    with pytest.raises(ValueError):
        runner.apply(GameAction.ACTION3)
    r = runner.apply(GameAction.RESET)
    assert r.frames and r.state is GameState.NOT_FINISHED
