# `docs/图/` —— 图目录索引 + **Quartus GUI 实测仿真图拍摄流程**

> 这份文件是 `docs/图/` 的**唯一清单所有者**：`docs/03-仿真验证方案.md` §3.1 与
> `HANDOFF.md` §4.1 都只写"见 `docs/图/README.md`"，具体文件名与状态以本文件为准。

---

## 0. 先分清两类图（**这一条最容易出错**）

| 类别 | 文件名 | 怎么来的 | 能不能当"实测仿真图"交 |
|---|---|---|---|
| ⭐ **Quartus GUI 实测截图** | `GUI-<模块>.png` | 在 **Quartus II 波形编辑器界面**里打开 `sim/<模块>.vwf` 后截屏 | ✅ **报告里只能用这一组** |
| 脚本渲染的辅助波形 | `SIM-<模块>.svg` | `scripts/sim.py` 解析 `.vwf` 后**用 Python 自己画**的矢量图 | ❌ 不是 Quartus 界面，**不能当实测截图** |
| 板子/画面照片 | `结算画面-预览.png` 等 | 上板实测或设计稿 | 按用途单独说明 |

**为什么必须有 GUI 截图**：`SIM-*.svg` 的像素是脚本画的，别人无法确认它没有被脚本"美化"；
而 Quartus 界面截图里带着**菜单栏、工程名、节点名列表、时间刻度**，是软件本身渲染的，可信度不同。
两者**不是**二选一 —— `SIM-*.svg` 留作"逐点比对"的辅助证据（`sim/rounds/*.md` 会链它），
报告正文的仿真波形图用 `GUI-*.png`。

### 0.1 ⚠️ 截图前必读：**一定要把窗口标题栏裁掉**

Quartus 的标题栏写的是**完整工程路径**，里面带**你的 Windows 用户名**：

```
Quartus II - C:/Users/<你的用户名>/Desktop/dld/quartus/puzzle - puzzle - [../sim/clk_gen.vwf]
```

把它截进图里，就等于把**本机绝对路径 + 用户名**发到公开仓库 —— 而本项目的既有纪律是
**"全仓库不出现作者本机绝对路径"**（`HANDOFF.md` §0；文本文件已经 `git grep` 0 命中）。
⚠️ 文本文件查得到，**PNG 是二进制，`git grep -I` 看不见** —— 所以这一条**只能靠人手动保证**。

**做法**：只截菜单栏以下的部分，或拍完把顶部标题栏那一条约 33 像素裁掉。
裁完之后菜单栏、工程名（Project Navigator 里的 `MAXII: EPM1270T144C5` / `puzzle_top`）、
节点名列表、波形网格、时间刻度**都还在**，一眼仍能看出是 Quartus 界面，不影响可信度。

`docs/图/GUI-clk_gen.png` 那张样例就是**裁掉标题栏之后**的样子，可以直接对照。

---

## 1. 为什么"打开 `.vwf` 就有波形"——不用重跑仿真

本工程没有 ModelSim，只有 Quartus II 9.1 内置仿真器（`scripts/vwf.py` 开头有完整说明）。
它的结果是**回写进激励文件本身**的：

```
quartus_sim <工程> --mode=functional --overwrite_waveform=on
        ↓
把每个节点算出来的波形写回 sim/<模块>.vwf 的 TRANSITION_LIST
```

所以 `sim/<模块>.vwf` **既是激励也是结果**，是入库的交付物之一（12 个模块各一份）。
实测抽查：`sim/buzzer_ctrl.vwf` 里输出 `o_buzz` 有 **1455 次跳变**、
`pre_cnt[0]` 有 **336 466 次**跳变 —— 里面确实是真跑出来的波形，不是空白模板。

⇒ **拍图不需要重新编译、不需要重新仿真**，打开就有。

---

## 2. 清单与当前状态

目标：**12 张** `GUI-<模块>.png`，一张一个模块。

| # | 目标文件名 | 打开的源文件 | 这张图在报告里证明什么 | 状态 |
|---|---|---|---|---|
| 1 | `GUI-clk_gen.png` | `sim/clk_gen.vwf` | 分频链（1 kHz → 200 Hz → 4 Hz / 2 Hz / 1 Hz / 40 Hz）与按键消抖计数 | ✅ 已有样例 |
| 2 | `GUI-keypad_scan.png` | `sim/keypad_scan.vwf` | 4×4 键盘扫描四状态机 + 消抖 + 按键按下/释放 | ⬜ 待拍 |
| 3 | `GUI-seg_scan.png` | `sim/seg_scan.vwf` | 数码管位选/段选扫描与 5 个字母的段形 | ⬜ 待拍 |
| 4 | `GUI-dot_matrix_scan.png` | `sim/dot_matrix_scan.vwf` | 8×8 点阵行扫描（125 Hz）与行序 | ⬜ 待拍 |
| 5 | `GUI-rng_lfsr.png` | `sim/rng_lfsr.vwf` | LFSR 伪随机序列（x⁸+x⁶+x⁵+x⁴+1，周期 255） | ⬜ 待拍 |
| 6 | `GUI-pattern_rom.png` | `sim/pattern_rom.vwf` | 图案库按 `i_pat` 查表输出 | ⬜ 待拍 |
| 7 | `GUI-piece_rom.png` | `sim/piece_rom.vwf` | 零片形状库按（形状/朝向）查表输出 | ⬜ 待拍 |
| 8 | `GUI-disp_format.png` | `sim/disp_format.vwf` | 显示格式转换（十进制/十六进制、倒计时编码） | ⬜ 待拍 |
| 9 | `GUI-game_fsm.png` | `sim/game_fsm.vwf` | 主状态机 S_IDLE→预览→对局→胜负 的迁移与计时 | ⬜ 待拍 |
| 10 | `GUI-puzzle_ctrl.png` | `sim/puzzle_ctrl.vwf` | 拼图引擎：重叠判定 / 选中锁定 / 旋转 / 整帧判据 | ⬜ 待拍 |
| 11 | `GUI-buzzer_ctrl.png` | `sim/buzzer_ctrl.vwf` | 音效：音高表查表 + 方波计数 + 三关 BGM 乐句 | ⬜ 待拍 |
| 12 | `GUI-puzzle_top.png` | `sim/puzzle_top.vwf` | 整机：三关流程 + 告急幽灵（绿 + 2 Hz 闪） | ⬜ 待拍 |

> 每张图对应的**断言明细**在 `sim/rounds/<模块>/rNN.json`（机读）与 `rNN.md`（人看），
> 逐模块的"当前轮次 + 条数"总表在 `docs/03-仿真验证方案.md` §2 / §4。

---

## 3. 操作流程 A：手动拍（**推荐**，12 张约 20 分钟）

### 3.1 准备（只做一次）

1. **打开 Quartus II 9.1**
   - 开始菜单 → `Quartus II 9.1`；或直接运行
     `C:\QuartusII91\QuartusII91\quartus\bin\quartus.exe`
2. **打开本工程**：`File → Open Project…`（快捷键 **Ctrl+J**）→ 选
   `<仓库>\quartus\puzzle.qpf`（也可以直接在资源管理器里双击这个 `.qpf`）
3. **关掉 `Tips & Tricks` 浮窗**（右上角 `×`），否则它挡住半个屏幕
4. **把 Quartus 窗口最大化**
5. **让波形编辑器占满主区**（关键，能让一屏多显示 3 倍信号）
   - 第一次打开任意 `.vwf` 之后，波形编辑器是**浮动的**小窗；
   - **双击它的标题栏**，它会停靠（dock）进主区，成为一大块；
   - 之后每次打开别的 `.vwf` 都复用这块位置。
6. （可选）**多腾出 ~200 像素高度**：`View → Utility Windows → Messages` 取消勾选，
   把底部消息窗关掉。

### 3.2 每个模块重复这 6 步

1. **`File → Open…`（Ctrl+O）**
2. 定位到 `<仓库>\sim\`，双击 **`<模块>.vwf`**
   - ⚠️ 第一次打开任意 `.vwf` 时 Quartus 会弹一条提示：
     *"Future versions of the Quartus II software will not support the Quartus II Simulator…"*
     → 勾上 **`Don't show this again`** → 点 **OK**。之后不再弹。
3. **`View → Fit in Window`（快捷键 `Ctrl+W`）** ← **最容易漏的一步**
   - 不按它，时间轴默认只显示最前面**几十纳秒**，波形挤成一片黑，什么也看不出来；
   - 按完之后整段仿真时间（如 `buzzer_ctrl` 的 0 ~ 6.7 ms）铺满窗口。
4. （可选）在左侧**信号名列表**里上下滚动，把你报告里要讲的那几行滚进可视区
   - 总线是**折叠**的（如 `i_sel`、`pre_cnt`）；点名字左边的小方块可以展开看每一位。
   - **不需要手动添加节点**：测试台要观察的中间信号（`OBSERVE` 里那些 `BURIED` 节点，
     如 `buzzer_ctrl` 的 `pre_cnt` / `cnt` / `tone_sel` / `on_now`）**已经写进 `.vwf` 的
     节点表**，打开就在列表里。
5. **截图**（抓活动窗口，别抓全屏；**拍完把标题栏裁掉**，见 §0.1）
   - 推荐：**`Alt + PrintScreen`** → 打开"画图" → `Ctrl+V` → **用选择框只框菜单栏以下的部分**
     → `Ctrl+Shift+X` 裁剪 → 另存为 PNG
   - 或：**`Win + Shift + S`** 框选（**从菜单栏上沿开始框，别框到标题栏**）→ 到画图里 `Ctrl+V` → 另存为 PNG
   - ❌ 不要用单独的 `PrintScreen`（全屏）：会把桌面、浏览器窗口一起拍进去。
6. **另存为 `<仓库>\docs\图\GUI-<模块>.png`** —— 文件名必须与 §2 表里一致
   （模块名、下划线都要对；`docs/03` §3.1 是按 `GUI-*.png` 通配引用的）

### 3.3 想只拍某一段时间（可选）

`View → Zoom…` 会弹一个对话框，可以直接填 **Start / End** 时间；填完点 OK，
时间轴就固定到那一段。适合"只想证明幽灵 2 Hz 闪烁周期"这类细节图。

---

## 4. 操作流程 B：一键脚本（可选，12 张约 2 分钟）

仓库里已经带了一个把上面流程自动化掉的脚本：

```powershell
# 在仓库根目录
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\shoot_vwf.ps1
```

它会：启动（或复用已开着的）Quartus GUI → 逐个打开 `sim/<模块>.vwf` →
按 `Ctrl+W` → 用 `PrintWindow` 抓**主窗口位图** → 存成 `docs\图\GUI-<模块>.png`。

常用参数：

```powershell
# 只拍两个模块
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\shoot_vwf.ps1 -Modules buzzer_ctrl,clk_gen
# 拍完把 Quartus 关掉
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\shoot_vwf.ps1 -CloseQuartus
```

**为什么它比手点更稳**：抓的是**窗口位图**（`PrintWindow`）而不是屏幕像素 ——
窗口被别的窗口挡住、甚至被拖到屏幕外都不影响结果，也绝不会把桌面上的东西拍进去。
**它默认会把顶部 33 像素（标题栏，含本机用户名）裁掉**（见 §0.1）；
确实想要完整窗口就连标题栏一起留，加 `-CropTop 0`。

**已知的两点**（不是故障）：

* 脚本可能打印 `!! <模块>：波形编辑器没有切到该文件` —— 这是**误报**：新版把多个 `.vwf`
  开成**标签页**，而脚本比的是面板标题（停留在第一个标签的名字），实际已经切过去了。
  拍完自己扫一眼图确认即可。
* 脚本会把 Quartus 窗口挪到屏幕左上角并调整大小，拍完恢复；运行期间会**抢桌面焦点**，
  建议别在它跑的时候打字。

---

## 5. 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 波形挤成一片黑，看不出周期 | 漏了 `Ctrl+W`（Fit in Window） | 补按 `Ctrl+W` |
| 图里出现桌面/浏览器 | 用了全屏 `PrintScreen` | 改用 `Alt+PrintScreen` 或 `Win+Shift+S` |
| 图里出现 `C:/Users/<你的用户名>/...` | 标题栏没裁掉（**会泄露本机路径与用户名**） | 按 §0.1 裁掉顶部标题栏；用脚本则默认已裁 |
| `docs/03` §3.1 的通配匹配不到图 | 文件名写错（大小写/下划线/模块名） | 严格按 §2 表的文件名 |
| 想看的内部信号找不到 | 总线折叠，或该模块节点太多需滚动 | 点小方块展开；或在信号列表里滚动 |
| 打开 `.vwf` 后提示"不支持内置仿真器" | Quartus 9.1 的固定提示 | 勾 `Don't show this again` → OK |
| 想重拍某个模块 | —— | 重复 §3.2 的 6 步，直接覆盖同名 PNG |

---

## 6. 拍完之后

1. 把 §2 表格里的状态从 `⬜ 待拍` 改成 `✅`（**本文件是清单所有者，只在这里改**）；
2. 确认 12 个文件名一个不缺：
   ```powershell
   Get-ChildItem docs\图\GUI-*.png | Select-Object Name, Length
   ```
3. 提交：
   ```powershell
   git add docs/图/GUI-*.png docs/图/README.md
   git commit -m "docs(fig): 补 12 张 Quartus GUI 实测仿真波形截图"
   ```
   ⚠️ 图是二进制，`.gitattributes` 里已有 `*.png binary`，不会被行尾转换。
