# 1. MEG, the Ulster facility, PsychoPy and eye tracking

Legend: **[V]** = a source confirms it. **[I]** = inferred or general practice. **[?]** = unknown, so ask the facility (see doc 4).

## 1.1 MEG in one paragraph

MEG (magnetoencephalography) records the very small magnetic fields that brain activity makes. The sensors sit in a helmet inside a magnetically shielded room (MSR). MEG has millisecond time resolution. So every event in the task must be marked in the MEG data with millisecond accuracy. A **trigger** does this. A trigger is a short 5 V (TTL) pulse that the stimulus PC sends to the MEG trigger input at the moment an event happens.

## 1.2 Ulster facility (Northern Ireland Functional Brain Mapping Facility, ISRC, Magee)

- **[V] System:** Elekta Neuromag (now MEGIN) **TRIUX**, 306 channels (102 magnetometers + 204 planar gradiometers), working since January 2015. Sources: archived ISRC facilities page https://web.archive.org/web/20251114233646/https://www.ulster.ac.uk/research/topic/computer-science/intelligent-systems-research-centre/facilities and https://meguk.ac.uk/?p=145
- **[V] Kit listed:** 128-channel MEG-compatible Brain Products EEG cap, MEG earphones, median-nerve stimulator, "MEG compatible motor or response pads".
- **[V] Stimulus PC:** called "STIM2", outside the MSR. **[I]** It may be Compumedics Neuroscan STIM2 hardware, or only a PC name.
- **[V] Display:** Panasonic PT-DS12KE projector outside the MSR, onto an Elekta screen. The facility claims a visual delay "shorter than 50 ms".
- **[V] Settings from a published Ulster study** (Rathee et al. 2021, Sci Data, https://pmc.ncbi.nlm.nih.gov/articles/PMC8085139): projector 1024×768 at 60 Hz, about 80 cm viewing distance, 1 kHz sampling, 0.1-300 Hz filter, triggers 4/8/16/32 in the STI channels of the .fif file, HEOG/VEOG + ECG, 5 HPI coils with continuous HPI.
- **[?] Eye tracker:** no public source names it. The brief says the facility uses one. EyeLink 1000 Plus is the usual choice at TRIUX sites, but that is not proof.
- **[V] Sampling rate: 1 kHz** (confirmed by the facility contact, 2026-10-19). One sample = 1 ms. So a 10 ms pulse = 10 samples, and a 5 ms gap = 5 samples.
- **[?]** Trigger interface, acquisition software version, PC operating system, PsychoPy version, response-pad model and wiring, pointer device in the MSR, photodiode.

## 1.3 How MEGIN/Elekta TRIUX reads triggers

- **[V]** Lines STI001-STI016 each carry one bit. Pulses are about +5 V, usually 5-10 ms. (Jyväskylä TRIUX page: https://www.jyu.fi/en/cibr/meg-support-pages/hardware/trigger-system)
- **[V]** STI101 is the sum: STI101 = Σ 2^(n-1) over the lines that are high. (Cambridge CBU: https://imaging.mrc-cbu.cam.ac.uk/meg/IdentifyingEventsWithTriggers)
- **[V]** At many sites the **response pads write to the upper bits** (for example STI009-STI016). A button press during a trigger then changes the value (8 + 512 = 520). Bit 16 makes STI101 negative if read as signed.
- **[V]** The software sees a new code only after the line goes back to 0. So **every pulse must return to 0** before the next one.
- **[V]** Read the events in MNE-Python (https://mne.tools/stable/generated/mne.find_events.html):

```python
import mne
raw = mne.io.read_raw_fif("subject_raw.fif")
events = mne.find_events(
    raw, stim_channel="STI101",
    mask=0xFF, mask_type="and",   # keep bits 1-8 = our task codes; drop the button bits
    uint_cast=True,               # fix negative values from bit 16
    shortest_event=2, min_duration=0.002,
)
```

Our codes use bits 1-8 only (values 1-255). **[?]** Ask the facility which bits the response pads use, and confirm 1-255 is free.

## 1.4 PsychoPy triggers

- **[V]** `psychopy.parallel.ParallelPort(address=0x378)`, then `setData(code)` drives pins 2-9 (bits 0-7). Windows needs `inpoutx64.dll` in the experiment folder. (https://www.psychopy.org/api/parallel.html, https://www.psychopy.org/hardware/parallelPortInstr.html)
- **[V]** USB trigger boxes (for example Brain Products TriggerBox) look like a serial port. Write one byte for the code, then write 0. (https://www.psychopy.org/hardware/serialPortInstr.html)
- **[V]** Cedrus StimTracker / c-pod use `pyxid2`. The box sets the pulse width in hardware.
- **[V]** LabJack U3 support is now the `psychopy-labjack` plugin.
- **[V]** `win.callOnFlip(fn, ...)` runs `fn` right after the next screen flip. This ties the trigger to the moment the frame goes to the display.
- **[I]** The PsychoPy Builder pattern "set on flip, clear on next flip" gives a pulse one frame long (16.7 ms at 60 Hz). Our code instead holds the line high for a fixed `--pulse-ms` (default 10 ms), then forces at least `--gap-ms` (default 5 ms) of 0. At 60 Hz, 10 + 5 = 15 ms, which is less than one frame (16.7 ms).
- **[I]** Do not show the game in a web browser. A browser gives no flip time, and its compositor adds delay we cannot measure.

## 1.5 Display delay and the photodiode

- **[V]** The trigger marks when the PC sends the frame, not when light reaches the eye. Measured delays at other sites: 17-18 ms at 60 Hz and 9-10 ms at 120 Hz (CBU, https://imaging.mrc-cbu.cam.ac.uk/meg/StimulusDetails). Another site measured 35.9 ± 0.4 ms (https://www.neuro.mcw.edu/meg/index.php/Designing_your_Experiment).
- **[I]** Measure the delay at Ulster. Our task draws a small square in a screen corner (`--photodiode bl`). The square goes white on each frame that has a trigger, and black on all other frames. Put a photodiode on that corner. Record it into a MEG MISC channel or a spare STI line. The delay = photodiode onset − trigger onset. If the delay is constant, subtract it in analysis.

## 1.6 Eye tracking with MEG

- **[V]** Python: `sr-research-pylink` (PyPI). PsychoPy ioHub support is now the `psychopy-eyetracker-sr-research` plugin. Send `tracker.sendMessage("TRIGGER 12")`. One forum report says f-strings fail in the ioHub `sendMessage`. So build the string first. (https://discourse.psychopy.org/t/no-f-string-allowed-sr-research-eyetracker-sendmessage-function/28351)
- **[V]** Three ways to sync EyeLink with MEG:
  1. **Shared TTL.** Split the trigger cable (DB25 Y-splitter) to the MEG and to the EyeLink Host PC parallel port. The EDF file then has `INPUT` events with the same codes. (https://www.sr-research.com/support/thread-81.html)
  2. **Ethernet message.** `sendMessage()` from the stimulus PC at the same time as the TTL. Simple, but the delay is not measured.
  3. **Analog output.** EyeLink analog card → MEG MISC channels. The MEG samples gaze directly, so the sync is exact. There is a fixed lag of about 7-8 ms (measured at DCCN). Volts → screen pixels needs the scale from the tracker's FINAL.INI. (https://www.fieldtriptoolbox.org/getting_started/eyetracker/eyelink/)
- **[I]** Best practice: use method 1 or 2, plus method 3 as a backup. Our code does method 2 (`--eyelink 100.1.1.1`). Methods 1 and 3 need only cabling, no code.
- **[?]** Tobii: no sign that Ulster uses one.

## 1.7 Lab Streaming Layer (LSL)

- **[V]** LSL puts many streams on one clock, but it cannot remove device delays. Hardware triggers are more exact. No native MEGIN LSL outlet exists.
- **[I]** Use LSL (`--lsl`) only as an extra copy of the codes, for example for a separate eye-tracker PC. Do not use it as the MEG time reference.

## 1.8 Using a mouse or keys inside the MSR

- **[I]** Do not put a normal USB mouse or keyboard in the MSR. They contain metal and electronics that make artefacts.
- **[V]** MEG-safe options: fibre-optic response pads (the facility has some), and fibre-optic trackballs, for example Current Designs / CRS fORP "Trackball 2" (about £2,300, needs a 932-series interface).
- **[I]** Most fibre-optic interfaces send USB key presses (for example "1", "2", "3", "4") to the stimulus PC. Map those keys in `meg_arc/task.py` (`DEFAULT_KEYS`).
- **[I]** Decision: we plan to use only the 4 keyboard-only games (`g50t`, `ls20`, `tr87`, `wa30`). They need 5 buttons: 4 directions and ACTION5. Reset is automatic after game over, or the operator presses R (docs/02, 2.6). Click games need a trackball, or a button-driven cursor (not built yet).
- **[I]** Artefacts: use continuous HPI with MaxFilter/tSSS movement correction. Give the participant an arm rest. Record EOG and ECG.
