function writeTrigger = arc_inpout(address)
% ARC_INPOUT  Parallel-port trigger writer through inpoutx64.dll (no io64 needed).
%   writeTrigger = arc_inpout()             % finds the LPT port's I/O address itself
%   writeTrigger = arc_inpout(hex2dec('E050'))
%   writeTrigger(code) writes code (0-255) to the port's DATA register.
%
%   Same method as testStimCodesWindows.m (it works on the stimulus PC):
%   inpoutx64.dll in C:\Windows\System32 or on the MATLAB path, and a small .NET
%   wrapper built once with PowerShell into tempdir. The InpOut driver must be
%   installed once by starting MATLAB "as administrator".
if ~ispc, error('arc_inpout:notWindows', 'triggerMode ''inpout'' is for Windows only.'); end
if nargin < 1 || isempty(address)
    address = findLptAddress();
    assert(~isempty(address), 'arc_inpout:noAddress', ['Could not read the parallel port''s I/O range. ', ...
        'Device Manager > Ports (COM and LPT) > the LPT port > Resources > I/O Range: pass the first number as triggerAddress.']);
end

dllPath = which('inpoutx64.dll');
if isempty(dllPath) && isfile('C:\Windows\System32\inpoutx64.dll'), dllPath = 'C:\Windows\System32\inpoutx64.dll'; end
assert(~isempty(dllPath), 'arc_inpout:noDll', ...
    'inpoutx64.dll not found. Put it in C:\Windows\System32 or on the MATLAB path (see testStimCodesWindows.m).');
if ~contains(getenv('PATH'), fileparts(dllPath))
    setenv('PATH', [fileparts(dllPath) ';' getenv('PATH')]);   % lets the .NET wrapper find the DLL
end

% Same file name and class as testStimCodesWindows.m, so a wrapper built by it is reused.
wrapper = fullfile(tempdir, 'InpOutNet_v2.dll');
if ~isfile(wrapper)
    src = ['using System.Runtime.InteropServices;' newline ...
           'namespace InpOutNet {' newline ...
           'public static class InpOutPort {' newline ...
           '  [DllImport("inpoutx64.dll")] public static extern void Out32(ushort PortAddress, ushort Data);' newline ...
           '  [DllImport("inpoutx64.dll")] public static extern ushort Inp32(ushort PortAddress);' newline ...
           '  [DllImport("inpoutx64.dll")] public static extern int IsInpOutDriverOpen();' newline ...
           '}' newline ...
           '}'];
    arc_build_net(src, wrapper);
end
NET.addAssembly(wrapper);
assert(InpOutNet.InpOutPort.IsInpOutDriverOpen() ~= 0, 'arc_inpout:noDriver', ...
    'The InpOut driver is not open. Start MATLAB as administrator once so inpoutx64.dll can install its driver.');

addr = uint16(address);
writeTrigger = @(v) InpOutNet.InpOutPort.Out32(addr, uint16(v));
fprintf('Parallel port triggers at 0x%X (inpoutx64)\n', address);
end

function a = findLptAddress()
% Lowest I/O start address Windows gave the first parallel port (the data register).
a = [];
ps1 = fullfile(tempdir, 'find_lpt_address.ps1');
fid = fopen(ps1, 'w');
fprintf(fid, '$p = Get-CimInstance Win32_ParallelPort | Select-Object -First 1\n');
fprintf(fid, 'if ($p) {\n');
fprintf(fid, '  Get-CimInstance Win32_PNPAllocatedResource | Where-Object { $_.Dependent.DeviceID -eq $p.PNPDeviceID } | ForEach-Object {\n');
fprintf(fid, '    $r = $_.Antecedent\n');
fprintf(fid, '    if ($r.CimClass.CimClassName -eq ''Win32_PortResource'') { [string][uint64]$r.StartingAddress }\n');
fprintf(fid, '  }\n}\n');
fclose(fid);
[~, out] = system(sprintf('powershell -NoProfile -ExecutionPolicy Bypass -File "%s"', ps1));
tok = regexp(out, '(\d+)', 'tokens');
if isempty(tok), return; end
a = min(cellfun(@(t) str2double(t{1}), tok));
end
