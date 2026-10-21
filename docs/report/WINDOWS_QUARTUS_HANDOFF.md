# Windows Quartus II 实测编译截图与报告重建交接指南

> **状态（2026-10-21）：本文档描述的流程已在本机执行完毕。** 报告第四部分的两张编译报告截图
> 已经是 **Quartus II 9.1 的软件界面现场截图**（`PrintWindow` 抓窗口位图后按"报告树 + 报告正文"
> 裁剪，未做任何重绘、补写或贴字），PDF / DOCX / MD 三种交付物与截图数字逐项一致。

---

## 一、为什么必须用真实的 Quartus 编译截图

按照《数字电路与逻辑设计实验》课程评分标准，报告第四部分 **"实际实现功能说明及资源利用情况（5 分）"**
有硬性核查要求：

1. **器件型号与容量必须真实对应**：目标芯片 `Altera MAX II EPM1270T144C5`（1,270 个逻辑单元 LE，
   127 个 LAB，无片上 RAM）；
2. **逻辑资源与引脚利用率可信度**：实测展示 `Total logic elements`（LE 占用数及百分比）与
   `Total pins`（用户引脚占用数）；
3. **静态时序收敛证明**：50 MHz 晶振约束下的 `Fmax` 与建立/保持时间裕量（Worst-case Slack ≥ 0.000 ns）。

用 Windows 下 Quartus II 实际编译出来的原图具有不可辩驳的工程实测可信度。**加工过的"仿真界面图"
（自己补行、合并表格、加说明面板）一旦被追问就是诚信问题，比数字写错严重得多**，因此本仓库只接受真实截屏。

---

## 二、本机的实测数据（唯一事实源）

`quartus_sh -t scripts/build.tcl`（map → fit → asm → tan → sta 全流程）清洁重编译，
**0 error / 16 warning**，产出：

| 项目 | 实测值 | 出处 |
|---|---|---|
| Fitter Status | `Successful - Wed Oct 21 12:38:34 2026` | `output_files/puzzle.fit.summary` |
| Quartus II 版本 | `9.1 Build 222 10/21/2009 SJ Full Version` | 同上 |
| 器件 / 时序模型 | `EPM1270T144C5` / `Final` | 同上 |
| Total logic elements | **1,264 / 1,270（`fit.rpt` 显示 100%，实际 99.53%，余 6 LE）** | 同上 |
| Total LABs | **127 / 127（100%）** | `puzzle.fit.rpt` · `Fitter Resource Usage Summary` |
| Total pins | **52 / 116（45%）** | `puzzle.fit.summary` |
| Total virtual pins / UFM | `0` / `0 / 1 (0%)` | 同上 |
| Fmax（Slow 模型） | **54.27 MHz**（Restricted Fmax 同为 54.27 MHz） | `puzzle.sta.rpt` · `Fmax Summary` |
| Setup slack | **+1.572 ns**（TNS 0.000） | `puzzle.sta.rpt` · `Setup Summary` |
| Hold slack | **+1.078 ns**（TNS 0.000） | `puzzle.sta.rpt` · `Hold Summary` |
| Min pulse width | **+9.734 ns**（TNS 0.000） | `puzzle.sta.rpt` · `Minimum Pulse Width Summary` |
| 固件 | `puzzle.pof` 27,312 字节，sha256 `cc3c69b3419f…`（与入库 `build_provenance.json` **逐字节一致**） | `build_provenance.json` |
| 装箱参数 | `SEED = 8` | `quartus/puzzle.qsf` |

⚠️ **`fit.rpt` 的百分比是"以 1,270 为基数四舍五入"**：1,264/1,270 = 99.53%，Quartus 打印 `100 %`。
引用时写"1,264 / 1,270（99.53%，fitter 显示 100%）"，不要直接抄 100% 当余量，也不要写成 82.52% 之类的旧值。

---

## 三、两张截图是怎么拍出来的（可复现）

前提：Quartus II 9.1 已装在本机（`C:\QuartusII91\QuartusII91\quartus\bin\quartus.exe`），
且 `quartus/output_files/` 里已有一次成功的编译报告（见 §二）。

1. **命令行先做一次清洁重编译**（这一步保证报告数据库与 `.rpt` 都是本次产物）：
   ```powershell
   cd quartus
   C:\QuartusII91\QuartusII91\quartus\bin\quartus_sh.exe -t ..\scripts\build.tcl
   ```
   ⚠️ 必须包含 `sta` 这一步（`build.tcl` 第 5 步）：经典的 `quartus_tan` **不读** `.sdc`，
   只有 TimeQuest 才按 `create_clock -period 20.000` 报出 Fmax / setup / hold 裕量。
   ⚠️ **不要**在 `puzzle.qsf` 里加 `USE_TIMEQUEST_TIMING_ANALYZER ON` 再走 GUI 一键编译 ——
   时序驱动 fitter 的行为会改变（实测 setup slack 变 +0.577 ns、`.pof` 哈希变为 `1cc9fb11…`），
   与入库固件证据链脱钩。本仓库的正式流程始终是 `build.tcl`。
2. **开 GUI 并打开编译报告**：`quartus.exe quartus\puzzle.qpf` → 菜单
   `Processing → Compilation Report`（`Ctrl+R`）。报告窗标题变为
   `Compilation Report - Flow Summary`。
3. **截图①（资源利用率）**：左侧报告树点 `Flow Summary`，抓窗口位图，裁掉窗口边框/标题栏
   （标题栏含本机绝对路径与用户名，**绝不能入图**），只保留"报告树 + Flow Summary 正文"，
   存为 `docs/report/GUI-编译-面积.png`。
4. **截图②（静态时序）**：展开报告树的 `TimeQuest Timing Analyzer`（点节点前的 `+`），
   双击 `Fmax Summary`，同样裁剪存为 `docs/report/GUI-编译-时序.png`。
   ⚠️ 三张姊妹页面 `Setup Summary` / `Hold Summary` / `Minimum Pulse Width Summary` 里的
   `Slack` 分别是 1.572 / 1.078 / 9.734（TNS 均 0.000）；一张截图装不下三张表时，
   请在正文写清"读数来自这三个页面"，**不要把三张表合并成一张**。
5. **裁剪口径**：只保留报告面板（左报告树 + 右报告正文）。窗口标题栏、菜单栏、Project Navigator、
   Tasks、Messages、状态栏一律裁掉 —— 既避免泄漏本机路径，也让纸面字号足够大
   （当前成品：面积图 1010×470、时序图 700×430，PDF 内约 7 pt 字高）。

拍的辅助脚本（一键抓窗口位图 + 按 `MDIClient` 裁剪）见 `scripts/shoot_vwf.ps1`，
它给仿真波形用的同一套 Win32 封装（`PrintWindow` / 附加线程抢前台 / 对话框轮询）可直接复用。

---

## 四、重新生成三件交付物

### 4.1 PDF（Typst）

本机已把 Typst 0.15.1 解压到 `.tmp/typst/`（该目录被 `.gitignore` 覆盖，不入库）。构建：

```powershell
cd <仓库根>
.tmp\typst\bin\typst-x86_64-pc-windows-msvc\typst.exe compile --root . `
  "docs\report\实验报告_题目4_简易拼图游戏.typ" `
  "docs\report\实验报告_题目4_简易拼图游戏.pdf"
```

模板 `template.typ` 的字体栈是跨平台的：macOS 优先 `Songti SC / Heiti SC / Hiragino Sans GB / Menlo`，
Windows 回退 `Noto Serif SC / Noto Sans SC / Consolas`，因此两边都能构建；
构建时出现的 `unknown font family: songti sc` 只是"本机没有该字体、已按栈回退"的**正常警告**。

### 4.2 DOCX 与 MD

`.docx` 与 `.md` 由同一次内容修订同步产出（图片按 sha256 与 `docs/report/*.png` 逐一核对，
表格/正文数字与 PDF 逐字对齐）。修改 `.typ` 文案后，务必同步这两份，避免出现
"PDF 说 1,264、DOCX 说 1,048" 这类图文自相矛盾。

### 4.3 重建后必须自检的三条

1. **数字自洽**：`python scripts/audit_evidence.py` 必须 `0 FAIL`（当前 `0 FAIL / 1 WARN / 30 OK`，
   唯一 WARN 是"LAB 已满 127/127"，那是事实）；
2. **截图与表格对得上**：PDF 里 §4.2 的表格每一行都要能在两张截图或 `puzzle.sta.rpt` 里找到出处；
3. **不漏本机路径**：`git grep` 检索本机用户目录前缀应为 0 命中（PNG 是二进制，靠人工裁剪保证）。

---

## 五、代码与工程完整性声明

- **零代码污染**：报告编制、排版与截图过程中**未修改 `rtl/` 下任何一行 VHDL 逻辑，未修改 `sim/` 下任何
  仿真激励，未修改 `quartus/puzzle.sdc` 时序约束与任何引脚约束**；
- `quartus/output_files/` 全部为可重新生成的编译产物（`.gitignore` 已覆盖），本轮的清洁重编译
  在数值上**逐项复现**上一版：LE 1,264、LAB 127/127、pins 52/116、Fmax 54.27 MHz、
  setup +1.572 ns、hold +1.078 ns、`puzzle.pof` sha256 `cc3c69b3419f…` **逐字节相同**；
- 因此固件二进制特征值与硬件烧录结果保持严格一致，报告里的每一个资源/时序数字都可回溯到
  `quartus/build_provenance.json` 与 `quartus/output_files/*.rpt`。
