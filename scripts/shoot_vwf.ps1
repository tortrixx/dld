<#
================================================================================
 shoot_vwf.ps1 —— 用 Quartus II 9.1 **GUI 的波形编辑器**给每个模块拍实测仿真图
================================================================================

⚠️ 本文件必须保留 **UTF-8 BOM**（开头 3 字节 EF BB BF）：
   Windows PowerShell 5.1 读**没有 BOM** 的 .ps1 会按 GBK 解码 → 中文注释全变乱码
   → 脚本直接语法报错。`scripts/bootstrap.ps1` 同理。
   若被某个编辑器/写入接口吃掉了 BOM，请补回：
       $p='scripts\shoot_vwf.ps1'
       $t=[IO.File]::ReadAllText($p,(New-Object Text.UTF8Encoding($false)))
       [IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding($true)))

【为什么需要它】
    实验报告里的"仿真波形图"必须是 **Quartus 软件界面的截图**。
    `docs/图/SIM-*.svg` 是 `scripts/sim.py` 用 Python 自己渲染的**辅助图**，
    不是 Quartus 的界面，不能当实测截图交。本脚本负责拍真正的那一组：
    `docs/图/GUI-<模块>.png`。

【原理】
    1. 用 GUI 打开 `quartus/puzzle.qpf`（**只读**：不做任何编译）；
    2. 用 `File → Open` 打开 `sim/<模块>.vwf`
       —— 这个文件既是激励也是结果（`quartus_sim --overwrite_waveform=on`
       会把仿真结果写回每个节点的 TRANSITION_LIST，见 `scripts/vwf.py` 开头）；
    3. `Ctrl+W`（View → Fit in Window）把整段仿真时间铺满窗口；
    4. 用 `PrintWindow` 抓主窗口位图存成 PNG。
       ⚠️ 抓的是**窗口位图**而不是屏幕像素，所以窗口被挡住、被拖出屏幕都不影响，
       也不会把桌面上别的东西拍进去。

【为什么不用 SendKeys 敲路径】
    打开对话框是**独立的顶层窗口**，路径直接写进它的文件名控件
    （控件 ID 1148，`WM_SETTEXT`）+ 发 `WM_COMMAND IDOK`，
    比模拟键盘可靠得多（不受输入法/焦点影响）。

【用法】
    powershell -ExecutionPolicy Bypass -File scripts/shoot_vwf.ps1
    powershell -ExecutionPolicy Bypass -File scripts/shoot_vwf.ps1 -Modules buzzer_ctrl,puzzle_top
    powershell -ExecutionPolicy Bypass -File scripts/shoot_vwf.ps1 -KeepOpen      # 拍完不关 Quartus
    powershell -ExecutionPolicy Bypass -File scripts/shoot_vwf.ps1 -CloseQuartus  # 拍完关掉

【注意】
    · 需要 Quartus II 9.1 已安装（路径探测顺序同 `scripts/qenv.py`）；
    · 运行期间会**占用桌面焦点**并把 Quartus 窗口挪到左上角，拍完会恢复；
    · 第一次打开 .vwf 时 Quartus 会弹一条"将来不再支持内置仿真器"的提示，
      脚本会自动勾掉 "Don't show this again" 并确定。
#>
[CmdletBinding()]
param(
    # 要拍的模块（默认 = sim/ 下全部 tb_*.py 对应的模块）
    [string[]]$Modules,
    # 输出目录（相对仓库根）
    [string]$OutDir = 'docs\图',
    # 单个文件打开后的等待毫秒数（大文件要更久）
    [int]$OpenWaitMs = 9000,
    # 拍完是否保持 Quartus 开着
    [switch]$KeepOpen,
    # 拍完关掉 Quartus
    [switch]$CloseQuartus,
    # 只做连接/摆位，不拍照（调试用）
    [switch]$Probe,
    # 从顶部裁掉多少像素（**默认 33 = 裁掉标题栏**）
    # ⚠️ 为什么默认裁：Quartus 的标题栏会写 `C:/Users/<你的 Windows 用户名>/.../puzzle`，
    #    截进去就等于把本机绝对路径与用户名发到公开仓库 —— 本项目纪律本来就是
    #    "全仓库不出现作者本机绝对路径"。裁掉标题栏后，菜单栏 / 工程名 / 节点列表 /
    #    波形网格 / 时间刻度都还在，仍然一眼能看出是 Quartus 界面。
    #    想要完整窗口（含标题栏）就传 -CropTop 0。
    [int]$CropTop = 33
)

$ErrorActionPreference = 'Stop'
$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ROOT

# ============================================================
# 0. 依赖
# ============================================================
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public struct RECT { public int Left, Top, Right, Bottom; }
public class W32 {
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool repaint);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr h, uint cmd);
  [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h, int id);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="SendMessageW")]
  public static extern IntPtr SendMessageStr(IntPtr h, uint msg, IntPtr w, string l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  public static string Text(IntPtr h){ var sb=new StringBuilder(1024); GetWindowTextW(h,sb,1024); return sb.ToString(); }
  public static string Cls(IntPtr h){ var sb=new StringBuilder(256); GetClassNameW(h,sb,256); return sb.ToString(); }
  public static List<IntPtr> Kids(IntPtr h){
    var list = new List<IntPtr>();
    IntPtr c = GetWindow(h, 5);
    while (c != IntPtr.Zero) { list.Add(c); c = GetWindow(c, 2); }
    return list;
  }
  public static List<IntPtr> Tops(){
    var list = new List<IntPtr>();
    EnumWindows(delegate(IntPtr c, IntPtr p){ list.Add(c); return true; }, IntPtr.Zero);
    return list;
  }
}
'@

function Say([string]$m) { Write-Host ("[shoot_vwf] " + $m) }

# ============================================================
# 1. 找 quartus.exe（顺序与 scripts/qenv.py 一致）
# ============================================================
function Resolve-QuartusExe {
    $cands = @()
    foreach ($v in @('QUARTUS_ROOT', 'QUARTUS_ROOTDIR', 'QUARTUS_BIN')) {
        $val = [Environment]::GetEnvironmentVariable($v)
        if ($val) { $cands += $val }
    }
    $cands += @(
        'C:\QuartusII91\QuartusII91',
        'C:\altera\91\quartus',
        'C:\altera\91',
        'D:\QuartusII91\QuartusII91'
    )
    $cands += (Get-ChildItem 'C:\' -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*Quartus*' } | ForEach-Object { $_.FullName })
    foreach ($c in $cands) {
        foreach ($p in @((Join-Path $c 'quartus.exe'),
                         (Join-Path $c 'quartus\bin\quartus.exe'),
                         (Join-Path $c 'bin\quartus.exe'))) {
            if (Test-Path $p) { return (Resolve-Path $p).Path }
        }
    }
    $onPath = Get-Command quartus.exe -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    throw "找不到 quartus.exe —— 请设 QUARTUS_ROOT 环境变量，或把 quartus\bin 加进 PATH"
}

# ============================================================
# 2. 窗口工具
# ============================================================
function Get-MainWindow {
    $p = Get-Process -Name quartus -ErrorAction SilentlyContinue |
         Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
    if ($p) { return $p.MainWindowHandle }
    return [IntPtr]::Zero
}

function Get-QuartusPid([IntPtr]$hwnd) {
    $q = [uint32]0
    [void][W32]::GetWindowThreadProcessId($hwnd, [ref]$q)
    return $q
}

function Get-VisibleDialogs([IntPtr]$hwnd) {
    $q = Get-QuartusPid $hwnd
    $out = @()
    foreach ($t in [W32]::Tops()) {
        $tp = [uint32]0
        [void][W32]::GetWindowThreadProcessId($t, [ref]$tp)
        if ($tp -eq $q -and [W32]::IsWindowVisible($t) -and ([W32]::Cls($t) -eq '#32770')) { $out += $t }
    }
    return $out
}

function Dismiss-Dialogs([IntPtr]$hwnd) {
    foreach ($d in (Get-VisibleDialogs $hwnd)) {
        $title = [W32]::Text($d)
        $ok = [IntPtr]::Zero; $never = [IntPtr]::Zero
        foreach ($c in [W32]::Kids($d)) {
            $tx = [W32]::Text($c)
            if ($tx -eq 'OK' -or $tx -eq '确定') { $ok = $c }
            elseif ($tx -like '*show this again*' -or $tx -like '*不再显示*') { $never = $c }
        }
        if ($never -ne [IntPtr]::Zero) { [void][W32]::SendMessage($never, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) }
        if ($ok -ne [IntPtr]::Zero) { [void][W32]::SendMessage($ok, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) }
        else { [void][W32]::PostMessage($d, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero) }
        Say ("关掉提示框 '" + $title + "'")
    }
}

function Get-EditorWindow([IntPtr]$hwnd) {
    $found = [IntPtr]::Zero
    $stack = New-Object System.Collections.Stack
    $stack.Push($hwnd)
    while ($stack.Count -gt 0) {
        $cur = $stack.Pop()
        foreach ($c in [W32]::Kids($cur)) {
            if (([W32]::Text($c) -like '*.vwf') -and ([W32]::Cls($c) -like 'Afx:*')) { $found = $c }
            $stack.Push($c)
        }
    }
    return $found
}

function Capture-Window([IntPtr]$hwnd, [string]$path) {
    $r = New-Object RECT
    [void][W32]::GetWindowRect($hwnd, [ref]$r)
    $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
    $bmp = New-Object System.Drawing.Bitmap($w, $h)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    [void][W32]::PrintWindow($hwnd, $hdc, 2)
    $g.ReleaseHdc($hdc); $g.Dispose()

    # 裁掉标题栏（见 param 里 $CropTop 的说明：避免把本机用户名写进公开仓库）
    if ($CropTop -gt 0 -and $CropTop -lt $h) {
        $rect = New-Object System.Drawing.Rectangle(0, $CropTop, $w, ($h - $CropTop))
        $cropped = $bmp.Clone($rect, $bmp.PixelFormat)
        $bmp.Dispose()
        $bmp = $cropped
        $h = $h - $CropTop
    }
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    return @{ W = $w; H = $h; Bytes = (Get-Item $path).Length }
}

function Send-Keys([IntPtr]$hwnd, [string]$keys) {
    [void][W32]::SetForegroundWindow($hwnd)
    Start-Sleep -Milliseconds 400
    [System.Windows.Forms.SendKeys]::SendWait($keys)
}

# ============================================================
# 3. 主流程
# ============================================================
$exe = Resolve-QuartusExe
Say ("Quartus: " + $exe)
$qpf = Join-Path $ROOT 'quartus\puzzle.qpf'
if (-not (Test-Path $qpf)) { throw "找不到 $qpf" }

if ($Modules -and $Modules.Count -gt 0) {
    $mods = $Modules
} else {
    $mods = Get-ChildItem (Join-Path $ROOT 'sim') -Filter 'tb_*.py' |
            ForEach-Object { $_.BaseName.Substring(3) } | Sort-Object
}
Say ("模块（" + $mods.Count + "）：" + ($mods -join ', '))

$outPath = Join-Path $ROOT $OutDir
if (-not (Test-Path $outPath)) { New-Item -ItemType Directory -Path $outPath | Out-Null }

# --- 3.1 确保 GUI 在跑 ---
$main = Get-MainWindow
if ($main -eq [IntPtr]::Zero) {
    Say "启动 Quartus GUI（第一次要等 1~2 分钟）..."
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.Arguments = '"' + $qpf + '"'
    $psi.WorkingDirectory = Join-Path $ROOT 'quartus'
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true     # 关键：不让子进程继承本进程的 stdout 管道
    $psi.RedirectStandardError = $true
    [void][System.Diagnostics.Process]::Start($psi)
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 3
        $main = Get-MainWindow
        if ($main -ne [IntPtr]::Zero) { break }
    }
    if ($main -eq [IntPtr]::Zero) { throw "Quartus GUI 没起来（等 180 s）" }
}
Say ("主窗口 hwnd=" + $main)

# --- 3.2 摆位（抓的是窗口位图，位置只影响人看，不影响图） ---
[void][W32]::ShowWindow($main, 9)
Start-Sleep -Milliseconds 400
$wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
[void][W32]::MoveWindow($main, 0, 0, [int]$wa.Width, [int]$wa.Height, $true)
Start-Sleep -Milliseconds 900
$r = New-Object RECT; [void][W32]::GetWindowRect($main, [ref]$r)
Say ("窗口 " + ($r.Right - $r.Left) + "x" + ($r.Bottom - $r.Top))

if ($Probe) { Say 'Probe 模式，结束'; exit 0 }

# --- 3.3 逐个模块拍照 ---
$results = @()
foreach ($m in $mods) {
    $vwf = Join-Path $ROOT ("sim\" + $m + ".vwf")
    if (-not (Test-Path $vwf)) { Say ("跳过 " + $m + "：没有 " + $vwf); continue }

    Dismiss-Dialogs $main

    # 打开：Ctrl+O → 填路径 → IDOK
    Send-Keys $main '^o'
    Start-Sleep -Milliseconds 2500
    $dlg = [IntPtr]::Zero
    $dlgs = Get-VisibleDialogs $main
    if ($dlgs.Count -eq 0) { Say ("!! " + $m + "：打开对话框没出现"); continue }
    $dlg = $dlgs[0]
    $edit = [W32]::GetDlgItem($dlg, 1148)
    if ($edit -eq [IntPtr]::Zero) { $edit = [W32]::GetDlgItem($dlg, 1152) }
    if ($edit -eq [IntPtr]::Zero) { Say ("!! " + $m + "：找不到文件名控件"); continue }
    [void][W32]::SendMessageStr($edit, 0x000C, [IntPtr]::Zero, $vwf)
    Start-Sleep -Milliseconds 500
    [void][W32]::SendMessage($dlg, 0x0111, [IntPtr]1, $edit)
    Start-Sleep -Milliseconds $OpenWaitMs

    # 等编辑器切到本模块
    # ⚠️ Quartus 把多个 .vwf 开成**标签页**，而这里拿到的窗口文本是**面板标题**
    #    （停在第一个标签的名字），所以匹配不上**不代表**没切过去 —— 只提示，不中断。
    $ok = $false
    for ($i = 0; $i -lt 20; $i++) {
        $ed = Get-EditorWindow $main
        if ($ed -ne [IntPtr]::Zero -and ([W32]::Text($ed) -like ('*' + $m + '.vwf*'))) { $ok = $true; break }
        Start-Sleep -Milliseconds 1000
    }
    if (-not $ok) { Say ("提示：" + $m + " 的面板标题没变（标签页误报居多），拍完请自己看一眼图") }
    Start-Sleep -Milliseconds 1500

    Dismiss-Dialogs $main

    # 整段仿真时间铺满窗口
    Send-Keys $main '^w'
    Start-Sleep -Milliseconds 2000

    $png = Join-Path $outPath ('GUI-' + $m + '.png')
    $info = Capture-Window $main $png
    Say ($m.PadRight(16) + " -> " + (Split-Path -Leaf $png) + "  " + $info.W + "x" + $info.H + "  " + $info.Bytes + " B")
    $results += [pscustomobject]@{ Module = $m; Png = $png; W = $info.W; H = $info.H; Bytes = $info.Bytes }
}

Say ("拍了 " + $results.Count + " 张")

# --- 3.4 收尾 ---
if (-not $KeepOpen) {
    [void][W32]::MoveWindow($main, 0, 0, [int]$wa.Width, [int]([Math]::Min($wa.Height, 1010)), $true)
}
if ($CloseQuartus) {
    $qp = Get-Process -Name quartus -ErrorAction SilentlyContinue
    if ($qp) { $qp | ForEach-Object { [void]$_.CloseMainWindow() }; Start-Sleep -Seconds 3 }
    Say "已请求关闭 Quartus"
}

$results | Format-Table -AutoSize
exit 0
