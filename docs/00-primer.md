# 0. Primer: start here

This guide assumes you know nothing about MEG, Psychtoolbox, or eye tracking.

> **Update:** the facility uses Psychtoolbox in MATLAB, not PsychoPy. This primer now follows that plan. Details: `docs/05-psychtoolbox.md`.
Part A explains the system we propose, and why we chose it.
Part B lists what you need to learn before the visit to Ulster MEG.
A glossary and a checklist for the visit are at the end.

---

# Part A: The proposed system

## A1. The problem in one picture

The MEG records the brain all the time. At Ulster it takes **1000 measurements per second** (1 kHz). So it takes one measurement every 1 ms. Each measurement is a **sample**.

The MEG does not know what the participant sees or does. It only records the brain.

So we must put a **mark** into the recording at the exact sample when something happens. Examples: "the participant pressed UP" or "the game showed a new picture". This mark is a **trigger**.

Later, in analysis, you find every mark. Then you cut out the brain data around it, for example from 200 ms before to 800 ms after. Then you average many of these pieces. If a mark is 20 ms late, the brain response looks 20 ms late, which gives a wrong result.

So the main job is: **send each trigger at the exact moment the event happens.**

## A2. The pieces of equipment

```
  SHIELDED ROOM (MSR)                          CONTROL ROOM (outside)
 ┌──────────────────────────────┐            ┌──────────────────────────────────┐
 │  participant, head in helmet │            │  STIMULUS PC  (runs our program) │
 │                              │  light     │     │                            │
 │  screen  ◄───────────────────┼────────────┼── projector                      │
 │                              │            │     │ trigger cable (TTL)        │
 │  response pad (fibre optic) ─┼────────────┼──►  │                            │
 │                              │            │     ▼                            │
 │  eye-tracker camera ─────────┼────────────┼──► EYE-TRACKER PC                │
 │                              │            │                                  │
 │  MEG sensors (helmet) ───────┼────────────┼──► MEG ACQUISITION PC            │
 └──────────────────────────────┘            │     records brain + trigger lines│
                                             └──────────────────────────────────┘
```

- **Stimulus PC.** This PC runs the game. It draws the picture and reads the buttons. It sends the triggers.
- **Projector.** It sits outside the shielded room. It shines the picture through a hole onto a screen in front of the participant. Its electronics would make magnetic noise inside the room, so it stays outside.
- **Response pad.** The participant presses buttons on it. It uses light in glass fibres, not wires, so it makes no magnetic noise.
- **MEG acquisition PC.** This PC records the brain. It also records the **trigger lines** (the STI channels) next to the brain data, sample by sample.
- **Eye-tracker PC.** This PC records where the eyes look.

## A3. What ARC-AGI-3 is

- ARC-AGI-3 is a set of small puzzle games. Each game shows a 64 × 64 grid of coloured squares.
- The player does not get instructions. The player must find the rules by trying things.
- Each game is one small Python file.
- The ARC Prize team made a Python package called **`arc-agi`** (the "Toolkit"). It loads a game. Your code tells it "press UP". It gives back the new picture as numbers.
- The Toolkit was made for **AI programs** that play the games. It does not have a proper player for humans.
- Humans play on the ARC Prize website (three.arcprize.org). That web player is not public code.

## A4. The three options we looked at

### Option 1: Use the website in a browser. Rejected.

- We cannot change the website code, so we cannot add triggers to it.
- A browser does not tell us when a picture reaches the screen. The delay changes from moment to moment.
- It needs internet in the lab.

### Option 2: Change the ARC-AGI code and put the triggers inside it. Rejected.

- The Toolkit calculates the new picture. It does not put the picture on the screen.
- A trigger inside the Toolkit would go out **before** the picture is visible. The gap would be 0 to 17 ms and different each time.
- The Toolkit's own display is slow (about 15 ms to draw one picture). It also cannot read keys or the mouse.
- If we change the package, each ARC-AGI update would remove or break our changes.

### Option 3: Use ARC-AGI as a library, plus a Psychtoolbox program in MATLAB. Chosen.

- A **library** is code that you use but do not change. You call it like a tool.
- The games stay in Python. Python does only the game logic: "this button was pressed, what is the new picture?"
- The facility runs its tasks in **Psychtoolbox**, a free toolbox for experiments in MATLAB. So MATLAB does everything that touches time: it draws the picture, reads the buttons, and sends the triggers.
- MATLAB can call Python code directly (MATLAB R2024b or newer). So on each button press, MATLAB asks Python for the new picture.
- `Screen('Flip')` in Psychtoolbox shows the picture at the next screen refresh. Our script sends the trigger right after it.
- So the program that knows the time is also the program that sends the trigger.

The first plan used **PsychoPy**, a similar tool in Python. The idea is the same. The PsychoPy version stays as a backup.

## A5. What happens on one button press

A screen does not change smoothly. It redraws the full picture at fixed times. At 60 Hz it redraws every 16.7 ms. Each redraw is a **refresh**. A "flip" means "show the next picture at the next refresh". In Psychtoolbox the command is `Screen('Flip')`.

Example timeline:

| Time | What happens | Trigger sent |
|---|---|---|
| 0 ms | The participant presses UP on the pad. | |
| about 1-5 ms (unknown, must measure) | The stimulus PC receives the key. | **1** ("input: ACTION1") |
| + about 1 ms (expected, must measure) | MATLAB asks the Python game for the new picture. | |
| next refresh (0-17 ms later) | The new picture goes to the projector. | **11** ("response shown for ACTION1") |
| same moment | A small square in a screen corner turns white. | |
| about 17-50 ms later (unknown, must measure) | Light from the projector reaches the screen. A **photodiode** on the corner square sees it. | photodiode signal goes into the MEG |
| if the player solved a level | | **30** ("level complete") |

- The trigger is a short electrical pulse: the line goes to 5 V for 10 ms, then back to 0 V.
- At 1 kHz, 10 ms = **10 samples**. That is plenty: MNE-Python needs at least 2 samples.
- After each pulse, the line stays at 0 V for at least 5 ms (5 samples). The MEG can only see a new code after the line goes back to 0.
- Our program also writes every trigger into a log file (`events.tsv`) with its exact time. The Toolkit writes its own file with every game step. So you can rebuild the full game later.

## A6. Why the photodiode matters

- The trigger marks when the PC **sends** the picture. The eye sees it later, because the projector needs time to show it.
- A **photodiode** is a small light sensor. We tape it on the screen over the corner square. Its signal goes into a spare MEG channel.
- **Delay** = photodiode time − trigger time.
- If the delay is the same every time (for example always 32 ms), you subtract it in analysis. No problem.
- If the delay changes (for example 20-45 ms), that is **jitter**. Jitter blurs the brain responses. The photodiode signal is then the true time to use.

## A7. Summary in 5 lines

1. ARC-AGI gives us the game logic. We do not change it.
2. Psychtoolbox (MATLAB) draws the game and reads the buttons. It asks Python for each new picture.
3. At each screen change, MATLAB sends a trigger code to the MEG (and the eye tracker).
4. A photodiode measures the real delay of the projector.
5. A log file keeps every event, so we can rebuild the game later.

---

# Part B: What to learn before the visit

The items are in order. Spend the most time on B1, B2 and B3.

## B1. MEG basics

### What MEG measures

- Brain cells (neurons) send small electrical currents. Many thousands of neurons fire together. Their currents make a very small magnetic field outside the head.
- This field is very weak. The Earth's magnetic field is hundreds of millions of times stronger. A passing car or a lift also makes a much larger field.
- So the MEG needs two things:
  - **Very sensitive sensors.** They are called **SQUIDs**. They work only when very cold, so they sit in liquid helium (about −269 °C) inside the helmet. The helmet is the large white device the head goes into.
  - **A shielded room (MSR).** Its walls are made of special metal that blocks magnetic noise from outside.
- Ulster has an **Elekta Neuromag TRIUX** (the company is now named MEGIN). It has **306 sensors**:
  - 102 **magnetometers**. Each measures the field at one point.
  - 204 **planar gradiometers**. Each measures how the field changes across a small distance. They see sources close to them better, and ignore far noise better.

### Why MEG is good for this project

- **Time:** MEG sees changes within milliseconds. fMRI (brain scanning with MRI) sees changes only over seconds.
- **Place:** MEG shows roughly where the activity is. It is less exact than fMRI.
- **Quiet and safe:** nothing goes into the body, and nothing is noisy.

### What goes wrong in MEG (artefacts)

An **artefact** is a signal in the recording that does not come from the brain.

- **Metal on the body.** Zips, bra wires, hair clips, some make-up, tattoos with metal ink, dental work. Metal makes very large noise. Participants change into metal-free clothes. The facility checks this ("screening").
- **Eye blinks and eye movements.** The eye acts like a small battery. Each movement makes a large signal at the front of the head. ARC-AGI-3 needs a lot of looking around, so expect many eye artefacts. **EOG** electrodes around the eyes record them, so analysis can remove them later.
- **Heartbeat.** **ECG** electrodes record it, for the same reason.
- **Muscles.** Jaw, neck, and arm movement. Pressing buttons is fine. Large arm movement is not.
- **Head movement.** If the head moves in the helmet, the sensors see the brain from a new place. **HPI coils** fix this (see below).

### What happens to the participant before the recording (about 30-45 min, ask the facility)

1. Screening for metal, and a change into metal-free clothes.
2. Small coils (**HPI coils**) are taped to the head. Ulster uses 5. During the recording they send a weak signal, so the system always knows where the head is. This is "continuous HPI".
3. A pen-like tracker (**Polhemus digitiser**) records the shape of the head and the coil positions. This later helps to match the MEG to a brain model or MRI scan.
4. EOG and ECG electrodes go on the face and chest.
5. The participant sits in the MEG chair, head in the helmet. The staff close the door. You talk over an intercom and watch on a camera.

### Words you will hear

- **.fif file.** The file type the MEGIN system saves.
- **MaxFilter / tSSS.** MEGIN software that removes outside noise and corrects for head movement. It runs after the recording.
- **Sampling rate.** Samples per second. Ulster: 1000 Hz (1 kHz). One sample every 1 ms.
- **Filter (online).** The recording keeps only certain frequencies. The 2021 Ulster study kept 0.1-300 Hz.
- **Empty-room recording.** A short recording with nobody in the room, to measure the noise.

## B2. Triggers (most important for the build)

### Bits and codes

- A trigger cable has **8 data wires** (more on some systems). Each wire is either at 0 V (off) or 5 V (on). Each wire is one **bit**.
- 8 bits together give one number from 0 to 255. Example: code **11** in binary is `00001011`. So wires 1, 2 and 4 are on.

| Wire (bit) | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|---|---|
| Value | 128 | 64 | 32 | 16 | 8 | 4 | 2 | 1 |
| Code 11 | 0 | 0 | 0 | 0 | **1** | 0 | **1** | **1** |

  8 + 2 + 1 = 11.
- **0 means "nothing"**, so 0 can never be a code.
- **TTL** is the name of this 0 V / 5 V signal.

### How the MEGIN system records triggers

- Each wire becomes one channel in the recording: **STI001**, **STI002**, ... up to **STI016**.
- One more channel, **STI101**, holds the total number. If wires 1, 2 and 4 are on, STI101 = 11.
- **The response pad may also use some of these wires**, often the upper ones (STI009-STI016). If the participant presses a button during our trigger, STI101 shows our code plus the button's value. For example 11 + 512 = 523. In analysis, a **mask** keeps only wires 1-8 (`mask=0xFF`). We must ask which wires the pad uses.
- If the pad writes to STI channels, then **the MEG has the exact time of each button press**. That is better than our "input" trigger, because our trigger goes out only after the PC receives the key.

### How the stimulus PC sends triggers

The common ways are:
- **Parallel port.** An old 25-pin printer socket. PsychoPy sets its pins directly. It has very little delay. Many labs still use it. It needs an "address", for example `0x378`.
- **USB trigger box.** A small box with USB in and a trigger socket out. The PC writes one byte to it.
- **Other boxes:** Cedrus StimTracker, LabJack, or (maybe) Neuroscan STIM2 hardware. Ulster calls its stimulus PC "STIM2". We do not know if that is only a name.

Our code supports a parallel port and a USB serial box. Other boxes need about 15 more lines of code.

### Rules

1. Send each code as a pulse: on, wait 10 ms, off.
2. Keep at least 5 ms of 0 between codes.
3. Never use 0 as a code.
4. Use codes that the response pad does not use.

## B3. Timing and the screen

- **Refresh rate.** How often the screen redraws. Ulster's projector ran at 60 Hz in the 2021 study, so 16.7 ms per picture. A change can show only at the next refresh.
- **Vsync / flip.** PsychoPy waits for the refresh, then shows the new picture. Only at that moment do we know the picture went out. That is why triggers go on the flip.
- **Delay vs jitter:**
  - **Delay**: always the same lateness. You can subtract it. No problem.
  - **Jitter**: random lateness. You cannot remove it. It blurs the data. Avoid it.
- **Projector delay.** Other MEG sites measured 17 to 36 ms. Ulster says "less than 50 ms". The photodiode test measures the real number.
- **Dropped frames.** If the PC is too slow, it misses a refresh. Our program logs flip times, so we can see if this happens.

## B4. Eye tracking

### How it works

- The usual system is an **EyeLink** (by SR Research). We do not know if Ulster has one. Ask.
- An infrared camera films the eye. Infrared light is invisible to the participant. Software finds the **pupil** and a small **reflection** on the front of the eye. From those two it calculates where the eye looks.
- It can sample up to 1000 times per second or more.
- In the MEG room the camera sits on a stand, away from the helmet. It must not touch the helmet.
- Before recording, the participant does a **calibration**: they look at dots in known places on the screen. The tracker learns how eye position maps to screen position. Each recording block needs a quick check, and a new calibration if the head moved.
- The eye-tracker PC (the "Host PC") saves an **EDF** file.

### Why it is useful for ARC-AGI-3

- It shows which part of the grid the player looks at, and when. This can show their strategy.
- It helps to find and remove eye artefacts in the MEG data.

### How to line up eye data with MEG data

| Method | How | Good | Bad |
|---|---|---|---|
| Shared trigger cable | A Y-splitter sends the same trigger to the MEG and to the eye-tracker PC. | Same code, same moment in both files. | Needs the cable. |
| Network message | Our program sends "TRIGGER 11" to the eye tracker over the network at the same time. | Only code. Our program does this already (`--eyelink`). | Small unknown network delay. |
| Analog output | The eye tracker sends gaze as a voltage into spare MEG channels. | The MEG records the gaze itself. Sync is exact. | Fixed delay of about 7-8 ms. Needs scaling. |

Best practice: use two methods, so one can back up the other.

## B5. Psychtoolbox and MATLAB

- **MATLAB** is a paid programming tool, common in neuroscience labs. Ulster uses it for most of its tasks and analysis.
- **Psychtoolbox** is a free add-on for MATLAB. It shows pictures with exact timing and reads keys with exact times.
- Our script is `matlab/arc_meg_task.m`. It calls the Python game through `meg_arc/bridge.py`.
- The key parts we use:
  - `PsychImaging('OpenWindow')`: the full-screen window.
  - `Screen('DrawTexture')`: draws the 64 × 64 grid with sharp squares.
  - `Screen('Flip')`: shows the new picture at the next refresh and returns its time.
  - `KbQueueCheck`: reads keys with the time each key went down.
  - `GetSecs`, `WaitSecs`: one precise clock.
  - `Eyelink('Message')`: sends each trigger code to the eye tracker too.
- Version note: the games need Python 3.12. MATLAB can call Python 3.12 from **R2024b**. With an older MATLAB, Python runs as a small separate server. That way is slower.
- The MATLAB script is not tested yet (no MATLAB here). Expect small fixes on the first run.
- The facility also uses Unity 3D for interactive tasks. Each game would need a rewrite for Unity, so we do not plan to use it.

## B6. Response devices

- No normal keyboard or mouse in the shielded room. They contain metal and electronics.
- **Fibre-optic response pads** are safe. Ulster has some. They usually send a normal key press (for example "1", "2", "3", "4") to the stimulus PC. We change our key map to match.
- ARC-AGI-3 games use up to 7 actions plus reset. Some games need a **click** on a grid square:
  - We plan to use only the 4 keyboard-only games: `g50t`, `ls20`, `tr87`, `wa30`. They need 5 buttons: 4 directions and 1 action button. After game over, any button restarts the level. For a restart during a level, the operator presses R.
  - Click games need a MEG-safe **trackball** (for example the fORP Trackball 2, about £2,300). Or we build a cursor that moves with buttons.
- Game order and time per game are still research decisions. The hardware limits the choice.

## B7. Thinking about the experiment design

This is not code, but the visit will raise these questions:

- **Self-paced task.** ARC-AGI-3 has no fixed trials. The player acts when ready. So "trials" are events: each button press, each screen change, each level solved.
- **What to compare.** Examples: brain activity before a press that solves a level vs before a press that does not. Or early in a game (exploring) vs late (rule known). Decide this early. It decides which triggers matter most.
- **Enough events.** Brain responses are small. You usually need 50-100 or more events of each kind to average.
- **Session length.** Long recordings tire the participant, and the head moves. MEG sessions often use blocks of about 10 minutes with rests. Ask the facility for their limit.
- **Baseline.** Analysis compares activity to a quiet time. In a self-paced game there is no clear quiet time. Some designs add a short fixed pause, or a fixation cross, between games.
- **Pilot first.** Run yourself or a colleague before real participants.
- **Ethics and data.** You need ethics approval for human participants. The facility will ask about consent forms, screening forms, and data storage. Ask who owns the data and how you take it away.

## B8. Analysis in one page (so you know what the data must contain)

Ulster uses **FieldTrip** (MATLAB) for most analysis and **MNE-Python** for source localisation. The steps are the same in both.

1. Load the `.fif` file.
2. Run MaxFilter / tSSS to remove noise and correct head movement.
3. Find the triggers in STI101. MNE: `mne.find_events(raw, stim_channel="STI101", mask=0xFF, uint_cast=True)`. FieldTrip: `ft_read_event`, then `ft_definetrial`.
4. Correct each display trigger with the photodiode delay.
5. Remove eye and heart artefacts (for example with ICA, a method that separates mixed signals).
6. Cut "epochs" around each event, for example −200 to +800 ms.
7. Average epochs of the same kind. Compare kinds.
8. Join with `events.tsv` and the ARC game file to label each event (which level, which action, solved or not).

So the data must contain: clean triggers, the photodiode channel, EOG and ECG, head position (HPI), the head shape (digitiser), and our log files.

---

# Glossary

| Word | Meaning |
|---|---|
| Artefact | A signal in the data that does not come from the brain. |
| Bit | One wire, on or off. 8 bits make a code from 0 to 255. |
| Calibration (eye) | The participant looks at dots so the tracker learns where they look. |
| ECG | Heart signal electrodes. |
| EDF | The eye-tracker data file. |
| EOG | Eye movement electrodes. |
| Epoch | A cut piece of data around one event. |
| .fif | The MEGIN data file. |
| FieldTrip | Free MATLAB toolbox for MEG analysis. Ulster uses it. |
| Flip | Show the next picture at the next screen refresh. In Psychtoolbox: `Screen('Flip')`. |
| Gradiometer | MEG sensor that measures field change across a short distance. |
| HPI coils | Small coils on the head that show head position. |
| Jitter | Random timing error. Bad. Cannot be removed. |
| Library | Code you use without changing it. |
| Magnetometer | MEG sensor that measures the field at one point. |
| MaxFilter / tSSS | MEGIN noise removal and head-movement correction. |
| MNE-Python | Free Python software for MEG analysis. |
| MSR | Magnetically shielded room. |
| Parallel port | 25-pin socket. Sends 8-bit triggers with almost no delay. |
| Photodiode | Light sensor on the screen. Measures when the picture really appears. |
| Polhemus / digitiser | Pen tracker that records head shape. |
| PsychoPy | Free Python software to run experiments. Our backup option. |
| Psychtoolbox | Free MATLAB toolbox to run experiments with exact timing. Ulster uses it. |
| Refresh rate | How often the screen redraws (60 Hz = every 16.7 ms). |
| Sample | One measurement. At 1 kHz, one every 1 ms. |
| SQUID | The very sensitive, very cold MEG sensor. |
| STI001-STI016 | MEG channels that record each trigger wire. |
| STI101 | MEG channel with the total trigger code. |
| Stimulus PC | The PC that runs the task. |
| Toolkit (`arc-agi`) | The ARC Prize Python package that runs the games. |
| Trigger | A short pulse that marks an event in the recording. |
| TTL | The 0 V / 5 V signal that triggers use. |

---

# Checklist for the visit

## Bring

- [ ] Laptop with this repo, working (`uv run pytest` passes).
- [ ] USB stick with: this repo, `environment_files/` (the games), a Python 3.12 installer, and `uv`. The stimulus PC may have no internet.
- [ ] The questions in `docs/04-facility-questions.md`, printed.
- [ ] Your list of research questions (B7). It decides the games and the triggers.

## Do on the day

1. Look at the stimulus PC. Note the operating system, the MATLAB and Psychtoolbox versions, and how the trigger cable connects. Ask if you can install Python 3.12.
1. Ask for a copy of their Psychtoolbox trigger function and their EyeLink routine.
2. Ask for the STI wire map. Write down which wires the response pad uses.
3. Ask to see the response pads. Press each button. Note which key each one sends.
4. Ask about the eye tracker: model, calibration routine, and whether the trigger cable also goes to it.
5. If they allow it, install the program and run a test with the MEG recording on and nobody in the room:
   - Send each code once. Check that STI101 shows the same codes in the same order.
   - Tape a photodiode on the corner square. Measure the delay over at least 50 screen changes. Check if the delay is constant.
6. Agree on the next steps: who changes what, and the date of the first pilot.
