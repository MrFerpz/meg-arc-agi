function test_bridge()
% TEST_BRIDGE  Check the MATLAB <-> Python link. No Psychtoolbox needed.
%
%   Run from the matlab/ folder:   test_bridge
%   Needs MATLAB R2024b or newer, and `uv sync` run once in the repo.

repo = fileparts(fileparts(mfilename('fullpath')));
fprintf('MATLAB %s\n', version);
mod = arc_setup_python(repo);
pe = pyenv;
fprintf('Python %s at %s\n', pe.Version, pe.Executable);

bridge = mod.Bridge(fullfile(repo, 'environment_files'), fullfile(tempdir, 'arc_test_recordings'));

% 1. Start a game and convert the first frame.
s = struct(bridge.start_game('ls20'));
frames = uint8(s.frames);
check(isequal(size(frames), [1 64 64 3]), 'start_game frames are 1x64x64x3 uint8');
check(isequal(double(s.available_actions), [1 2 3 4]), 'ls20 actions are 1-4');
check(double(s.default_fps) > 0, 'default_fps is set');

% 2. One action: codes and frames come back.
check(bridge.is_allowed(int32(1)) && ~bridge.is_allowed(int32(6)), 'is_allowed works');
r = struct(bridge.apply(int32(1), int32(-1), int32(-1)));
codes = double(r.onset_codes);
check(codes(1) == 11, 'ACTION1 response code is 11');
check(size(uint8(r.frames), 1) == double(r.n_frames), 'n_frames matches frames');
check(double(mod.Bridge.input_code(int32(0))) == 9, 'RESET input code is 9');
C = structfun(@double, struct(mod.Bridge.codes()), 'UniformOutput', false);
check(C.GAME_END == 99, 'code map loads');

% 3. A click game.
bridge.start_game('vc33');
r = struct(bridge.apply(int32(6), int32(10), int32(20)));
codes = double(r.onset_codes);
check(codes(1) == 16, 'ACTION6 response code is 16');

% 3b. Screen look helpers (grid lines, border, level counter).
ov = uint8(mod.Bridge.grid_overlay(int32(640)));
check(isequal(size(ov), [640 640 4]), 'grid overlay is 640x640x4 uint8');
check(ov(6, 11, 4) == 51 && ov(6, 6, 4) == 0, 'grid line alpha is 51 (20 %) on lines only');
check(strcmp(char(mod.Bridge.level_text(int32(0), int32(7))), 'LEVEL 1 / 7'), 'level text');

% 4. Speed of one game step, including the frame conversion.
bridge.start_game('ls20');
n = 200; t = zeros(1, n);
for i = 1:n
    tic;
    a = mod_action(i);
    if ~bridge.is_allowed(int32(a)), a = 0; end   % after GAME_OVER only RESET is allowed
    r = struct(bridge.apply(int32(a), int32(-1), int32(-1)));
    f = uint8(r.frames); %#ok<NASGU>
    t(i) = toc;
end
fprintf('Step + conversion: median %.2f ms, max %.2f ms (n=%d)\n', 1000 * median(t), 1000 * max(t), n);

% 5. Look at the picture (plain MATLAB figure, not Psychtoolbox).
s = struct(bridge.start_game('ls20'));
frames = uint8(s.frames);
figure('Name', 'ls20 first frame'); image(squeeze(frames(1, :, :, :))); axis image off;
fprintf('ALL CHECKS PASSED. A figure shows the first frame of ls20.\n');
end

function a = mod_action(i)
a = mod(i - 1, 4) + 1;   % cycle ACTION1-4
end

function check(ok, what)
if ok
    fprintf('  PASS  %s\n', what);
else
    error('test_bridge:fail', 'FAIL  %s', what);
end
end
