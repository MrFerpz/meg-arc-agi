"""Trigger code map for ARC-AGI-3 MEG sessions.

All codes are 8-bit (1-255). 0 is the idle level and is never a code.
Confirm with the facility which STI bits are free before you collect data:
on some MEGIN set-ups the response pads also write to STI101.
"""

from arcengine import GameAction

# Input received (key press / mouse click), sent when the input is read.
INPUT = {
    GameAction.ACTION1: 1,
    GameAction.ACTION2: 2,
    GameAction.ACTION3: 3,
    GameAction.ACTION4: 4,
    GameAction.ACTION5: 5,
    GameAction.ACTION6: 6,
    GameAction.ACTION7: 7,
    GameAction.RESET: 9,
}

# First frame of the game's response is on screen (sent on the screen flip).
RESPONSE_ONSET = {action: code + 10 for action, code in INPUT.items()}

ANIMATION_END = 20  # last frame of a multi-frame response is on screen
LEVEL_COMPLETE = 30
LEVEL_START = 31  # first frame of a level is on screen (game start, next level, RESET)
GAME_OVER = 40
LIFE_LOST = 41  # a game's life counter dropped, or GAME_OVER in a game with one life
GAME_WIN = 50
INPUT_IGNORED = 60  # input not in available_actions, or click off the grid

# Resting-state blocks (sent on the flip of the fixation cross, or of the end screen).
RESTING_EYES_OPEN_PRE = 70  # before the games
RESTING_EYES_OPEN_POST = 71  # after the games
RESTING_EYES_CLOSED_POST = 72  # after the games
RESTING_END = 79

GAME_END = 99
GAME_START_BASE = 100  # trial start: GAME_START_BASE + game number in the session (1-based)

SESSION_START = 250
SESSION_END = 251
REST_START = 252
REST_END = 253


def game_start(game_number: int) -> int:
    code = GAME_START_BASE + game_number
    if not 101 <= code <= 249:
        raise ValueError(f"game_number {game_number} out of range 1-149")
    return code
