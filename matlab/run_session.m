% RUN_SESSION  Open this file and press Run to start a MEG session.
%   Change the settings below before each run. See arc_meg_task.m for all options.

participant = 'T02';                  % new ID each run, max 8 letters (the EyeLink file name)
games       = {'ls20', 'tr87', 'vc33'};
eyelink     = true;
triggerMode = 'inpout';               % 'none' to test without the trigger cable
windowed    = false;                  % true = small window, for a desk test

arc_meg_task(participant, games, triggerMode=triggerMode, eyelink=eyelink, windowed=windowed)
