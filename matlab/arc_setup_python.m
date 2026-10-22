function bridgeModule = arc_setup_python(repo, mode)
% ARC_SETUP_PYTHON  Point MATLAB at the repo's Python 3.12 and load meg_arc.
%   Needs MATLAB R2024b or newer (first release with Python 3.12 support).
%   mode: 'InProcess' (default, fastest) or 'OutOfProcess' (use this if
%   Python libraries clash with MATLAB's own libraries; each call is slower).
if nargin < 2, mode = 'InProcess'; end
pe = pyenv;
if pe.Status == "NotLoaded"
    pyExe = fullfile(repo, '.venv', 'Scripts', 'python.exe');   % Windows
    if ~isfile(pyExe), pyExe = fullfile(repo, '.venv', 'bin', 'python'); end   % macOS / Linux
    assert(isfile(pyExe), 'arc_setup_python:noVenv', ...
        'No Python in %s. Run "uv sync --python 3.12" in that folder first (docs/06, 6.3).', fullfile(repo, '.venv'));
    pyenv('Version', pyExe, 'ExecutionMode', mode);
end
if count(py.sys.path, repo) == 0
    insert(py.sys.path, int32(0), repo);
end
bridgeModule = py.importlib.import_module('meg_arc.bridge');
end
