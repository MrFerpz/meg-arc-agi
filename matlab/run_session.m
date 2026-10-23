% RUN_SESSION  Open this file and press Run to start a MEG session.
%   Change the settings below before each run. See arc_meg_task.m for all options.

participant = 'T02';                  % new ID each run, max 8 letters (the EyeLink file name)
games       = {'ls20', 'tr87', 'vc33'};
eyelink     = true;
triggerMode = 'inpout';               % 'none' to test without the trigger cable
windowed    = false;                  % true = small window, for a desk test
minutesPerGame = 10;                  % a game ends at this limit or when all its levels are won
restSeconds    = 30;                  % rest screen between games, then SPACE starts the next one
eyesOpenPreSeconds    = 120;          % resting state: eyes open before the games (0 = skip)
eyesOpenPostSeconds   = 60;           % resting state: eyes open after the games (0 = skip)
eyesClosedPostSeconds = 60;           % resting state: eyes closed after the games (0 = skip)

arc_meg_task(participant, games, triggerMode=triggerMode, eyelink=eyelink, windowed=windowed, ...
    minutesPerGame=minutesPerGame, restSeconds=restSeconds, eyesOpenPreSeconds=eyesOpenPreSeconds, ...
    eyesOpenPostSeconds=eyesOpenPostSeconds, eyesClosedPostSeconds=eyesClosedPostSeconds)
