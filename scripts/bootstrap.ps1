# ============================================================================
#  bootstrap.ps1 —— 一键生成 Quartus 工程（Windows / PowerShell 主环境）
#
#  用法：
#     pwsh -File scripts/bootstrap.ps1                 # 顶层实体 = puzzle_top
#     pwsh -File scripts/bootstrap.ps1 board_test_top  # 换一个顶层实体
#
#  它**只做一件事**：把同学从"记得先跑生成脚本"里解放出来 ——
#  先定位仓库根，再调用 scripts/gen_project.py 写出
#  quartus/puzzle.qpf + quartus/puzzle.qsf。于是一份全新 clone 出来的仓库
#  就能直接编译，无需任何手工建工程的步骤。
#
#  说明：
#    · 只用系统 Python 3 的**标准库**，不安装任何东西，也不改别的文件。
#    · ⚠️ 本脚本**不**写死任何 Quartus 安装路径 —— 查找 Quartus 是
#      scripts/qenv.py 的职责，这里只管生成工程文件。
#    · 找 Python 按 `python` → `py -3` **两级回退**：Windows 上"装了 Python
#      但安装时没勾 Add Python to PATH"很常见，那时只有 py 启动器可用，
#      只找 python 会把它误判成"没装 Python"。
#    · ⚠️ 调用原生命令时**不信任** $ErrorActionPreference：见下面 Invoke-NativeSafe
#      的注释（Microsoft Store 的 python 占位程序 + PowerShell 7.4+ 会先抛
#      NativeCommandError，绕开我们自己的中文提示）。
#    · 不用 `#Requires` 之类的版本指令（在旧版 PowerShell 上兼容性差），
#      只用 $ErrorActionPreference 控制出错行为。
#    · ⚠️ 本文件必须存成 **UTF-8 带 BOM**：Windows PowerShell 5.1 对**没有 BOM** 的
#      .ps1 会按系统 ANSI 代码页解码（简体中文机器 = GBK/936），中文注释会被解成
#      乱码、并连带**把后面的引号吃掉**，报出一堆莫名其妙的
#      "Unexpected token '}'" —— 与本脚本的逻辑无关。改完请确认 BOM 还在。
#    · ⚠️ 若 PowerShell 报 "running scripts is disabled on this system" 或
#      "is not digitally signed"，那是**执行策略**拦住了脚本（与脚本内容无关，
#      脚本根本还没开始跑）—— 一次性放行即可：
#        powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
#      或给当前用户永久放行：Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# ============================================================================

$ErrorActionPreference = 'Stop'

# ---- 工具函数：安全地调用原生命令 ------------------------------------------
# ⚠️ 为什么需要这一层：本脚本开头设了 $ErrorActionPreference = 'Stop'。若系统里的
#    python 是 Microsoft Store 的**占位程序**（App Execution Alias），它既不干活、
#    又只会往 stderr 写一句 "Python was not found..." 并返回退出码 9009。
#      · 在 PowerShell 7.4+ 且开启了 $PSNativeCommandUseErrorActionPreference 的环境里，
#        原生命令的 stderr 输出会**先**抛出 NativeCommandError 终止脚本；
#      · 在 Windows PowerShell 5.1 里，只要对原生命令做了 `2>&1` 重定向，EAP='Stop'
#        同样会抛 NativeCommandError（本机实测：真退出码 9009 被吃成 1）。
#    两种情况都**到不了**下面那段友好的中文提示。所以这里把调用夹在 try/catch 里，
#    并把两个偏好变量临时都降下来（用完**原样恢复**）—— 失败与否一律由我们
#    自己查 $LASTEXITCODE 判定，保证任何情况下都只由自己的提示 + 非 0 退出码收场。
function Invoke-NativeSafe {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [string[]]$ArgList = @(),
        # 探测用：把 stdout/stderr 一起收进返回值，别把噪音直接打给同学
        [switch]$Capture
    )

    # 这个变量只在 PowerShell 7.3+ 才有；旧版（含 Windows PowerShell 5.1）连名字都没有。
    $HasNativePref = $null -ne (Get-Variable -Name 'PSNativeCommandUseErrorActionPreference' -ErrorAction SilentlyContinue)
    $OldNativePref = $null
    if ($HasNativePref) {
        $OldNativePref = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }
    # 调用原生命令期间把 EAP 降到 'Continue'：否则 5.1 下 stderr 会变成终止性错误，
    # 真退出码就传不出来了（本函数末尾 finally 会恢复成原来的值）。
    $OldEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    try {
        if ($Capture) {
            $Out = & $Exe @ArgList 2>&1
            $Code = $LASTEXITCODE
            if ($null -eq $Code) { $Code = 0 }
            return [pscustomobject]@{ Code = $Code; Output = (($Out | Out-String).Trim()) }
        }
        # ⚠️ 这里必须 `| Out-Host`：函数体内的原生命令 stdout 会**进入函数的输出流**，
        #    被调用方的 `$Run = Invoke-NativeSafe ...` 赋值吞掉 —— 同学就看不到
        #    gen_project.py 打印的"将写入…/wrote …"了。Out-Host 直接打到控制台。
        & $Exe @ArgList | Out-Host
        $Code = $LASTEXITCODE
        if ($null -eq $Code) { $Code = 0 }
        return [pscustomobject]@{ Code = $Code; Output = '' }
    } catch {
        # 兜底：宿主仍然抛了 NativeCommandError（或命令根本启动不了）时，
        # 只把"失败"这件事用非 0 退出码交回调用方，不往外冒英文异常。
        return [pscustomobject]@{ Code = 1; Output = '' }
    } finally {
        $ErrorActionPreference = $OldEap
        if ($HasNativePref) { $PSNativeCommandUseErrorActionPreference = $OldNativePref }
    }
}

# 仓库根 = 本脚本所在目录（scripts/）的上一级。
# 用 $PSScriptRoot 而不是当前目录，这样**从任意目录**调用都能工作。
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# 顶层实体名：给了参数就用参数当顶层实体名；否则用游戏本体 puzzle_top
# （gen_project.py 自己的默认值是 board_test_top，那是板级自检，不是游戏）。
if ($args.Count -ge 1 -and "$($args[0])".Trim() -ne '') {
    $Top = "$($args[0])".Trim()
} else {
    $Top = 'puzzle_top'
}

Write-Host '=============================================================='
Write-Host " bootstrap : 仓库根 = $Root"
Write-Host " 顶层实体  : $Top"
Write-Host '=============================================================='

# ---- 检查 1：找可用的 Python 3（python → py -3 两级回退）------------------
# ⚠️ 候选按「可执行文件 + 前置参数」成对保存：`py` 必须带 `-3` 才能锁定 Python 3，
#    调用时展开成 `& $Exe @Pre scripts/gen_project.py <顶层实体>`，
#    也就是命令行上的 `py -3 scripts/gen_project.py puzzle_top`。
$Candidates = @(
    [pscustomobject]@{ Exe = 'python'; Pre = @() },
    [pscustomobject]@{ Exe = 'py';     Pre = @('-3') }
)

$PyExe = $null
$PyPre = @()
$PyVer = ''
foreach ($C in $Candidates) {
    if (-not (Get-Command $C.Exe -ErrorAction SilentlyContinue)) { continue }

    # 名字找得到还不够：微软商店的占位程序也叫 python.exe，但一跑就返回 9009。
    # 所以**真跑一次 --version** 才算数（退出码 0 且版本串里有 Python 3）。
    $Probe = Invoke-NativeSafe -Exe $C.Exe -ArgList (@($C.Pre) + @('--version')) -Capture
    if ($Probe.Code -eq 0 -and "$($Probe.Output)" -match 'Python 3') {
        $PyExe = $C.Exe
        $PyPre = @($C.Pre)
        $PyVer = "$($Probe.Output)".Trim()
        break
    }
}

if (-not $PyExe) {
    Write-Host ''
    Write-Host '错误：找不到可用的 Python 3（python 与 py -3 都试过了）。' -ForegroundColor Red
    Write-Host '      请先安装 Python 3（≥3.8），**安装时勾选 "Add Python to PATH"**，'
    Write-Host '      然后**重新打开一个终端**再跑本脚本。'
    Write-Host '      验证方法：在终端里执行 python --version 或 py -3 --version，应显示 Python 3.x。'
    Write-Host '      ⚠️ 若提示 "Python was not found" 之类并指向微软商店，那说明装的是'
    Write-Host '         商店的**占位程序**：到「设置 → 应用 → 高级应用设置 → 应用执行别名」'
    Write-Host '         把 python.exe / python3.exe 两个别名关掉，或者改用 py -3。'
    exit 1
}
Write-Host " 已找到 Python : $(Get-Command $PyExe | Select-Object -ExpandProperty Source)  [$PyVer]"
# 打印**实际**要跑的命令行：走了 py -3 回退时，这里能一眼看出来（不是写死的 python）。
$PyCmd = (@($PyExe) + @($PyPre) + @('scripts/gen_project.py', $Top)) -join ' '
Write-Host " 将要执行  : $PyCmd"

# ---- 调用生成脚本（在仓库根下执行，相对路径才成立）-------------------
$Run = Invoke-NativeSafe -Exe $PyExe -ArgList (@($PyPre) + @('scripts/gen_project.py', $Top))
$Code = $Run.Code

# ---- 检查 2：把 gen_project 的退出码**原样透传** -----------------------
if ($Code -ne 0) {
    Write-Host ''
    Write-Host "错误：gen_project.py 失败（退出码 $Code），Quartus 工程没有生成。" -ForegroundColor Red
    Write-Host '      常见原因：'
    Write-Host '        · 这个 python 是 Microsoft Store 的占位程序（提示 "Python was not found"）；'
    Write-Host '        · 顶层实体名拼错（可选值见 scripts/gen_project.py 的 TOP_PORTS）。'
    exit $Code
}

# ---- 成功：直接打印下一步，省掉"接下来干嘛"的疑问 ---------------------
Write-Host ''
Write-Host '下一步：' -ForegroundColor Green
Write-Host '  1) 打开工程 : quartus\puzzle.qpf（Quartus II 9.1 -> File -> Open Project）'
Write-Host '  2) 编译     : quartus_sh.exe -t scripts\build.tcl'
Write-Host '                （quartus_sh.exe 在 Quartus 安装目录的 bin\ 下；'
Write-Host '                  本脚本不写死安装路径，请用完整路径或把它加进 PATH）'
Write-Host '  3) 烧录     : quartus_pgm.exe -c "USB-Blaster [USB-0]" -m jtag -o "p;quartus\output_files\puzzle.pof"'
Write-Host '                （先在 Quartus 里编译出 .pof；也可以到 quartus\output_files 下执行）'
