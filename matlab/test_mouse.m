function test_mouse(seconds)
% TEST_MOUSE  Print each mouse button event for some seconds (default 20). Windows only.
%   Press left, right, wheel up and wheel down. Each press must print one line.
if nargin < 1, seconds = 20; end
arc_setup_ptb();
mouse = arc_mouse_hook();
cleaner = onCleanup(@() mouse.stop());
names = {'left', 'right', 'wheel_up', 'wheel_down'};
fprintf('Press the mouse buttons for %d s.\n', seconds);
tEnd = GetSecs + seconds;
while GetSecs < tEnd
    ev = mouse.poll();
    for i = 1:size(ev, 1)
        fprintf('  %-10s  %.1f ms ago  at x=%d y=%d\n', names{ev(i, 1)}, 1000 * (GetSecs - ev(i, 2)), ev(i, 3), ev(i, 4));
    end
    WaitSecs(0.01);
end
fprintf('Done.\n');
end
