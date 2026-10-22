# 3. Integration design: the `meg_arc` package

> **Update (doc 5):** the facility uses Psychtoolbox in MATLAB. The PsychoPy task below (`meg_arc/task.py`) is now the fallback. The codes, timing rules and game logic in this doc still apply to the MATLAB version (`matlab/arc_meg_task.m` + `meg_arc/bridge.py`).

## 3.1 Overview

```
 participant ── response pad / trackball ──► stimulus PC (PsychoPy, Python 3.12)
                                               │
                         meg_arc/task.py  ◄────┤ reads input (keyboard events)
                               │               │
                 meg_arc/game.py (arc-agi, OFFLINE) → frames + codes
                               │
     win.flip() ──callOnFlip──► TriggerSender.pulse(code)
                                   ├─► parallel port / USB trigger box ──► MEG STI001-008 (STI101)
                                   │                                  └─► (Y-splitter) EyeLink Host input
                                   ├─► EyeLink message "TRIGGER <code>"     (optional)
                                   ├─► LSL marker stream                    (optional)
                                   └─► data/<participant>_<time>/events.tsv
     photodiode square on screen ──────────────────────────────────────► MEG MISC channel
```

## 3.2 Files

| File | Job | Needs PsychoPy? |
|---|---|---|
| `meg_arc/codes.py` | Trigger code map (8-bit). | No |
| `meg_arc/triggers.py` | `TriggerSender`: fixed pulse width, forced zero gap, sends to all outputs. Outputs: `NullOutput`, `ParallelPortOutput`, `SerialOutput`. | Only for parallel |
| `meg_arc/game.py` | `GameRunner`: wraps `arc-agi`. Turns one input into frames + codes. Fast colour lookup. | No |
| `meg_arc/display.py` | Mouse position → grid cell. Photodiode position. | No |
| `meg_arc/eventlog.py` | `events.tsv` writer. | No |
| `meg_arc/task.py` | The PsychoPy task: window, input, frame playback, triggers, EyeLink, LSL. | Yes |
| `scripts/fetch_games.py` | Download games for offline use. | No |
| `tests/test_meg_arc.py` | 11 tests. Run `uv run pytest`. | No |

## 3.3 Trigger codes (`meg_arc/codes.py`)

| Code | Event | When it is sent |
|---|---|---|
| 1-7 | Input ACTION1-ACTION7 | When the input is read |
| 9 | Input RESET | When the input is read |
| 11-17 | Response onset for ACTION1-7 | On the flip of the first response frame |
| 19 | Response onset for RESET | Same |
| 20 | Animation end (multi-frame responses only) | On the flip of the last frame |
| 30 | Level complete | On the first response frame (after its 11-19 code) |
| 31 | Level start: the first frame of a level is on screen (game start, next level, RESET) | On the flip of that frame (the last frame of the response) |
| 40 | Game over | On the first response frame |
| 41 | Life lost: the game's life counter dropped (ls20: 3 lives, r11l: 5 hits), or game over in a game with one life | On the first response frame (before 40) |
| 50 | Game win (all levels) | Same |
| 60 | Input ignored (action not available, or click off the grid) | When the input is read |
| 99 | Game end (time limit or win) | At the end of the game |
| 101-249 | Trial start = game start, game number N in the session = 100 + N (then 31) | On the flip of the first frame |
| 250 / 251 | Session start / end | |
| 252 / 253 | Rest start / end | On the flip of the message |

All codes use bits 1-8 only. Change them in one place if the facility needs other values.

## 3.4 Timing rules in the code

1. **Display events are flip-locked.** `Task.flip_with_codes` queues `TriggerSender.pulse` with `win.callOnFlip`. The pulse starts within microseconds of the flip return (smoke test: flip `t` and trigger `t` differ by about 4 µs).
2. **Fixed pulse, forced gap.** `pulse()` holds the code for `pulse_s` (10 ms), then sets 0, and waits until `min_gap_s` (5 ms) of 0 have passed before the next code. So `mne.find_events` always sees separate events. The test `test_pulse_width_and_gap` checks this.
3. **Busy wait, not sleep.** `time.sleep()` can be late by more than 1 ms on Windows, so the code spins on the clock.
4. **One clock.** Triggers, flips and the log all use `psychopy.core.getTime`. The first log row stores `unix=` time for the same moment, so `events.tsv` lines up with the ARC JSONL recording (UTC timestamps).
5. **Animation speed.** Each frame stays for `1/default_fps` s, rounded to whole screen refreshes. `default_fps` is set per game (3-30 fps, see doc 2).
6. **Inputs during an animation are dropped and logged** (`inputs_dropped`). This keeps one input → one response. **[?]** Check if the web player does the same. Change it if the research question needs queued inputs.
7. **Several codes on one frame** (for example 11 then 30) go out one after the other, 15 ms apart. The first code is flip-exact. The second is 15 ms later and the log has its exact time.
8. **Warning** if `pulse + gap` is longer than one refresh. At 60 Hz this does not happen with the defaults. At 120 Hz, use `--pulse-ms 5 --gap-ms 3`.

## 3.5 Output files (one folder per run)

`data/<participant>_<YYYYmmdd-HHMMSS>/`

- `events.tsv`: one row per trigger, input, flip, and game end. Columns: `t, event, code, game_id, game_number, action, x, y, frame_index, n_frames, state, levels_completed, input_t, flip_t, note`.
- `arc_recordings/<scorecard>/<game>-<guid>.jsonl`: the Toolkit's own step-by-step recording with full frames. You can replay the game from it.
- `<participant>.EDF` if EyeLink is on.

## 3.6 What was tested, and what was not

Tested (macOS, Python 3.12, arc-agi 0.9.9, PsychoPy 2026.2.4):

- `uv run pytest`: 11 tests pass. Codes unique and 8-bit. Pulse width and gap. Mouse → cell mapping. Colour lookup equal to the Toolkit. Level-complete and game-over codes on a real game (vc33). Animation-end code on ls20. Log format.
- A windowed smoke run with fake inputs: 2 games, 97 inputs, 203 triggers, `events.tsv` and both ARC recordings written. Input → response-flip delay was about 17-27 ms.

**Not tested (no hardware here):**

- Real parallel port or USB trigger box. (macOS has no parallel port.)
- EyeLink (`connect_eyelink` follows the pylink API but no tracker was connected). Calibration is not in the code. Use the facility's routine, or SR Research's `EyeLinkCoreGraphicsPsychoPy` from their PsychoPy examples.
- LSL outlet.
- PsychToolbox keyboard backend (fails to load on this Mac, so PsychoPy fell back to the `event` module. It should work on Windows).
- Photodiode timing.

## 3.7 Next steps

1. Send the questions in doc 4 to the facility.
2. On the facility stimulus PC: install Python 3.12 + `uv`, copy this repo and `environment_files/`, run `uv sync --extra psychopy`.
3. Set `--trigger` and `--trigger-address` to match their hardware. If they use Cedrus or LabJack, add an output class in `triggers.py` (about 15 lines).
4. Map the response-pad keys in `DEFAULT_KEYS`.
5. Run a test with the photodiode and the MEG recording, no participant. Check:
   - every code in `events.tsv` appears in STI101 (same order, same count),
   - the photodiode delay is constant.
6. Games: we plan to use the 4 keyboard-only games (`g50t`, `ls20`, `tr87`, `wa30`). They need a 5-button pad. Reset is automatic after game over, or the operator presses R. Click games need a trackball (docs/02, 2.6).
