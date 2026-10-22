# 4. Questions for Ulster MEG

Send these before the first test session. Each answer changes a setting in the code (shown in brackets).

## Acquisition

1. Which acquisition software and version? Sampling rate is 1 kHz (confirmed). Are STI001-STI016 saved, or only STI101?
2. What is the shortest pulse the acquisition detects? Is 10 ms high + 5 ms low OK? [`--pulse-ms`, `--gap-ms`]

## Triggers

3. How does the stimulus PC send triggers? Parallel port (which address?), USB trigger box (which model, which COM port?), LabJack, Cedrus StimTracker, or Neuroscan STIM2 hardware? [`--trigger`, `--trigger-address`]
4. Which STI bits do the response pads use? Are codes 1-255 (bits 1-8) free for us? Is any line inverted? [`meg_arc/codes.py`]

## Stimulus PC

0. (New, see doc 5.) Which MATLAB and Psychtoolbox versions are on the stimulus PC? MATLAB R2024b or newer lets MATLAB call the Python game directly. Can we install Python 3.12 and our package? Can we have a copy of your Psychtoolbox trigger function?
5. Operating system? Is PsychoPy installed, and which version? Can we install Python 3.12 and our own packages (`uv`)? Does the PC have internet, or must games be copied in? [`scripts/fetch_games.py`]

## Display

6. Projector resolution and refresh rate now (the 2021 study used 1024×768 at 60 Hz)? [`--grid-px`; at 768 px tall, use `--grid-px 640`]
7. Is the visual delay measured? Do you have a photodiode, and can it go into a MISC channel? Which corner is best? [`--photodiode`]

## Eye tracker

8. Which eye tracker (EyeLink 1000 Plus? Tobii?) and its Host PC IP? [`--eyelink`]
9. Does the trigger cable also go to the EyeLink Host PC (Y-splitter)? Is the EyeLink analog output wired to MEG MISC channels?
10. Which calibration routine do you use in Psychtoolbox (EyeLink toolbox)?

## Response devices

11. Which response pads (model, number of buttons)? We need 5 buttons for the 4 keyboard-only games (4 directions, 1 action). Reset is automatic or by the operator. Can the operator hear the participant on the intercom during recording? Which keys do they send to the PC? [`DEFAULT_KEYS` in `meg_arc/task.py`]
12. Is a fibre-optic trackball (for example fORP Trackball 2) available? Only needed if we add click games (ACTION6). Our plan uses keyboard-only games.

## Session

13. How do you read and mask STI101 events in FieldTrip?
13b. Have you run a Psychtoolbox task that calls Python from MATLAB (`pyenv`, `py.`), or that talks to another program (TCP/UDP, LSL, Unity)? Who on your team would help if the Python part fails?
14. Longest recording block you allow? Usual rest and head-position check routine? [`--minutes-per-game`, `--rest-seconds`]
15. Which Psychtoolbox version and licence does the stimulus PC use? Psychtoolbox 3.0.20 and newer must reach the licence server every few days. A PC with no internet needs a special offline ("air gapped") licence (see `PsychLicenseHandling.m`).
