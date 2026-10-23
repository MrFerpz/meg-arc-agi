"""MATLAB bridge: lets a Psychtoolbox (MATLAB) task run ARC-AGI-3 games.

MATLAB owns the screen, the input and the triggers. Python only runs the game.
Every return value is a plain dict of numpy arrays, ints and strings, so that
MATLAB converts it with struct(), uint8(), double() and string().

Two ways to call it:

1. In-process (MATLAB R2024b or newer, Python 3.12):
       bridge = py.meg_arc.bridge.Bridge("environment_files", "data/arc_recordings");
       s = struct(bridge.start_game("ls20"));
2. Local HTTP (any MATLAB version), start the server first:
       uv run python -m meg_arc.bridge --port 8765
   then call webwrite("http://127.0.0.1:8765/apply", ...) from MATLAB.
"""

import argparse
import logging
from typing import Any

import numpy as np
from arcengine import GameAction

from . import codes, display
from .game import GameRunner, Response, frame_to_rgb, make_arcade


def _response_dict(resp: Response) -> dict[str, Any]:
    return {
        # n x 64 x 64 x 3 uint8. MATLAB: frames = uint8(s.frames)
        "frames": np.stack([frame_to_rgb(f) for f in resp.frames]),
        "n_frames": len(resp.frames),
        "onset_codes": np.array(resp.onset_codes, dtype=np.int32),
        "end_codes": np.array(resp.end_codes, dtype=np.int32),  # send on the last flip
        "state": resp.state.name,
        "levels_completed": resp.levels_completed,
        "win_levels": resp.win_levels,
    }


class Bridge:
    def __init__(self, environments_dir: str = "environment_files",
                 recordings_dir: str = "recordings", offline: bool = True) -> None:
        self.arcade = make_arcade(environments_dir, recordings_dir, offline=offline)
        self.runner: GameRunner | None = None

    def start_game(self, game_id: str, seed: int = 0) -> dict[str, Any]:
        self.runner = GameRunner(self.arcade, str(game_id), seed=int(seed))
        last = self.runner.last
        return {
            "frames": frame_to_rgb(self.runner.current_frame)[None],
            "n_frames": 1,
            "available_actions": np.array(last.available_actions, dtype=np.int32),
            "default_fps": self.runner.default_fps,
            "state": last.state.name,
            "levels_completed": last.levels_completed,
            "win_levels": last.win_levels,
        }

    def _runner(self) -> GameRunner:
        if self.runner is None:
            raise RuntimeError("call start_game() first")
        return self.runner

    @staticmethod
    def codes() -> dict[str, int]:
        """All fixed trigger codes, so MATLAB and Python share one code map."""
        return {
            "INPUT_IGNORED": codes.INPUT_IGNORED, "GAME_END": codes.GAME_END,
            "LEVEL_START": codes.LEVEL_START, "LIFE_LOST": codes.LIFE_LOST,
            "GAME_START_BASE": codes.GAME_START_BASE,
            "SESSION_START": codes.SESSION_START, "SESSION_END": codes.SESSION_END,
            "REST_START": codes.REST_START, "REST_END": codes.REST_END,
            "RESTING_EYES_OPEN_PRE": codes.RESTING_EYES_OPEN_PRE,
            "RESTING_EYES_OPEN_POST": codes.RESTING_EYES_OPEN_POST,
            "RESTING_EYES_CLOSED_POST": codes.RESTING_EYES_CLOSED_POST,
            "RESTING_END": codes.RESTING_END,
            "VIDEO_START": codes.VIDEO_START, "VIDEO_END": codes.VIDEO_END,
        }

    @staticmethod
    def grid_overlay(grid_px: int) -> np.ndarray:
        """RGBA grid-line image, grid_px x grid_px x 4. MATLAB: uint8(...)"""
        return display.grid_overlay(int(grid_px))

    @staticmethod
    def look() -> dict[str, Any]:
        """Border colour and width rule, so MATLAB draws the same screen."""
        return {"border_rgb": np.array(display.BORDER_RGB, dtype=np.int32),
                "border_divisor": 50, "border_min_px": 4}

    @staticmethod
    def level_text(levels_completed: int, win_levels: int) -> str:
        return display.level_text(int(levels_completed), int(win_levels))

    @staticmethod
    def input_code(action_id: int) -> int:
        return codes.INPUT[GameAction.from_id(int(action_id))]

    def is_allowed(self, action_id: int) -> bool:
        return self._runner().is_allowed(GameAction.from_id(int(action_id)))

    def apply(self, action_id: int, x: int = -1, y: int = -1) -> dict[str, Any]:
        """action_id: 0 = RESET, 1-7 = ACTION1-7. x, y only for ACTION6 (0-63)."""
        action = GameAction.from_id(int(action_id))
        data = {"x": int(x), "y": int(y)} if action is GameAction.ACTION6 else {}
        return _response_dict(self._runner().apply(action, data))


def serve(port: int, environments_dir: str, recordings_dir: str) -> None:
    """Small JSON server for MATLAB releases older than R2024b."""
    from flask import Flask, jsonify, request

    bridge = Bridge(environments_dir, recordings_dir)
    app = Flask(__name__)

    def to_json(d: dict[str, Any]) -> Any:
        out = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in d.items()}
        return jsonify(out)

    @app.post("/start_game")
    def start_game() -> Any:
        body = request.get_json(force=True)
        return to_json(bridge.start_game(body["game_id"], body.get("seed", 0)))

    @app.post("/is_allowed")
    def is_allowed() -> Any:
        return jsonify({"allowed": bridge.is_allowed(request.get_json(force=True)["action_id"])})

    @app.post("/apply")
    def apply() -> Any:
        body = request.get_json(force=True)
        return to_json(bridge.apply(body["action_id"], body.get("x", -1), body.get("y", -1)))

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app.run(host="127.0.0.1", port=port, threaded=False)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="ARC-AGI-3 bridge server for MATLAB")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--environments-dir", default="environment_files")
    p.add_argument("--recordings-dir", default="data/arc_recordings")
    a = p.parse_args()
    serve(a.port, a.environments_dir, a.recordings_dir)
