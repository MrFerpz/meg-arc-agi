function arc_meg_task(participant, games, opts)
% ARC_MEG_TASK  Play ARC-AGI-3 games in Psychtoolbox and send MEG triggers.
%
%   arc_meg_task('P01', {'ls20', 'tr87', 'g50t', 'wa30'})
%   arc_meg_task('TEST', {'ls20'}, windowed=true, triggerMode='none')
%
%   MATLAB owns the screen, the input and the triggers. Python
%   (meg_arc/bridge.py) only runs the game logic. Every trigger that marks a
%   screen change is sent right after Screen('Flip') returns. A photodiode
%   square in a screen corner is white on those frames.
%
%   Needs: MATLAB R2024b or newer (Python 3.12 support), Psychtoolbox 3,
%   and the repo's Python environment (uv sync). See docs/05-psychtoolbox.md.
%
%   UNTESTED: written without MATLAB or Psychtoolbox at hand. Check every
%   hardware part (trigger output, keys, screen) at the facility first.
%   Replace writeTrigger below with the facility's own trigger function.

arguments
    participant (1,:) char
    games cell = {'ls20', 'ft09', 'vc33'}
    opts.repo (1,:) char = fileparts(fileparts(mfilename('fullpath')))
    opts.minutesPerGame (1,1) double = 10
    opts.restSeconds (1,1) double = 30
    opts.triggerMode (1,:) char {mustBeMember(opts.triggerMode, {'none', 'io64', 'serial'})} = 'none'
    opts.triggerAddress (1,:) char = '378'   % hex LPT address for io64, or 'COM3' for serial
    opts.pulseMs (1,1) double = 10
    opts.gapMs (1,1) double = 5
    opts.eyelink (1,1) logical = false
    opts.windowed (1,1) logical = false
    opts.screen (1,1) double = NaN
    opts.gridPx (1,1) double {mustBeMultipleOf64(opts.gridPx)} = 640   % 640 fits a 1024x768 projector
    opts.photodiodePx (1,1) double = 60
    opts.useMouse (1,1) logical = true
    opts.pythonMode (1,:) char {mustBeMember(opts.pythonMode, {'InProcess', 'OutOfProcess'})} = 'InProcess'
end

% ---- output folder and log -------------------------------------------------
outDir = fullfile(opts.repo, 'data', sprintf('%s_%s', participant, datestr(now, 'yyyymmdd-HHMMSS')));
mkdir(outDir);
logFid = fopen(fullfile(outDir, 'events.tsv'), 'w');
fprintf(logFid, 't\tevent\tcode\tgame_id\tgame_number\taction\tx\ty\tn_frames\tstate\tlevels_completed\tnote\n');
gameId = ''; gameNumber = 0;
logEvent(GetSecs, 'clock_anchor', [], sprintf('unix=%.6f', posixtime(datetime('now', 'TimeZone', 'UTC'))));

% ---- Python game bridge ----------------------------------------------------
bridgeModule = arc_setup_python(opts.repo, opts.pythonMode);
bridge = bridgeModule.Bridge(fullfile(opts.repo, 'environment_files'), fullfile(outDir, 'arc_recordings'));
C = structfun(@double, struct(bridgeModule.Bridge.codes()), 'UniformOutput', false);

% ---- trigger output --------------------------------------------------------
pulseS = opts.pulseMs / 1000;
gapS = opts.gapMs / 1000;
lastLow = -Inf;
switch opts.triggerMode
    case 'none'
        writeTrigger = @(v) [];
    case 'io64'
        % io64 MEX (common on Windows). Ask the facility for their function.
        ioObj = io64;
        assert(io64(ioObj) == 0, 'io64 driver did not start');
        lptAddr = hex2dec(opts.triggerAddress);
        writeTrigger = @(v) io64(ioObj, lptAddr, v);
    case 'serial'
        % USB trigger box on a virtual COM port, via Psychtoolbox IOPort.
        serialHandle = IOPort('OpenSerialPort', opts.triggerAddress, 'BaudRate=115200');
        writeTrigger = @(v) IOPort('Write', serialHandle, uint8(v));
end
writeTrigger(0);

% ---- keys (same as the ARC-AGI-3 web player; map pad buttons here) --------
KbName('UnifyKeyNames');
keyNames = {'w', 'UpArrow', 's', 'DownArrow', 'a', 'LeftArrow', 'd', 'RightArrow', 'space', 'f', 'z', 'r'};
keyActions = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 7, 0];   % 0 = RESET ('r' = operator key)
keyCodes = cellfun(@KbName, keyNames);
escCode = KbName('ESCAPE');
keyList = zeros(1, 256);
keyList([keyCodes, escCode]) = 1;

el = [];        % EyeLink handle, set below if used
prevTex = [];   % last frame texture, closed after the next frame is drawn
edfName = '';
try
    % ---- screen --------------------------------------------------------
    PsychDefaultSetup(2);
    if isnan(opts.screen), opts.screen = max(Screen('Screens')); end
    winRectArg = [];
    if opts.windowed
        winRectArg = [40 40 1064 808];
        % Test runs only (e.g. on a Mac laptop): timing tests fail in a window.
        Screen('Preference', 'SkipSyncTests', 1);
    end
    [win, winRect] = PsychImaging('OpenWindow', opts.screen, 0, winRectArg);
    ifi = Screen('GetFlipInterval', win);
    Screen('TextSize', win, 28);
    dst = CenterRectOnPoint([0 0 opts.gridPx opts.gridPx], winRect(3) / 2, winRect(4) / 2);
    % Look of the web player: grid lines, a border, a level counter (docs/02, 2.5).
    Screen('BlendFunction', win, 'GL_SRC_ALPHA', 'GL_ONE_MINUS_SRC_ALPHA');
    look = struct(bridgeModule.Bridge.look());
    borderRgb = double(look.border_rgb) / 255;
    bw = max(double(look.border_min_px), floor(opts.gridPx / double(look.border_divisor)));
    borderRect = InsetRect(dst, -bw, -bw);
    overlayTex = Screen('MakeTexture', win, uint8(bridgeModule.Bridge.grid_overlay(int32(opts.gridPx))));
    pd = opts.photodiodePx;
    diodeRect = [0, winRect(4) - pd, pd, winRect(4)];   % bottom-left corner
    if opts.pulseMs + opts.gapMs > ifi * 1000
        warning('pulse + gap (%.1f ms) is longer than one frame (%.1f ms)', opts.pulseMs + opts.gapMs, ifi * 1000);
    end
    logEvent(GetSecs, 'display', [], sprintf('ifi_ms=%.4f size=%dx%d', ifi * 1000, winRect(3), winRect(4)));

    KbQueueCreate([], keyList);
    KbQueueStart;
    if ~opts.useMouse, HideCursor(win); end

    % ---- EyeLink (optional) --------------------------------------------
    if opts.eyelink
        el = EyelinkInitDefaults(win);
        if ~EyelinkInit(0), error('EyeLink did not connect'); end
        edfName = [participant(1:min(8, end)) '.edf'];
        Eyelink('Openfile', edfName);
        EyelinkDoTrackerSetup(el);    % calibration and validation
        Eyelink('StartRecording');
    end

    % ---- session ---------------------------------------------------------
    showMessage('Waiting for the MEG operator.\n\nPress SPACE to start.', 0);
    waitForSpace();
    sendTrigger(C.SESSION_START, 'session_start');
    for g = 1:numel(games)
        playGame(games{g}, g);
        if g < numel(games)
            showMessage('Rest.', C.REST_START);
            WaitSecs(opts.restSeconds);
            showMessage('Press SPACE for the next game.', C.REST_END);
            waitForSpace();
        end
    end
    cleanUp('done');
catch err
    cleanUp('aborted');
    if ~strcmp(err.identifier, 'arc:quit'), rethrow(err); end
end

% =========================================================================
    function playGame(id, number)
        gameId = id; gameNumber = number;
        s = struct(bridge.start_game(id));
        fps = double(s.default_fps);
        holdFlips = max(1, round((1 / fps) / ifi));
        frames = uint8(s.frames);
        levelStr = char(bridgeModule.Bridge.level_text(int32(0), s.win_levels));
        drawFrame(squeeze(frames(1, :, :, :)), true, levelStr);
        Screen('Flip', win);
        sendTrigger(C.GAME_START_BASE + number, ['game_start ' id]);
        KbQueueFlush;
        mouseWasDown = false;
        state = string(s.state); levels = double(s.levels_completed);
        limit = GetSecs + opts.minutesPerGame * 60;

        while GetSecs < limit && state ~= "WIN"
            [action, x, y, src, tIn] = readInput();
            if isempty(action), WaitSecs(0.001); continue; end
            % The pad has no reset button: after game over, any input resets.
            % For a reset during a level, the operator presses R (docs/02, 2.6).
            if state == "GAME_OVER" && action ~= 0
                action = 0; x = -1; y = -1; src = [src ' auto_reset'];
            end
            if ~bridge.is_allowed(int32(action)) || (action == 6 && x < 0)
                logEvent(tIn, 'input_ignored', [], src, action, x, y);
                sendTrigger(C.INPUT_IGNORED, 'input_ignored');
                continue
            end
            logEvent(tIn, 'input', [], src, action, x, y);
            sendTrigger(double(bridgeModule.Bridge.input_code(int32(action))), sprintf('action %d', action));

            r = struct(bridge.apply(int32(action), int32(x), int32(y)));
            frames = uint8(r.frames);
            n = double(r.n_frames);
            onsetCodes = double(r.onset_codes);
            endCode = double(r.end_code);
            state = string(r.state); levels = double(r.levels_completed);
            levelStr = char(bridgeModule.Bridge.level_text(r.levels_completed, r.win_levels));

            vbl = 0;
            for i = 1:n
                drawFrame(squeeze(frames(i, :, :, :)), i == 1 || (i == n && endCode > 0), levelStr);
                if i == 1
                    vbl = Screen('Flip', win);
                else
                    vbl = Screen('Flip', win, vbl + (holdFlips - 0.5) * ifi);
                end
                if i == 1
                    for c = onsetCodes, sendTrigger(c, sprintf('frame 1/%d', n)); end
                end
                if i == n && endCode > 0
                    sendTrigger(endCode, sprintf('frame %d/%d', n, n));
                end
            end
            logEvent(vbl, 'response_done', [], '', action, x, y, n, char(state), levels);
            % Inputs made during an animation are dropped (one input = one response).
            KbQueueFlush;
        end

        sendTrigger(C.GAME_END, ['game_end ' id]);
        logEvent(GetSecs, 'game_end', [], '', [], [], [], [], char(state), levels);
        gameId = ''; gameNumber = 0;

        function [action, x, y, src, tIn] = readInput()
            action = []; x = -1; y = -1; src = ''; tIn = NaN;
            [pressed, firstPress] = KbQueueCheck;
            if pressed
                if firstPress(escCode) > 0, error('arc:quit', 'Escape pressed'); end
                hits = find(firstPress(keyCodes) > 0);
                if ~isempty(hits)
                    [tIn, k] = min(firstPress(keyCodes(hits)));
                    action = keyActions(hits(k));
                    src = ['key:' keyNames{hits(k)}];
                    return
                end
            end
            if opts.useMouse
                [mx, my, buttons] = GetMouse(win);
                down = buttons(1);
                if down && ~mouseWasDown
                    tIn = GetSecs;
                    action = 6; src = 'mouse';
                    col = floor((mx - dst(1)) / opts.gridPx * 64);
                    row = floor((my - dst(2)) / opts.gridPx * 64);
                    if col >= 0 && col < 64 && row >= 0 && row < 64
                        x = col; y = row;
                    end
                end
                mouseWasDown = down;
            end
        end
    end

    function drawFrame(rgb, diodeOn, levelStr)
        Screen('FillRect', win, borderRgb, borderRect);
        tex = Screen('MakeTexture', win, rgb);
        % Close the previous frame's texture only now: it was drawn and flipped before.
        if ~isempty(prevTex), Screen('Close', prevTex); end
        prevTex = tex;
        Screen('DrawTexture', win, tex, [], dst, 0, 0);          % filterMode 0 = sharp pixels
        Screen('DrawTexture', win, overlayTex, [], dst, 0, 0);   % grid lines, 20 % opacity
        Screen('TextSize', win, 20);
        b = Screen('TextBounds', win, levelStr);
        Screen('DrawText', win, levelStr, borderRect(3) - b(3), borderRect(2) - b(4) - 8, 0.6);
        Screen('FillRect', win, double(diodeOn), diodeRect);
    end

    function showMessage(txt, code)
        Screen('TextSize', win, 28);
        DrawFormattedText(win, txt, 'center', 'center', 1);
        Screen('FillRect', win, double(code > 0), diodeRect);
        Screen('Flip', win);
        if code > 0, sendTrigger(code, txt(1:min(20, end))); end
    end

    function waitForSpace()
        KbQueueFlush;
        while true
            [pressed, firstPress] = KbQueueCheck;
            if pressed && firstPress(escCode) > 0, error('arc:quit', 'Escape pressed'); end
            if pressed && firstPress(KbName('space')) > 0, return; end
            WaitSecs(0.005);
        end
    end

    function t = sendTrigger(code, label)
        % Fixed pulse width, then at least gapS of 0 before the next code.
        assert(code >= 1 && code <= 255, 'trigger code out of range');
        wait = lastLow + gapS - GetSecs;
        if wait > 0, WaitSecs(wait); end
        writeTrigger(code);
        t = GetSecs;
        if ~isempty(el), Eyelink('Message', 'TRIGGER %d %s', code, label); end
        WaitSecs('UntilTime', t + pulseS);
        writeTrigger(0);
        lastLow = GetSecs;
        logEvent(t, 'trigger', code, label);
    end

    function logEvent(t, event, code, note, action, x, y, n, state, levels)
        if nargin < 5, action = []; end
        if nargin < 6, x = []; end
        if nargin < 7, y = []; end
        if nargin < 8, n = []; end
        if nargin < 9, state = ''; end
        if nargin < 10, levels = []; end
        f = @(v) num2str(v);
        fprintf(logFid, '%.6f\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n', t, event, f(code), gameId, ...
            f(gameNumber(gameNumber > 0)), f(action), f(x(x >= 0)), f(y(y >= 0)), f(n), state, f(levels), note);
    end

    function cleanUp(how)
        % Each step in its own try, so one failure does not skip the rest.
        logEvent(GetSecs, how, [], '');
        try sendTrigger(C.SESSION_END, 'session_end'); catch, end
        try writeTrigger(0); catch, end
        if strcmp(opts.triggerMode, 'serial')
            try IOPort('Close', serialHandle); catch, end
        end
        if ~isempty(el)
            try
                Eyelink('StopRecording');
                Eyelink('CloseFile');
                Eyelink('ReceiveFile', edfName, outDir, 1);
                Eyelink('Shutdown');
            catch e
                warning('EyeLink clean-up failed: %s', e.message);
            end
        end
        fclose(logFid);
        try KbQueueRelease; catch, end
        ShowCursor;
        sca;
    end
end

function mustBeMultipleOf64(v)
% Whole screen pixels per grid square, so every square has the same size.
if mod(v, 64) ~= 0
    error('gridPx must be a multiple of 64 (for example 640 or 768).');
end
end
