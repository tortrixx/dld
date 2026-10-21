# Windows Quartus II 实际编译截图与报告更新实操交接指南

本文档专为**切换至 Windows 电脑后使用 Quartus II 软件获得真实板级资源编译截图，并一键回填到实验报告**而编写。

---

## 一、为什么需要使用真实的 Quartus 编译截图？

按照《数字电路与逻辑设计实验》课程评分标准，报告第四部分**“实际实现功能说明及资源利用情况 (5分)”**具有严格的硬性核查要求：
1. **器件型号与容量必须真实对应**：报告必须呈现目标芯片 `Altera MAX II EPM1270T144C5`（1,270 个逻辑单元 LE，127 个 LAB，无片上 RAM）；
2. **逻辑资源与引脚利用率可信度**：必须实测展示 `Total logic elements`（LE 占用数及百分比）与 `Total pins`（用户引脚占用数）；
3. **静态时序收敛证明**：必须给出在 50 MHz 晶振约束下的 `Fmax`（最高工作频率）与建立/保持时间裕量（Worst-case Slack $\ge 0.000$ ns）。

使用 Windows 下 Quartus II 软件实际编译出来的原图，具有不可辩驳的工程实测可信度，能确保这 5 分评分完全不被挑剔扣减。

---

## 二、Windows 下 Quartus II 编译实操流程

### 步骤 1：打开工程
1. 在 Windows 电脑上启动 **Quartus II**（推荐版本：Quartus II 9.1 或 13.0sp1 Web Edition）；
2. 点击菜单栏 **`File` -> `Open Project...`**；
3. 定位并选择本仓库目录下的工程文件：
   ```text
   dld\quartus\puzzle.qpf
   ```
4. 打开后，确认左上角 `Project Navigator` 中显示的顶层实体为 **`puzzle_top`**，目标器件为 **`EPM1270T144C5`**。

### 步骤 2：执行全编译 (Full Compilation)
1. 点击顶部菜单栏 **`Processing` -> `Start Compilation`**（或直接按快捷键 **`Ctrl + L`**）；
2. 观察底部 `Processing` 任务栏，等待以下 4 项全流程完成：
   - `Analysis & Synthesis` (分析与综合)
   - `Fitter (Device Positioning & Routing)` (布局布线)
   - `Assembler (Generate programming files)` (生成固件 `.pof`)
   - `TimeQuest Timing Analyzer` (静态时序分析)
3. 编译完成后，状态栏将显示：**`Quartus II ... was successful. 0 errors, ... warnings`**。

---

## 三、截取两张核心报告截图

在 Quartus II 界面左侧或弹出的 **`Compilation Report`** 窗口中截取以下两张图：

### 截图 ①：资源利用率总览（覆盖替换：`GUI-编译-面积.png`）
1. 在 `Compilation Report` 树状目录中，点击顶层的 **`Flow Summary`** 或 **`Fitter` -> `Summary`**；
2. **截图范围要求**：
   - 包含上方的 **Device: `EPM1270T144C5`** 和 **Timing Models: Final**；
   - 完整截取表格中的核心指标：
     - `Total logic elements`（例如：1,048 / 1,270 (83%)）
     - `Total pins`（例如：38 / 116 (33%)）
     - `Total virtual pins`（0）
     - `UFM blocks`（0 / 1 (0%)）
3. **保存路径**：直接保存/覆盖为：
   ```text
   docs\report\GUI-编译-面积.png
   ```

### 截图 ②：静态时序分析报告（覆盖替换：`GUI-编译-时序.png`）
1. 在 `Compilation Report` 树状目录中，展开 **`TimeQuest Timing Analyzer`**（若为经典时序分析器则为 `Classic Timing Analyzer`）；
2. 点击 **`Multicorner Timing Analysis Summary`** 或 **`Fmax Summary`**；
3. **截图范围要求**：
   - 截取时钟网络 `clk_50m`（或 `clk`）的 **Fmax** 汇总行（例如：`68.52 MHz` 或 `54.27 MHz`，需 $\ge 50.00 \text{ MHz}$）；
   - 截取 **Worst-case Slack**（`Setup: +5.421 ns`，`Hold: +0.892 ns`，显示绿色 `PASSED`）；
4. **保存路径**：直接保存/覆盖为：
   ```text
   docs\report\GUI-编译-时序.png
   ```

---

## 四、一键重新生成最终实验报告

当您在 Windows 电脑上将上述两张新截图放入 `docs\report\` 目录后，无需手动调排版，直接执行以下任一方式即可一键刷新 PDF 和 Word：

### 方式 1：使用 Typst 命令行（最快捷）
若 Windows 上安装了 `typst`（可通过 `winget install --id Typst.Typst` 安装）：
```powershell
cd docs\report
typst compile 实验报告_题目4_简易拼图游戏.typ 实验报告_题目4_简易拼图游戏.pdf
```

### 方式 2：使用 Python 脚本生成全套（PDF + Word + Markdown）
若已激活 Python 环境：
```powershell
python scratch\build_full_academic_report.py
python scratch\generate_docx_md.py
```
此时 `实验报告_题目4_简易拼图游戏.pdf` 和 `实验报告_题目4_简易拼图游戏.docx` 中的第 4 节截图将自动更新为您刚刚截取的最新真实图片！

---

## 五、代码完整性安全声明

- **零代码污染原则**：整个报告编制、排版调优与文档生成过程中，**未修改 `rtl/` 目录下的任何一行 VHDL 逻辑代码，未修改 `sim/` 下的任何仿真激励，未修改 `quartus/` 下的硬件引脚与时序约束**；
- 本地 `git status` 检查始终保持工作区干净（除 `docs/report/` 交付文档目录外，零 untracked、零 modified）。切换至 Windows 电脑后可直接使用 Git 拉取或拷贝，固件二进制特征值（Hash / POF Checksum）与硬件烧录 100% 保持严格一致！
