# 6. Stimulus PC set-up (Psychtoolbox version)

Assumes a Windows stimulus PC. Change the paths for Linux or macOS.

## 6.1 What must be on the PC

| Item | Who provides it | Notes |
|---|---|---|
| MATLAB R2024b or newer | Facility | Older MATLAB cannot load Python 3.12. Then the HTTP way is needed (doc 5.3, MATLAB side not written yet). |
| Psychtoolbox 3 | Facility | With their licence. |
| Python 3.12 | You (needs admin rights?) | Ask the facility first. |
| `uv` (Python package tool) | You | Only for set-up. Not used during the experiment. |
| This repo folder | You (USB stick) | See 6.2. |

During the experiment **only MATLAB runs**. MATLAB starts Python inside itself. No internet is needed: the games run from `environment_files\`.

## 6.2 Files to copy

Copy the repo to, for example, `C:\meg-arc-agi\`. You need:

```
meg_arc\              the Python bridge and game logic
matlab\               arc_meg_task.m, arc_setup_python.m, test_bridge.m
environment_files\    the 25 downloaded games
pyproject.toml
uv.lock
```

Do not copy `.venv\` (it is for macOS), `vendor\` or `data\`.

## 6.3 Install (once)

If the PC has internet, in PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
cd C:\meg-arc-agi
uv sync --python 3.12
uv run pytest
```

- `uv sync` makes `C:\meg-arc-agi\.venv\` with Python 3.12 and the `arc-agi` package.
- `uv run pytest` should end with all tests passed.
- If the PC has **no internet**, the packages must come on the USB stick as a "wheelhouse" (pre-downloaded install files). This is not built yet.

## 6.4 Check in MATLAB

```matlab
cd C:\meg-arc-agi\matlab
test_bridge
```

It should print `ALL CHECKS PASSED` and show a picture of the first ls20 level.

If `pyenv` fails to load the `.venv` Python: install Python 3.12 from python.org, then run `uv sync --python "C:\Path\To\Python312\python.exe"` and try again.

## 6.5 Run the task

Test run, small window, no triggers:

```matlab
arc_meg_task('TEST', {'ls20'}, windowed=true, triggerMode='none')
```

Full screen with triggers (example, change it to the facility's hardware):

```matlab
arc_meg_task('P01', {'ls20', 'tr87', 'g50t', 'wa30'}, triggerMode='io64', triggerAddress='378', eyelink=true)
```

- Esc quits. Space starts the session and each next game.
- The output goes to `C:\meg-arc-agi\data\<participant>_<date-time>\`: `events.tsv`, the ARC game recordings, and the EyeLink `.edf` file.
- The facility's own trigger function will probably replace `writeTrigger` in `arc_meg_task.m`.
