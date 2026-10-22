# meg-arc-agi

Play ARC-AGI-3 games in an MEG scanner (Ulster MEG, Elekta/MEGIN TRIUX) with Psychtoolbox (MATLAB) or PsychoPy, and send a trigger to the MEG (and eye tracker) for every game event.

## Docs

0. [Primer: start here (no background needed)](docs/00-primer.md)
1. [MEG, the Ulster facility, PsychoPy, eye tracking](docs/01-meg-facility.md)
2. [ARC-AGI-3 code: what it is and where to hook in](docs/02-arc-agi-3-code.md)
3. [Integration design: the `meg_arc` package](docs/03-integration-design.md)
4. [Questions for Ulster MEG](docs/04-facility-questions.md)
5. [Update: the facility uses Psychtoolbox (MATLAB)](docs/05-psychtoolbox.md). **Read this first: it changes the display part of docs 0-3.**
6. [Stimulus PC set-up (Psychtoolbox version)](docs/06-stimulus-pc-setup.md)

**Short answer:** do not edit the ARC-AGI code. Use the `arc-agi` package as a library for the game logic. A Psychtoolbox (MATLAB) script (`matlab/arc_meg_task.m`) shows the frames and sends triggers right after each screen flip. It calls Python through `meg_arc/bridge.py`. The PsychoPy version (`meg_arc/task.py`) is a fallback.

## Quick start

Needs Python 3.12 (`arc-agi` needs >=3.12, PsychoPy needs <3.13) and `uv`.

```bash
uv sync --extra psychopy
uv run python scripts/fetch_games.py        # once, with internet
uv run pytest                               # 12 tests, no hardware needed
uv run --extra psychopy python -m meg_arc.task --participant TEST --games ls20 --windowed --trigger none
```

In the scanner (example, change to the facility's hardware):

```bash
uv run --extra psychopy python -m meg_arc.task --participant P01 \
    --games ls20 tr87 g50t wa30 --minutes-per-game 10 \
    --trigger parallel --trigger-address 0x378 \
    --eyelink 100.1.1.1 --photodiode bl --grid-px 640
```

Psychtoolbox version (MATLAB R2024b or newer, untested):

```matlab
arc_meg_task('TEST', {'ls20'}, windowed=true, triggerMode='none')   % run from the matlab/ folder
```

Keys: W/A/S/D or arrows = ACTION1-4, Space/F = ACTION5, Z = ACTION7, R = reset, mouse click = ACTION6, Esc = quit.

`vendor/` holds read-only clones of the arcprize repos for reference (git-ignored).
