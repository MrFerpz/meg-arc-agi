function test_video(seconds, videoFile)
% TEST_VIDEO  Play the start of the session video in a small window (default 10 s).
%   Checks that Psychtoolbox can play the video (it needs GStreamer on Windows).
%   Prints the video's size and frame rate, and how many video frames were
%   skipped. Esc stops early. videoFile default: robots.mp4 in the repo folder.
if nargin < 1, seconds = 10; end
if nargin < 2, videoFile = fullfile(fileparts(fileparts(mfilename('fullpath'))), 'robots.mp4'); end
if ~isfile(videoFile), error('Video file not found: %s', videoFile); end
arc_setup_ptb();
Screen('Preference', 'SkipSyncTests', 1);   % small window: the timing tests fail in a window
win = Screen('OpenWindow', max(Screen('Screens')), 0, [40 40 680 400]);
cleaner = onCleanup(@() sca);
[movie, secs, fps, w, h] = Screen('OpenMovie', win, videoFile);
fprintf('Opened %s: %dx%d, %.2f frames/s, %.1f s long.\n', videoFile, w, h, fps, secs);
winRect = Screen('Rect', win);
scale = min(winRect(3) / w, winRect(4) / h);
rect = CenterRect([0 0 w * scale, h * scale], winRect);
Screen('PlayMovie', movie, 1);
n = 0; pts = [];
tEnd = GetSecs + seconds;
while GetSecs < tEnd
    [tex, t] = Screen('GetMovieImage', win, movie, 1);
    if tex <= 0, break; end
    Screen('DrawTexture', win, tex, [], rect);
    Screen('Flip', win);
    Screen('Close', tex);
    n = n + 1; pts(n) = t; %#ok<AGROW>
    [down, ~, keys] = KbCheck;
    if down && keys(KbName('ESCAPE')), break; end
end
Screen('PlayMovie', movie, 0);
Screen('CloseMovie', movie);
skipped = sum(round(diff(pts) * fps) - 1);
fprintf('Showed %d video frames. Skipped %d frames.\n', n, skipped);
if n == 0
    fprintf('FAIL: no frames came from the video.\n');
else
    fprintf('OK: the video plays.\n');
end
end
