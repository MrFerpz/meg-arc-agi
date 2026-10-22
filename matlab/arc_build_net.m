function arc_build_net(src, dllFile)
% ARC_BUILD_NET  Compile C# source into a .NET DLL with Windows PowerShell (Add-Type).
%   No compiler or Visual Studio needed. Load the result with NET.addAssembly(dllFile).
ps1 = [tempname '.ps1'];
fid = fopen(ps1, 'w');
fprintf(fid, '$src = @''\n%s\n''@\n', src);
fprintf(fid, 'Add-Type -TypeDefinition $src -OutputAssembly ''%s'' -OutputType Library\n', dllFile);
fclose(fid);
[st, out] = system(sprintf('powershell -NoProfile -ExecutionPolicy Bypass -File "%s"', ps1));
delete(ps1);
if st ~= 0 || ~isfile(dllFile)
    error('arc_build_net:failed', 'Building %s failed:\n%s', dllFile, out);
end
end
