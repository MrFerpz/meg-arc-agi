function testStimCodesWindows(address, codes, holdSec)
% TESTSTIMCODESWINDOWS  Send dummy stim codes on a Windows PC's parallel port (no io64 needed).
%
%   testStimCodesWindows                         % finds the LPT port's I/O address itself, sends 1 2 4 ... 128 255
%   testStimCodesWindows(hex2dec('E050'))        % use this I/O address (first number of the LPT port's I/O Range)
%   testStimCodesWindows(addr, [1 5 9], 0.5)     % your own codes, each held 0.5 s, then 0
%
% What it needs (once):
%   * inpoutx64.dll (the InpOut32/InpOutx64 library from highrez.co.uk, x64 version) either in C:\Windows\System32
%     or in a folder on the MATLAB path. The driver inside it installs itself the first time it loads when MATLAB
%     is started "as administrator": do that once.
%   * Windows 64-bit MATLAB. No MATLAB compiler and no io64.mexw64: a tiny .NET wrapper is built once with
%     PowerShell (Add-Type) into the temp folder and loaded with NET.addAssembly.
%
% Each code is written to the port's DATA register, held for holdSec (default 0.2 s), then 0 is written. The code
% is also read back from the port; a read-back that differs does not always mean failure (some ports do not
% read back), so check the real receiver: the MEG STI channel, a scope, or an LED/logic probe on pins 2-9.
% WARNING: the box feeds the MEG trigger input. Test with acquisition off or into a test recording.
%
% Version 1.1 -- 2026-10-21 (v1.1: .NET class in a namespace, MATLAB could not resolve the global one; UNTESTED: written on a machine without MATLAB, the card or the stim box)
if ~ispc, error('testStimCodesWindows is for Windows. On Linux the paradigm uses ppdev_mex.'); end
if nargin < 2 || isempty(codes),   codes = [1 2 4 8 16 32 64 128 255]; end
if nargin < 3 || isempty(holdSec), holdSec = 0.2; end

% ---- 1. I/O address of the parallel port ----
if nargin < 1 || isempty(address)
    address = findLptAddress();
    if isempty(address)
        error(['Could not read the parallel port''s I/O range automatically. Open Device Manager > Ports (COM and LPT) > ', ...
               'the LPT port > Resources > I/O Range and call  testStimCodesWindows(hex2dec(''<first number>''))']);
    end
end
fprintf('Parallel port data register at 0x%X\n', address);

% ---- 2. inpoutx64.dll ----
dllPath = which('inpoutx64.dll');
if isempty(dllPath) && isfile('C:\Windows\System32\inpoutx64.dll'), dllPath = 'C:\Windows\System32\inpoutx64.dll'; end
if isempty(dllPath)
    error(['inpoutx64.dll not found. Get the InpOut32/InpOutx64 binaries from highrez.co.uk (the x64 folder holds inpoutx64.dll), ', ...
           'copy it to C:\Windows\System32 (as administrator) or to a folder on the MATLAB path, then start MATLAB as administrator.']);
end
setenv('PATH', [fileparts(dllPath) ';' getenv('PATH')]);   % lets the .NET wrapper find the DLL wherever it is

% ---- 3. a small .NET wrapper around Out32 / Inp32, built once ----
wrapper = fullfile(tempdir, 'InpOutNet_v2.dll');   % v2: the class now lives in a namespace (MATLAB cannot reach types in the global namespace)
if ~isfile(wrapper)
    src = ['using System.Runtime.InteropServices;' newline ...
           'namespace InpOutNet {' newline ...
           'public static class InpOutPort {' newline ...
           '  [DllImport("inpoutx64.dll")] public static extern void Out32(ushort PortAddress, ushort Data);' newline ...
           '  [DllImport("inpoutx64.dll")] public static extern ushort Inp32(ushort PortAddress);' newline ...
           '  [DllImport("inpoutx64.dll")] public static extern int IsInpOutDriverOpen();' newline ...
           '}' newline ...
           '}'];
    ps1 = fullfile(tempdir, 'build_inpout_wrapper.ps1');
    fid = fopen(ps1, 'w');
    fprintf(fid, '$src = @''\n%s\n''@\n', src);
    fprintf(fid, 'Add-Type -TypeDefinition $src -OutputAssembly ''%s'' -OutputType Library\n', wrapper);
    fclose(fid);
    [st, out] = system(sprintf('powershell -NoProfile -ExecutionPolicy Bypass -File "%s"', ps1));
    if st ~= 0 || ~isfile(wrapper)
        error('Building the .NET wrapper failed:\n%s', out);
    end
end
NET.addAssembly(wrapper);

% ---- 4. driver check ----
if InpOutNet.InpOutPort.IsInpOutDriverOpen() == 0
    error(['The InpOut driver is not open. Start MATLAB as administrator once (Run as administrator) so inpoutx64.dll can install ', ...
           'its driver, and make sure the DLL is the 64-bit one.']);
end

% ---- 5. send the codes ----
fprintf('Sending:\n');
for c = codes(:)'
    InpOutNet.InpOutPort.Out32(uint16(address), uint16(c));
    back = double(InpOutNet.InpOutPort.Inp32(uint16(address)));
    fprintf('  code %3d written, port reads back %3d\n', c, back);
    pause(holdSec);
    InpOutNet.InpOutPort.Out32(uint16(address), uint16(0));
    pause(holdSec);
end
fprintf('Done. Port left at 0.\n');
end

function a = findLptAddress()
% I/O range(s) Windows assigned to the first parallel port; returns the lowest start address (the data register).
a = [];
ps1 = fullfile(tempdir, 'find_lpt_address.ps1');
fid = fopen(ps1, 'w');
fprintf(fid, '$p = Get-CimInstance Win32_ParallelPort | Select-Object -First 1\n');
fprintf(fid, 'if ($p) {\n');
fprintf(fid, '  Get-CimInstance Win32_PNPAllocatedResource | Where-Object { $_.Dependent.DeviceID -eq $p.PNPDeviceID } | ForEach-Object {\n');
fprintf(fid, '    $r = $_.Antecedent\n');
fprintf(fid, '    if ($r.CimClass.CimClassName -eq ''Win32_PortResource'') { [string][uint64]$r.StartingAddress }\n');   % I/O ports only (not memory or IRQ); only the start address is filled in
fprintf(fid, '  }\n}\n');
fclose(fid);
[~, out] = system(sprintf('powershell -NoProfile -ExecutionPolicy Bypass -File "%s"', ps1));
tok = regexp(out, '(\d+)', 'tokens');
if isempty(tok), return; end
starts = cellfun(@(t) str2double(t{1}), tok);
fprintf('I/O port start address(es) of the parallel port: ');
fprintf('0x%X  ', starts);
fprintf('\n');
a = min(starts);   % the data register is the first port of the range
end
