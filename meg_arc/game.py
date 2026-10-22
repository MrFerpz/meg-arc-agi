"""Game logic layer: wraps an ARC-AGI-3 environment, no display, no hardware.

It turns one player input into the frames to show and the trigger codes that
go with them. Keep it free of PsychoPy so that tests run headless.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import FrameDataRaw, GameAction, GameState

from . import codes

# Same colours as arc_agi.rendering.COLOR_MAP, as a lookup table (uint8 RGB).
PALETTE = np.array(
    [
        [0xFF, 0xFF, 0xFF], [0xCC, 0xCC, 0xCC], [0x99, 0x99, 0x99], [0x66, 0x66, 0x66],
        [0x33, 0x33, 0x33], [0x00, 0x00, 0x00], [0xE5, 0x3A, 0xA3], [0xFF, 0x7B, 0xCC],
        [0xF9, 0x3C, 0x31], [0x1E, 0x93, 0xFF], [0x88, 0xD8, 0xF1], [0xFF, 0xDC, 0x00],
        [0xFF, 0x85, 0x1B], [0x92, 0x12, 0x31], [0x4F, 0xCC, 0x30], [0xA3, 0x56, 0xD6],
    ],
    dtype=np.uint8,
)


def frame_to_rgb(frame: np.ndarray) -> np.ndarray:
    """64x64 colour indices -> 64x64x3 uint8. Vectorised: about 0.05 ms."""
    return PALETTE[np.clip(frame, 0, 15)]


@dataclass
class Response:
    action: GameAction
    data: dict[str, Any]
    frames: list[np.ndarray]
    state: GameState
    levels_completed: int
    win_levels: int
    onset_codes: list[int] = field(default_factory=list)  # send on first flip
    end_code: Optional[int] = None  # send on last flip, if >1 frame


class GameRunner:
    def __init__(
        self,
        arcade: Arcade,
        game_id: str,
        save_recording: bool = True,
        seed: int = 0,
    ) -> None:
        env = arcade.make(game_id, seed=seed, save_recording=save_recording)
        if env is None:
            raise RuntimeError(f"could not load game {game_id!r}")
        self.env = env
        self.game_id = game_id
        self.default_fps = env.info.default_fps or 5
        obs = env.observation_space
        assert obs is not None
        self.last: FrameDataRaw = obs
        # Last frame on screen. Some steps return no frames (e.g. after GAME_OVER).
        self.last_frame: np.ndarray = obs.frame[-1]

    @property
    def available(self) -> set[GameAction]:
        return set(self.env.action_space)

    @property
    def current_frame(self) -> np.ndarray:
        return self.last_frame

    def is_allowed(self, action: GameAction) -> bool:
        if self.last.state in (GameState.GAME_OVER, GameState.WIN):
            return action is GameAction.RESET
        return action is GameAction.RESET or action in self.available

    def apply(self, action: GameAction, data: Optional[dict[str, Any]] = None) -> Response:
        data = data or {}
        if not self.is_allowed(action):
            raise ValueError(f"{self.game_id}: {action.name} not allowed in state {self.last.state.name}")
        before = self.last
        if action is GameAction.RESET:
            obs = self.env.reset()
        else:
            obs = self.env.step(action, data=data)
        if obs is None:
            raise RuntimeError(f"{self.game_id}: {action.name} returned no frame")
        self.last = obs

        onset = [codes.RESPONSE_ONSET[action]]
        if obs.levels_completed > before.levels_completed:
            onset.append(codes.LEVEL_COMPLETE)
        if obs.state is GameState.GAME_OVER and before.state is not GameState.GAME_OVER:
            onset.append(codes.GAME_OVER)
        if obs.state is GameState.WIN and before.state is not GameState.WIN:
            onset.append(codes.GAME_WIN)

        frames = list(obs.frame) or [self.last_frame]
        self.last_frame = frames[-1]
        return Response(
            action=action,
            data=data,
            frames=frames,
            state=obs.state,
            levels_completed=obs.levels_completed,
            win_levels=obs.win_levels,
            onset_codes=onset,
            end_code=codes.ANIMATION_END if len(frames) > 1 else None,
        )


def make_arcade(environments_dir: str, recordings_dir: str, offline: bool = True) -> Arcade:
    """OFFLINE = no network. Fetch the games first with scripts/fetch_games.py."""
    return Arcade(
        operation_mode=OperationMode.OFFLINE if offline else OperationMode.NORMAL,
        environments_dir=environments_dir,
        recordings_dir=recordings_dir,
        logger=logging.getLogger("arc_agi"),
    )
