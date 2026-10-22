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


# Games with more than one life: (attribute on the game object, step that means one
# life lost). The names are obfuscated in the game code, so they are per game version.
# ls20: 3 lives per level, one is lost when the energy bar is empty.
# r11l: hidden collision counter, GAME_OVER at 5.
# The other games end at the first loss (GAME_OVER), which counts as LIFE_LOST.
LIFE_COUNTERS: dict[str, tuple[str, int]] = {
    "ls20": ("aqygnziho", -1),
    "r11l": ("yledlprvvkb", +1),
}


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
    end_codes: list[int] = field(default_factory=list)  # send on last flip (same flip if 1 frame)


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
        self.life_counter = LIFE_COUNTERS.get(game_id.split("-")[0])
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

    def lives_value(self) -> Optional[int]:
        """The game's life counter, or None if the game has one life."""
        if self.life_counter is None:
            return None
        game = getattr(self.env, "_game", None)
        value = getattr(game, self.life_counter[0], None)
        if value is None:
            raise RuntimeError(f"{self.game_id}: life counter {self.life_counter[0]!r} not found "
                               "(new game version?). Update LIFE_COUNTERS in meg_arc/game.py.")
        return int(value)

    def is_allowed(self, action: GameAction) -> bool:
        if self.last.state in (GameState.GAME_OVER, GameState.WIN):
            return action is GameAction.RESET
        return action is GameAction.RESET or action in self.available

    def apply(self, action: GameAction, data: Optional[dict[str, Any]] = None) -> Response:
        data = data or {}
        if not self.is_allowed(action):
            raise ValueError(f"{self.game_id}: {action.name} not allowed in state {self.last.state.name}")
        before = self.last
        lives_before = self.lives_value()
        if action is GameAction.RESET:
            obs = self.env.reset()
        else:
            obs = self.env.step(action, data=data)
        if obs is None:
            raise RuntimeError(f"{self.game_id}: {action.name} returned no frame")
        self.last = obs

        level_complete = obs.levels_completed > before.levels_completed
        game_over = obs.state is GameState.GAME_OVER and before.state is not GameState.GAME_OVER
        life_lost = game_over
        if lives_before is not None:
            step = self.life_counter[1]
            life_lost = life_lost or (self.lives_value() - lives_before) * step > 0

        onset = [codes.RESPONSE_ONSET[action]]
        if level_complete:
            onset.append(codes.LEVEL_COMPLETE)
        if life_lost:
            onset.append(codes.LIFE_LOST)
        if game_over:
            onset.append(codes.GAME_OVER)
        if obs.state is GameState.WIN and before.state is not GameState.WIN:
            onset.append(codes.GAME_WIN)

        frames = list(obs.frame) or [self.last_frame]
        end = [codes.ANIMATION_END] if len(frames) > 1 else []
        # The engine draws the next level on the last frame of the response.
        if (level_complete or action is GameAction.RESET) and obs.state is not GameState.WIN:
            end.append(codes.LEVEL_START)
        self.last_frame = frames[-1]
        return Response(
            action=action,
            data=data,
            frames=frames,
            state=obs.state,
            levels_completed=obs.levels_completed,
            win_levels=obs.win_levels,
            onset_codes=onset,
            end_codes=end,
        )


def make_arcade(environments_dir: str, recordings_dir: str, offline: bool = True) -> Arcade:
    """OFFLINE = no network. Fetch the games first with scripts/fetch_games.py."""
    return Arcade(
        operation_mode=OperationMode.OFFLINE if offline else OperationMode.NORMAL,
        environments_dir=environments_dir,
        recordings_dir=recordings_dir,
        logger=logging.getLogger("arc_agi"),
    )
