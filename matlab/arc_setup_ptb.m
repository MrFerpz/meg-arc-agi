function arc_setup_ptb(ptbDir)
% ARC_SETUP_PTB  Put Psychtoolbox on the MATLAB path for this session only.
%   ptbDir: the Psychtoolbox folder (default: Psychtoolbox inside the repo,
%   else ../Psychtoolbox next to the repo).
%   Does nothing if Psychtoolbox is already on the path. Does not save the path.
if exist('PsychtoolboxVersion', 'file') == 2
    return
end
if nargin < 1 || isempty(ptbDir)
    repo = fileparts(fileparts(mfilename('fullpath')));
    ptbDir = fullfile(repo, 'Psychtoolbox');
    if ~isfolder(ptbDir), ptbDir = fullfile(fileparts(repo), 'Psychtoolbox'); end
end
% Accept the Psychtoolbox-3 download folder too (it holds a Psychtoolbox\ subfolder).
if ~isfile(fullfile(ptbDir, 'PsychBasic', 'PsychtoolboxVersion.m')) && isfolder(fullfile(ptbDir, 'Psychtoolbox'))
    ptbDir = fullfile(ptbDir, 'Psychtoolbox');
end
assert(isfolder(fullfile(ptbDir, 'PsychBasic')), 'arc_setup_ptb:notFound', ...
    'No Psychtoolbox at %s. Pass the folder: arc_meg_task(..., ptbDir=''C:\\path\\Psychtoolbox'')', ptbDir);
% Same as SetupPsychtoolbox: add all subfolders, but not .git or .svn folders.
p = strsplit(genpath(ptbDir), pathsep);
p = p(~cellfun(@isempty, p) & ~contains(p, [filesep '.git']) & ~contains(p, [filesep '.svn']));
addpath(strjoin(p, pathsep));
fprintf('Psychtoolbox %s from %s\n', PsychtoolboxVersion, ptbDir);
end
