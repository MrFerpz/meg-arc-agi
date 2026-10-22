function test_mouse(seconds, wheelMergeMs)
% TEST_MOUSE  Print each mouse button event for some seconds (default 20). Windows only.
%   Press left, right, wheel up and wheel down. Each press must give one PRESS line.
%   The release event of a scroll-button press shows as a "merged" line, with the
%   time since the last event. wheelMergeMs: see arc_mouse_hook (default 1000).
if nargin < 1, seconds = 20; end
if nargin < 2, wheelMergeMs = 1000; end
arc_setup_ptb();
mouse = arc_mouse_hook(wheelMergeMs);
cleaner = onCleanup(@() mouse.stop());
names = {'left', 'right', 'wheel_up', 'wheel_down'};
fprintf('Press the mouse buttons for %d s.\n', seconds);
tEnd = GetSecs + seconds;
tLast = NaN;
while GetSecs < tEnd
    ev = mouse.pollRaw();
    for i = 1:size(ev, 1)
        if ev(i, 6), kind = 'merged'; else, kind = 'PRESS'; end
        fprintf('  %-6s  %-10s  delta=%4d  %7.1f ms after the last event\n', kind, names{ev(i, 1)}, ...
            ev(i, 5), 1000 * (ev(i, 2) - tLast));
        tLast = ev(i, 2);
    end
    WaitSecs(0.01);
end
fprintf('Done.\n');
end
