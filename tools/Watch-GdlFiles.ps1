<#
    Count the files created and changed under some folders while a build runs,
    by folder, to say where GUI Designer writes (and so which folders real-time
    scanning has to look through). A file-system watcher on each root, counting
    in compiled code - a PowerShell event handler cannot keep up with a build -
    and a table of the busiest folders written when the stop file appears.

        powershell -NoProfile -File tools\Watch-GdlFiles.ps1 -Out w.tsv -Stop w.stop `
            -Roots C:\gdlwork,$env:LOCALAPPDATA,$env:APPDATA,C:\ProgramData

    The table has a line per folder: its path, how many files were created in
    it, how many change events (a write is usually several), and how many bytes
    the files that were still there at the end add up to. Folders under
    -Exclude (a regular expression on the path) are not counted - Claude
    Code's own, the watcher's output. It reads the file system's change
    notifications; it changes nothing.

    A watcher over a busy folder drops events when GUI Designer outpaces it
    (the buffer is 64 KB), and says how many times; read the counts as a lower
    bound.
#>
param(
    [Parameter(Mandatory)][string]$Out,
    [Parameter(Mandatory)][string]$Stop,
    [string[]]$Roots = @('C:\gdlwork', $env:LOCALAPPDATA, $env:APPDATA, 'C:\ProgramData'),
    [string]$Exclude = '\\(claude|\.claude|npm-cache|node_modules|CrashDumps|Microsoft\\(Windows|Edge|Defender)|Packages|Google|Mozilla|Temp\\claude)\\|\\Claude\\|\.claude',
    [int]$Top = 40
)

if (-not ('GdlFileCounter' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;

public class GdlFileCounter : IDisposable {
    public Dictionary<string, long[]> Dirs = new Dictionary<string, long[]>();   // created, changed
    public long Dropped;
    readonly List<FileSystemWatcher> watchers = new List<FileSystemWatcher>();
    readonly Regex exclude;
    readonly object gate = new object();

    public GdlFileCounter(string[] roots, string excludePattern) {
        exclude = new Regex(excludePattern, RegexOptions.IgnoreCase | RegexOptions.Compiled);
        foreach (string r in roots) {
            if (!Directory.Exists(r)) continue;
            FileSystemWatcher w = new FileSystemWatcher(r);
            w.IncludeSubdirectories = true;
            w.InternalBufferSize = 65536;
            w.NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite | NotifyFilters.Size;
            w.Created += delegate(object s, FileSystemEventArgs e) { Count(e.FullPath, 0); };
            w.Changed += delegate(object s, FileSystemEventArgs e) { Count(e.FullPath, 1); };
            w.Renamed += delegate(object s, RenamedEventArgs e) { Count(e.FullPath, 0); };
            w.Error += delegate(object s, ErrorEventArgs e) { lock (gate) { Dropped++; } };
            w.EnableRaisingEvents = true;
            watchers.Add(w);
        }
    }

    void Count(string path, int kind) {
        if (exclude.IsMatch(path)) return;
        string dir = Path.GetDirectoryName(path);
        if (dir == null) return;
        lock (gate) {
            long[] c;
            if (!Dirs.TryGetValue(dir, out c)) { c = new long[2]; Dirs[dir] = c; }
            c[kind]++;
        }
    }

    public string[] Snapshot() {
        lock (gate) {
            List<string> o = new List<string>();
            foreach (KeyValuePair<string, long[]> kv in Dirs)
                o.Add(kv.Key + "\t" + kv.Value[0] + "\t" + kv.Value[1]);
            return o.ToArray();
        }
    }

    public void Dispose() { foreach (FileSystemWatcher w in watchers) w.Dispose(); }
}
'@
}

$counter = [GdlFileCounter]::new([string[]]$Roots, $Exclude)
try {
    while (-not (Test-Path $Stop)) { Start-Sleep -Seconds 2 }
} finally {
    $counter.Dispose()
}

$rows = foreach ($line in $counter.Snapshot()) {
    $f = $line -split "`t"
    $bytes = 0
    $n = 0
    if (Test-Path -LiteralPath $f[0]) {
        $files = @(Get-ChildItem -LiteralPath $f[0] -File -Force -ErrorAction SilentlyContinue)
        $n = $files.Count
        $bytes = ($files | Measure-Object -Property Length -Sum).Sum
    }
    [pscustomobject]@{ Dir = $f[0]; Created = [int]$f[1]; Changes = [int]$f[2]; FilesLeft = $n; BytesLeft = [long]$bytes }
}
"dir`tcreated`tchange_events`tfiles_left`tbytes_left" | Out-File -FilePath $Out -Encoding ascii
$rows | Sort-Object Created, Changes -Descending | Select-Object -First $Top | ForEach-Object {
    "{0}`t{1}`t{2}`t{3}`t{4}" -f $_.Dir, $_.Created, $_.Changes, $_.FilesLeft, $_.BytesLeft
} | Out-File -FilePath $Out -Encoding ascii -Append
"# watcher errors (events dropped): $($counter.Dropped)" | Out-File -FilePath $Out -Encoding ascii -Append
