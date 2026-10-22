function mouse = arc_mouse_hook(wheelMergeMs)
% ARC_MOUSE_HOOK  Read left click, right click, wheel up and wheel down on Windows.
%   mouse = arc_mouse_hook();      % or arc_mouse_hook(wheelMergeMs), default 150
%   ev = mouse.poll();   % n x 4: [button, t, x, y], oldest first
%                        % button 1 = left, 2 = right, 3 = wheel up, 4 = wheel down
%                        % t = GetSecs time of the event, x y = screen pixels
%   ev = mouse.pollRaw();  % n x 6: [button, t, x, y, wheelDelta, merged], every event
%   The scroll buttons send more than one wheel event per press. A wheel event that
%   comes less than wheelMergeMs after the last one in the same direction is merged
%   into it (merged = 1): poll() leaves it out.
%   mouse.clear();       % drop all events not read yet
%   mouse.stop();        % remove the hook (arc_meg_task does this at the end)
%
%   Psychtoolbox cannot read the mouse wheel on Windows (GetMouseWheel gives an
%   error there). So this uses a Windows low-level mouse hook (WH_MOUSE_LL) in a
%   small .NET class, built once with PowerShell like the InpOut wrapper. The hook
%   runs on its own thread: it time-stamps each event when Windows delivers it,
%   even while MATLAB is busy. It only watches: the mouse works as normal.
if ~ispc, error('arc_mouse_hook:notWindows', 'arc_mouse_hook is for Windows only.'); end
if nargin < 1, wheelMergeMs = 150; end

% Change the version in the file name when the C# code changes: MATLAB cannot
% reload a .NET assembly in one session: restart MATLAB after a change.
dllFile = fullfile(tempdir, 'ArcMouseHook_v2.dll');
if ~isfile(dllFile)
    arc_build_net(strjoin(csharpSource(), newline), dllFile);
end
NET.addAssembly(dllFile);
ArcMouse.Hook.SetWheelMerge(wheelMergeMs / 1000);
if ~ArcMouse.Hook.Start()
    error('arc_mouse_hook:start', 'Mouse hook did not start: %s', char(ArcMouse.Hook.Error()));
end

% Offset from the hook's clock (QueryPerformanceCounter) to GetSecs.
d = zeros(1, 9);
for i = 1:numel(d)
    t0 = GetSecs; tHook = ArcMouse.Hook.Now(); t1 = GetSecs;
    d(i) = (t0 + t1) / 2 - tHook;
end
offset = median(d);

mouse.poll = @() pollEvents(offset, false);
mouse.pollRaw = @() pollEvents(offset, true);
mouse.clear = @() ArcMouse.Hook.Clear();
mouse.stop = @() ArcMouse.Hook.Stop();
end

function ev = pollEvents(offset, raw)
v = double(ArcMouse.Hook.Poll());
ev = reshape(v, 6, [])';
if ~isempty(ev), ev(:, 2) = ev(:, 2) + offset; end
if ~raw, ev = ev(ev(:, 6) == 0, 1:4); end
end

function src = csharpSource()
src = {
'using System;'
'using System.Collections.Concurrent;'
'using System.Collections.Generic;'
'using System.Diagnostics;'
'using System.Runtime.InteropServices;'
'using System.Threading;'
'namespace ArcMouse {'
'public static class Hook {'
'  [StructLayout(LayoutKind.Sequential)] struct POINT { public int x; public int y; }'
'  [StructLayout(LayoutKind.Sequential)] struct MSLLHOOKSTRUCT { public POINT pt; public uint mouseData; public uint flags; public uint time; public IntPtr extra; }'
'  [StructLayout(LayoutKind.Sequential)] struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam; public uint time; public POINT pt; }'
'  delegate IntPtr Proc(int nCode, IntPtr wParam, IntPtr lParam);'
'  [DllImport("user32.dll", SetLastError = true)] static extern IntPtr SetWindowsHookEx(int idHook, Proc fn, IntPtr hMod, uint threadId);'
'  [DllImport("user32.dll")] static extern bool UnhookWindowsHookEx(IntPtr hook);'
'  [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr hook, int nCode, IntPtr wParam, IntPtr lParam);'
'  [DllImport("user32.dll")] static extern int GetMessage(out MSG msg, IntPtr hWnd, uint min, uint max);'
'  [DllImport("user32.dll")] static extern bool PostThreadMessage(uint threadId, uint msg, IntPtr wParam, IntPtr lParam);'
'  [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();'
'  [DllImport("kernel32.dll")] static extern IntPtr GetModuleHandle(string name);'
'  static readonly ConcurrentQueue<double[]> events = new ConcurrentQueue<double[]>();'
'  static Proc proc;'   % kept in a field so the garbage collector does not free it
'  static IntPtr hook = IntPtr.Zero;'
'  static uint threadId;'
'  static Thread thread;'
'  static string error = "";'
'  static double wheelMerge = 0.15;'
'  static double[] lastWheel = { -1e9, -1e9 };'
'  public static void SetWheelMerge(double seconds) { wheelMerge = seconds; }'
'  public static double Now() { return (double)Stopwatch.GetTimestamp() / Stopwatch.Frequency; }'
'  public static string Error() { return error; }'
'  static IntPtr Callback(int nCode, IntPtr wParam, IntPtr lParam) {'
'    if (nCode >= 0) {'
'      double t = Now();'
'      int msg = wParam.ToInt32();'
'      if (msg == 0x0201 || msg == 0x0204 || msg == 0x020A) {'   % WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MOUSEWHEEL
'        MSLLHOOKSTRUCT s = (MSLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(MSLLHOOKSTRUCT));'
'        int delta = msg == 0x020A ? (short)(s.mouseData >> 16) : 0;'
'        int button = msg == 0x0201 ? 1 : msg == 0x0204 ? 2 : (delta > 0 ? 3 : 4);'
'        int merged = 0;'
'        if (button >= 3) {'
'          if (t - lastWheel[button - 3] < wheelMerge) merged = 1;'
'          lastWheel[button - 3] = t;'   % a long burst stays one press
'        }'
'        events.Enqueue(new double[] { button, t, s.pt.x, s.pt.y, delta, merged });'
'      }'
'    }'
'    return CallNextHookEx(IntPtr.Zero, nCode, wParam, lParam);'
'  }'
'  public static bool Start() {'
'    if (thread != null) return true;'
'    ManualResetEvent ready = new ManualResetEvent(false);'
'    thread = new Thread(() => {'
'      threadId = GetCurrentThreadId();'
'      proc = Callback;'
'      hook = SetWindowsHookEx(14, proc, GetModuleHandle(null), 0);'   % 14 = WH_MOUSE_LL
'      if (hook == IntPtr.Zero) error = "SetWindowsHookEx failed, Windows error " + Marshal.GetLastWin32Error();'
'      ready.Set();'
'      if (hook == IntPtr.Zero) return;'
'      MSG m;'
'      while (GetMessage(out m, IntPtr.Zero, 0, 0) > 0) { }'
'      UnhookWindowsHookEx(hook);'
'      hook = IntPtr.Zero;'
'    });'
'    thread.IsBackground = true;'
'    thread.Priority = ThreadPriority.Highest;'
'    thread.Start();'
'    ready.WaitOne();'
'    if (hook == IntPtr.Zero) { thread = null; return false; }'
'    return true;'
'  }'
'  public static void Stop() {'
'    if (thread == null) return;'
'    PostThreadMessage(threadId, 0x0012, IntPtr.Zero, IntPtr.Zero);'   % WM_QUIT
'    thread.Join(1000);'
'    thread = null;'
'  }'
'  public static void Clear() { double[] e; while (events.TryDequeue(out e)) { } }'
'  public static double[] Poll() {'
'    List<double> all = new List<double>();'
'    double[] e;'
'    while (events.TryDequeue(out e)) all.AddRange(e);'
'    return all.ToArray();'
'  }'
'}'
'}'
};
end
