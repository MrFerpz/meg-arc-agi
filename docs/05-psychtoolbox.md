# 5. Update: the facility uses Psychtoolbox (MATLAB)

Date: 2026-10-19. The facility replied. This doc changes the plan in docs 0-3. Where they disagree, this doc wins.

## 5.1 What the facility told us

- **Stimuli:** Psychtoolbox in MATLAB. They do **not** mainly use PsychoPy.
- **Analysis:** FieldTrip (MATLAB) for analysis and reports. MNE-Python mainly for source localisation.
- **Interactive tasks:** Unity 3D, also for real-time BCI work.
- **Python:** they say the facility is "fully compatible" with Python workflows. Their examples are all analysis (MNE, NumPy, SciPy, PyTorch). They do not say Python may run on the stimulus PC. **[?] Ask.**

## 5.2 New design

Same idea as before. Only the display program changes: **Psychtoolbox replaces PsychoPy.**

```
 MATLAB + Psychtoolbox  (matlab/arc_meg_task.m)          Python  (meg_arc/bridge.py)
 ┌──────────────────────────────────────────────┐        ┌───────────────────────────┐
 │ reads keys (KbQueue) and mouse               │  call  │ arc-agi Toolkit, OFFLINE  │
 │ asks Python: "action 1 was pressed"  ────────┼──────► │ runs one game step        │
 │                                      ◄───────┼─────── │ returns frames + codes    │
 │ draws frames, Screen('Flip')                 │        └───────────────────────────┘
 │ right after Flip: trigger → MEG (+ EyeLink)  │
 │ photodiode square, events.tsv log            │
 └──────────────────────────────────────────────┘
```

- **MATLAB owns everything that touches time:** the screen, the keys, the triggers, and the eye tracker. This is the facility's own, tested set-up.
- **Python owns only the game logic.** The ARC-AGI-3 games are Python files. Nobody has to rewrite them.
- The trigger codes stay the same (doc 3, table 3.3). MATLAB gets them from Python, so both sides use one code map.

## 5.3 How MATLAB calls Python: two ways

| | A. In-process (recommended) | B. Local HTTP server (fallback) |
|---|---|---|
| How | MATLAB loads Python inside itself (`pyenv`) and calls `py.meg_arc.bridge.Bridge` directly. | A small Python server runs in a second window (`uv run python -m meg_arc.bridge`). MATLAB sends it requests with `webwrite`. |
| MATLAB version | **R2024b or newer.** `arc-agi` needs Python 3.12, and MATLAB supports Python 3.12 from R2024b. ([MathWorks table](https://mathworks.com/support/requirements/python-compatibility.html)) | Any version. |
| Speed | **[I]** Expected about 1 ms per step. Not measured (no MATLAB here). | About 10 ms per call (measured with `curl` on a Mac). JSON decode of long animations in MATLAB may add more. |
| Risk | Python libraries can clash with MATLAB's own libraries in-process. | Two programs to start and stop. |
| Code | `matlab/arc_meg_task.m` uses this. | `meg_arc/bridge.py` has the server. The MATLAB side is not written yet. |

The extra delay of either way does **not** change trigger accuracy. The trigger goes out right after `Screen('Flip')`, and the Python call happens before that. The delay only makes the game feel a few ms slower.

## 5.4 Options we rejected

| Option | Why not |
|---|---|
| Psychtoolbox from Python | **[I]** The Python `psychtoolbox` package has only timing, keyboard, sound and serial-port parts. It has no `Screen`, so it cannot draw. |
| Rewrite the games in MATLAB | 25 games, each with its own rules. Too much work, and the copies could differ from the real games. |
| Rebuild the games in Unity | The facility uses Unity for interactive tasks, but each game would need a rewrite (same problem). A Unity front-end could call the Python bridge over HTTP later, if they prefer Unity. |
| Keep PsychoPy | Still works (`meg_arc/task.py`, tested on a Mac). Keep it as a fallback if the facility agrees to install PsychoPy. They know Psychtoolbox, so Psychtoolbox is the safer choice. |

## 5.5 Psychtoolbox basics (what the MATLAB script uses)

| Psychtoolbox part | What it does in our script |
|---|---|
| `PsychImaging('OpenWindow', ...)` | Opens the full-screen window. |
| `Screen('MakeTexture')`, `Screen('DrawTexture', ..., 0, 0)` | Draws the 64 × 64 grid, then the grid-line overlay (RGBA, 20 % opacity, made once by Python). Filter mode 0 keeps the squares sharp. |
| `Screen('FillRect')`, `Screen('DrawText')` | Draws the border and the `LEVEL n / N` counter (the web-player look, doc 2 section 2.5). |
| `Screen('Flip', win, when)` | Waits for the next screen refresh, shows the new picture, and returns its time. |
| `KbQueueCreate` / `KbQueueCheck` | Reads key presses with the time each key went down. |
| `GetMouse` | Reads the mouse for click games. |
| `GetSecs`, `WaitSecs('UntilTime', t)` | One precise clock for triggers, keys and the log. |
| `IOPort` | Writes to a USB/serial trigger box. |
| `EyelinkInitDefaults`, `EyelinkDoTrackerSetup`, `Eyelink('Message', ...)` | Built-in EyeLink support: connect, calibrate, send trigger messages. |

**Timing facts** ([Screen Flip docs](https://psychtoolbox.org/docs/Screen-Flip), [PTB forum](https://psychtoolbox.discourse.group/t/lptwrite-before-or-after-screen-39-flip-39/1545)):

- `Screen('Flip')` waits for the refresh, then returns. Our script sends the trigger right after it returns.
- Flip returns about the time the refresh starts. Light reaches the eye later.
- One forum user measured about ±5 ms jitter between the trigger and a photodiode on their system. So the photodiode test is still required.

## 5.6 Analysis with FieldTrip or MNE

Both tools read the same `.fif` file and the same STI101 trigger channel.

- **MNE-Python:** `mne.find_events(raw, stim_channel="STI101", mask=0xFF, uint_cast=True)`.
- **FieldTrip:** `ft_read_event` reads the trigger events from the `.fif` file. `ft_definetrial` cuts trials around them. **[?]** Ask how the facility masks out the response-pad bits in FieldTrip.
- Our `events.tsv` uses the `GetSecs` clock, with a `unix=` time stamp in the first row. The Toolkit's own JSONL file keeps every game step.

## 5.7 What was tested, and what was not

**Update 2026-10-19:** `test_bridge` passed in real MATLAB (R2026b trial, macOS, Python 3.12 from the repo `.venv`, in-process). All checks passed. One game step plus conversion to MATLAB arrays: median 1.56 ms, max 7.84 ms (200 steps). It found one bug, now fixed: after GAME_OVER the game returns no frame for a non-RESET action, and the next step crashed. `GameRunner.apply` now refuses actions that are not allowed and always keeps the last frame. The full Psychtoolbox task (`arc_meg_task`) is still not run: Psychtoolbox is not installed on this Mac.


- **Tested:** `meg_arc/bridge.py` in Python (`uv run pytest`, 12 tests pass). The HTTP server answered `start_game` and `apply` with `curl`.
- **Not tested:** `matlab/arc_meg_task.m`. No MATLAB or Psychtoolbox on this Mac. The script follows the documented APIs, but expect small fixes on the first run. Main risks:
  1. `pyenv` with the repo's `.venv` Python. If it fails, point `pyenv` at a normal Python 3.12 install and run `pip install -e .` there.
  2. `uint8()` on a 4-D numpy array (n × 64 × 64 × 3).
  3. The trigger output. Replace `writeTrigger` with the facility's own trigger function.

## 5.8 New questions for the facility

These are now in `docs/04-facility-questions.md`.

1. Which MATLAB version is on the stimulus PC? R2024b or newer lets us use the in-process way.
2. Which Psychtoolbox version?
3. Can we install Python 3.12 (and our package) on the stimulus PC?
4. Can we have a copy of your trigger function (the code that sends a trigger in your Psychtoolbox tasks)?
5. Do you have a Psychtoolbox EyeLink routine you use in the MEG (calibration, file names)?
6. How do you read and mask STI101 events in FieldTrip?

## 5.9 How to test, step by step

| Step | Where | Needs | Checks |
|---|---|---|---|
| 1 | Your Mac, now | Nothing new | `uv run pytest` (game logic, codes, bridge). The PsychoPy version shows the full idea on screen. |
| 2 | Your Mac | MATLAB R2024b or newer. Many universities give a free campus licence. | `test_bridge` in the `matlab/` folder. It checks the MATLAB ↔ Python link, the step speed, and shows a frame. No Psychtoolbox needed. |
| 3 (optional) | Your Mac | Psychtoolbox. Version 3.0.20 and newer need a paid licence on macOS and Windows after a free trial (14 days at the 2025 launch). Linux is free. ([PTB 3.0.21 notes](https://psychtoolbox.org/PTB-3.0.21-Released.html)) | `arc_meg_task('TEST', {'ls20'}, windowed=true)` runs end to end. Mac timing is not reliable in Psychtoolbox, so this checks only that it runs. |
| 4 | Facility stimulus PC | Their MATLAB and Psychtoolbox | Run `test_bridge`. Then `arc_meg_task` with `triggerMode='none'`. Then with their trigger output, the MEG recording and the photodiode. |

`matlab/arc_setup_python.m` holds the Python set-up, so both scripts use the same steps.

### Free ways to get MATLAB and Psychtoolbox for step 2-3 (checked 2026-10-19)

| Option | Cost | Limits | Runs our Psychtoolbox script? |
|---|---|---|---|
| University campus licence | Free for staff and students where the university has one | Ask your university IT. No public Ulster page was found. | Yes (with Psychtoolbox) |
| MATLAB 30-day trial ([mathworks.com/campaigns/products/trials.html](https://www.mathworks.com/campaigns/products/trials.html)) | Free, no payment card | 30 days, desktop and online, latest release (Python 3.12 supported) | Yes (with Psychtoolbox) |
| MATLAB Online (basic) | Free | Up to 20 hours per month, 15 min continuous compute, select products | **[I]** No. Psychtoolbox needs a local screen. Maybe usable for `test_bridge` only (not checked). |
| Psychtoolbox trial ([3.0.21 notes](https://psychtoolbox.org/PTB-3.0.21-Released.html)) | Free trial, then a yearly paid licence on macOS and Windows | 14 days per machine at the March 2025 launch. Price not published in the sources found. | Needed together with MATLAB |
| GNU Octave + Psychtoolbox on Linux | Free | Our script uses MATLAB-only features (`arguments`, `pyenv`, `py.`) | No, not without a rewrite |

Plan: start the MATLAB trial and the Psychtoolbox trial in the same week, close to the visit, because both clocks start at first use.
