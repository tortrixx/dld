# -*- coding: utf-8 -*-
"""tb_puzzle_top.py —— 整机场景仿真（B1 自检 → B2 待机 → B4 预览 → B5 散落 → B6 选择）

【这一轮要回答什么】
    前面 11 个模块各自验过之后，最后要回答的是**整机**问题：
    「把按键真的按下去，整条链路会不会按需求走完？」
      · B1  SW7=1 → 点阵全黄 2 Hz 闪 + 8 位数码管全显 "8"
      · B2  2 秒后待机：点阵全灭、DISP7='5'、DISP0='1'、其余全灭
      · B4  按【开始】→ 点阵显示完整图 4-1（第 2~5 行 x 第 2~4 列 = 12 格）、DISP7 倒计时
      · B5  预览 5 秒后散落：点阵出现零片、DISP4:DISP3 出现 30 秒倒计时
      · B6  按【选择】→ 绿色零片切换（选中的零片变绿）
      · B1  SW7=0 → 全部不显示

【怎么"按"矩阵键盘】
    4x4 矩阵的扫描相序是确定的，所以**按下某键时行线该在什么时候为低**可以精确算出来
    （与 tb_keypad_scan 同一套模型）：SETTLE 相四列全低 → 行落下；第 c 相只有第 c 列
    为低 → 行落下。本 tb 就按这个物理模型生成 kp_row 波形，而不是"随便给个电平"。
    这样按键是**真的被扫描器识别**，而不是绕过输入通道。

【时间压缩：为什么改 CLK_HZ（RTL_PATCHES）】
    真实 50 MHz 下 1 秒 = 5x10^7 拍，跑完"自检 2 s + 预览 5 s + 对局"要上亿拍，仿真
    不可行。所以把 `puzzle_pkg.CLK_HZ` 从 50_000_000 改成 **80_000**（**只作用于
    .tmp 隔离工程的副本**，仓库 rtl/ 不动；sim.py 会把补丁记进轮次记录）。
    关键是**分频比一个都没改**：200 Hz 节拍仍是 5 个 1 kHz 节拍、1 Hz 仍是 200 个
    200 Hz 节拍、2 Hz 仍是 1 Hz 的一半 —— 所以"自检 2 s / 预览 5 s / 限时 30 s"
    这些**需求里的秒数**一个字都没动，只是每"秒"的时钟数变少了。这一点在断言里
    用**节拍数**而不是纳秒来判，避免"把压缩当成功能"。

【实测时间刻度（CLK_HZ=80000，时钟 20 ns）】
    tick_1k  = 80 拍 = 1.6 us      tick_200 = 400 拍 = 8 us
    tick_1hz = 1.6 ms（"1 秒"）    tick_2hz = 800 us（500 ms）    tick_4hz = 400 us（250 ms）
    ⚠️ ERR-038：**2 Hz 闪烁**是用 tick_4hz（250 ms）翻转出来的（半周期 400 us）；
       tick_2hz 只作音效节奏 —— 之前把 tick_2hz 当"2 Hz 半周期"是 2 倍记账错误。
    上电复位 ~16 us；矩阵扫描 SETTLE 拍在 32 + 16k us。
"""

import os

# ============================================================================
# 第二关**固定**图案（B10）+ 第三关**随机**图案（A2）+ 异形零片 —— 本 tb 的两种模式
#
#   ⚠️ 2026-10-09（第 12 工作阶段 / D2）：**第二关图案不再随机**，改成"自拟但固定"
#      （= PAT3 阶梯，见 rtl/puzzle_pkg.vhd 的 L2_FIXED_PAT）；"多种拼图图案随机选择"
#      移到**新增的第三关** —— 这正是提高要求 2 的原文"增加游戏关数，多种拼图图案随机选择"。
#      于是本 tb 的第三场景要**连过三关**：一关（图 4-1）→ 二关（固定 PAT3）→ 三关（随机）。
#
#   模式 A（默认，DLD_L3PAT 未设或 =0）：
#       随机源钉 0（见 RTL_PATCHES）→ 第三关锁存的 pat_sel = "00" → 第三关用**图案 0**
#       （= 4x4 方块"田"）。第二关恒为 PAT3（RTL 里写死，与随机源无关）。
#
#   模式 B（DLD_L3PAT=2）：
#       把顶层那条锁存语句补丁成 pat_sel <= "10" → 第三关换成**图案 2（S/Z 锯齿）**，
#       于是两份走法计划（第二关 PAT3 + 第三关 PAT2）都**端到端拼通**（绿对勾 + PASS）。
#       这是 A2 的关键证据："换一幅图案，游戏照样能玩通、判据照样成立"。
#       第三关四个图案的可铺性由 tb_pattern_rom（逐 (level,pat,row) 精确比对）与
#       scripts/check_geometry.py（逐图案只许平移的穷举可铺性）验证，不再重复跑整机。
#
#   零片本身：第二关/第三关都是**四块异形**（1x3 横条 3 格 / 1x2 竖条 2 格 /
#   J 形 5 格 / 六格块 6 格，共 16 格），每局位置随机、不能重叠。
#   走法计划由 .tmp/opt/solve_l2plan.py 用 A*（代价 = 按键次数）解出，
#   再由 scripts/check_plans.py 用引擎规则离线复核（零次被拒、并集 == 图案）。
#
#   用法：python scripts/sim.py run puzzle_top                  # 模式 A（第三关 = 田）
#         $env:DLD_L3PAT=2; python scripts/sim.py run puzzle_top # 模式 B（第三关 = S/Z）
#   （两种模式的轮次记录分别落在 sim/rounds/puzzle_top/rNN.json，
#     json 里的 rtl_patches 会如实记下模式 B 用的那处补丁。）
# ============================================================================
FORCE_PAT = int(os.environ.get("DLD_L3PAT", "0") or "0")
if FORCE_PAT not in (0, 2):
    raise SystemExit("✗ DLD_L3PAT 只支持 0（模式 A，第三关=田）或 2（模式 B，第三关=S/Z）")

CLK = 20.0
GRID_PERIOD = 10.0

# ============================================================================
# ⚠️ 2026-10-09 第 14 工作阶段：**零片初始朝向不再全 0**（提高要求 A4 变成通关必需）
#
#   用户上板反馈："旋转 90 度效果倒是有，但是旋转好像对游戏并没有什么影响，
#   不旋转也能成功通关。" → `rtl/puzzle_pkg.vhd` 新增 PIECE_ORI_INIT，
#   `puzzle_ctrl` 在散落时把四块零片设成这个朝向（块 0..3 = 1/1/2/2）；
#   `scripts/check_geometry.py` 穷举证明"保持初始朝向、只许平移"时**任何一幅图案
#   都铺不满**。
#
#   ⚠️ 下面的四份走法计划**不是**"老计划前面加一段朝向归零前缀"，而是用**带旋转的
#      A\***按新初态重新解出来的（解算器 `.tmp/opt/rot_astar2.py`）：
#        状态 = (锚点, 朝向, sel)，动作 = 移动 / **旋转** / 换零片，
#        代价 = **按键次数**（换零片要按 (k'-k) mod n 次【选择】），
#        终点 = 某个**精确铺法**（锚点 + 朝向）且并集逐格等于图案，取所有铺法里最短的。
#      前缀法能得到一条"走得通"的路，但**不是最少按键**（一关 35 vs 19、二关 51 vs 34），
#      而"最少按键"正是这些计划的历史解算目标（见 .tmp/opt/solve_l2plan.py）。
#      四份计划连同终点锚点都必须与 scripts/check_plans.py 里的**逐字一致**（守卫在那里）。
# ============================================================================

RTL_PATCHES = [("puzzle_pkg.vhd", "50_000_000", "80_000"),
               # 第三场景要按"哪一块会落到哪里"写出按键计划，所以把随机源钉成 0
               # （只作用于 .tmp 隔离工程）：rnd_val 恒 0 → 每块候选恒为 (0,0)
               # → 16 次重试后落到**确定性回退锚点**
               ("puzzle_pkg.vhd", 'x"5A"', 'x"00"')]
if FORCE_PAT != 0:
    # 模式 B：绕过 LFSR 采样，把**第三关**的图案下发下标钉在 FORCE_PAT。
    # ⚠️ 补丁只作用于 .tmp 隔离工程的副本，仓库 rtl/ 一个字节都不动（sim.py 保证）。
    RTL_PATCHES.append(("puzzle_top.vhd", "pat_sel <= rnd_val(1 downto 0);",
                        'pat_sel <= "%s";' % format(FORCE_PAT, "02b")))

# ---- 第二关图案库：tb **独立**用 8x8 ASCII 图描述期望图案（不抄 RTL 字面量，
#      否则就是把 RTL 复述一遍，抄错了也看不出来）--------------------------------
L2_ASCII = {
    0: ["........", "........", "..####..", "..####..",
        "..####..", "..####..", "........", "........"],   # 田 4x4 实心方块
    1: ["........", "........", "..###...", ".#####..",
        ".#####..", "..###...", "........", "........"],   # 十 胖十字
    2: ["........", "........", ".####...", "...####.",
        "...####.", ".####...", "........", "........"],   # S/Z 锯齿
    3: ["........", "........", ".####...", ".#####..",
        "..####..", "...###..", "........", "........"],   # 阶梯
}


def pat_rows(k):
    """图案第 k 幅的 8 行 8 位列掩码（bit = 8*行 + 列，bit0 = 左上角）。"""
    m = 0
    for r, line in enumerate(L2_ASCII[k]):
        for c, ch in enumerate(line):
            if ch == "#":
                m |= 1 << (8 * r + c)
    return [(m >> (8 * r)) & 0xFF for r in range(8)]

T200 = 8000.0                      # tick_200 周期 (ns)
# 第 0 轮扫描的 SETTLE 拍。上电复位在 14.4 us 释放，复位后的第一个 tick_200
# （16 us）把状态机从 SC_ALL_HIGH 推到 SC_ALL_LOW，第二个（24 us）进 SETTLE。
# 这个相位是实测校准的（探针读数 kp_col 第一次出现 0000 全低相在 24040 ns）。
S0 = 24000.0
ROUND = 16000.0                    # 一轮扫描 = 2 个 tick_200

# ---- 各阶段时间点（ns）----
T_SELFTEST = (300_000.0, 3_100_000.0)
T_IDLE = (3_225_000.0, 3_385_000.0)        # 进待机(3.20 ms)之后、按开始生效之前
T_PREVIEW = (4_500_000.0, 10_800_000.0)
T_PLAY = (11_900_000.0, 15_000_000.0)      # 散落完成后的对局（sel = 0）
T_PLAY_SEL = (15_800_000.0, 17_300_000.0)  # 按过"选择"之后
T_DIR = (17_600_000.0, 19_900_000.0)       # ★ 按方向键的时段（ERR-020 的回归窗口）
T_OFF = (21_800_000.0, 22_600_000.0)       # SW7=0 之后
T_SW_OFF = 21_200_000.0

# ---------------------------------------------------------------------------
# ⚠️ ERR-031：keypad_scan 的消抖由 **16 轮缩到 4 轮**（DEBOUNCE_MAX 15 → 3，
#    原因见 rtl/puzzle_pkg.vhd：一轮扫描 = 2 个 tick_200 = 10 ms，旧文档把 2 倍
#    算漏了，板上真实值曾是 160 ms，用户反馈手感迟钝）。
#
#    本 tb 的按键计划原本按"按下后第 15 轮被接受"排期，现在只需第 3 轮就被接受 ——
#    **接受时刻会整体提前 12 轮**，而下面的绝对时间窗（T_IDLE / T_PREVIEW / T_PLAY /
#    T_PLAY_SEL / T_DIR / T_WIN …）全部是按老接受时刻标定的。
#    所以这里把每个按键的**按下起点整体后移 DB_SHIFT 轮**：按下推迟 12 轮、
#    消抖少等 12 轮 → 接受时刻与改之前**逐轮一致**，窗口一个都不用动。
#    RTL 再改消抖时必须同步：DB_ROUNDS = DEBOUNCE_MAX+1，DB_SHIFT = 16 - DB_ROUNDS。
#    （定义必须放在 KEY_PLAN 之前 —— 它就是按这个偏移写出来的。）
# ---------------------------------------------------------------------------
DB_ROUNDS = 4
DB_SHIFT = 16 - DB_ROUNDS          # = 12

# 按键计划：(首轮, 末轮, 行, 列, 说明)
#   原始键号 1 = (行0,列1) → game_fsm 译为【开始】
#   原始键号 3 = (行0,列3) → 【选择】
#   ★ 方向键：按**新映射**的十字键各按一次（键号 = 4*行+列）：
#     下=键号2(KEY15) 左=键号5(KEY10) 右=键号7(KEY12) 上=键号10(KEY7) 确认=键号6(KEY11)
#     （键号 0 = KEY13 永远不用：扫描器用 0 表示"无键"）
#     窗口取 22 轮（消抖要 4 轮，留足余量），相邻按键间隔 25 轮。
# A4 旋转：三次 KEY8。放在第一场景"确认"之后、SW7 拨下去之前的空档里
#   （轮号 1250/1294/1338 + DB_SHIFT，同键间隔 44 轮 = GAP_SAME）。
ROT_R0 = 1250 + DB_SHIFT
ROT_KEYS = [(ROT_R0 + 44 * i, ROT_R0 + 44 * i + 21, 2, 3, "旋转%d KEY8" % (i + 1))
            for i in range(3)]

KEY_PLAN = [
    (196 + DB_SHIFT, 228 + DB_SHIFT, 0, 1, "开始 KEY14"),
    (950 + DB_SHIFT, 985 + DB_SHIFT, 0, 3, "选择 KEY16"),
    (1092 + DB_SHIFT, 1112 + DB_SHIFT, 0, 2, "下 KEY15"),
    (1117 + DB_SHIFT, 1137 + DB_SHIFT, 1, 1, "左 KEY10"),
    (1142 + DB_SHIFT, 1162 + DB_SHIFT, 1, 3, "右 KEY12"),
    (1167 + DB_SHIFT, 1187 + DB_SHIFT, 2, 2, "上 KEY7"),
    (1192 + DB_SHIFT, 1212 + DB_SHIFT, 1, 2, "确认 KEY11"),
] + ROT_KEYS
RAW_START, RAW_SELECT = 1, 3

# ============================================================================
# 第三场景：**整机端到端连过两关**（确定性散落 + 真实按键）
#
# 【要回答什么】上板现象："第一关拼好按确认 → 出叉；退出重进又直接跳进第二关"。
#   这是在**整机**层面复现与回归 ERR-023（对局态目标图案被置零 → 成功判据永不成立）
#   与 ERR-024（新一局开始时上一局的 locked/pos 残留 → 还没散落就判胜/判负）。
#
# 【为什么要把随机源钉死】按键计划必须知道"哪一块会落在哪里"才能写出走法。
#   rnd_val 恒 0 时每块候选恒为 (0,0)，16 次重试后落到**确定性回退锚点**：
#     一关 (0,0)/(0,4)/(4,0)；二关 (0,0)/(0,4)/(4,0)/(4,4)
#   走法直接沿用 tb_puzzle_ctrl 已经验过的两份计划（那边是引擎级命令，这里换成按键）。
# ============================================================================

# 控制键在 4x4 矩阵上的位置 (行, 列)：键号 = 4*行+列，与 game_fsm.key_of() 一致
CTRL_KEY = {"start": (0, 1), "select": (0, 3), "confirm": (1, 2),
            "up": (2, 2), "down": (0, 2), "left": (1, 1), "right": (1, 3),
            # ⚠️ 2026-10-09 第 13 工作阶段（提高要求 A4）：新增【旋转】键 = KEY8，
            #    原始键号 4*行+列 = 4*2+3 = 11，由 game_fsm.key_of() 译为 K_ROT。
            "rot": (2, 3)}

# 一关：三块从回退锚点 (0,0)/(0,4)/(4,0)、**初始朝向 (1,1,2)** 走到
#   L1_EXPECT_POS（等价铺法 (2,2)(3,2)(3,2)、朝向 (2,2,2)：零片 1 与零片 2 共用锚点、
#   形状互补，并集仍逐格等于图 4-1 的 4x3 矩形）→ 16 条命令 + 3 次确认。
#   ⚠️ 第 1 条命令就是【旋转】—— 零片从非零朝向开始，不转就拼不出来。
PLAN_L1 = (["rot"] + ["right"] + ["down"] + ["right"] + ["down"] + ["select"] +
           ["down"] + ["rot"] + ["down"] + ["left"] + ["down"] + ["left"] +
           ["select"] + ["up"] + ["right"] * 2 +
           ["confirm"] * 3)
# 第二关（**固定** PAT3 = 阶梯，D2 之后不再随机）：四块异形零片从回退锚点、初始朝向
#   (1,1,2,2) 走到 PAT3 的一种等价铺法（槽 0..3 → (5,3)(2,1)(2,2)(2,3)，朝向全 2）
#   → 30 条命令 + 4 次确认。
#   ⚠️ PAT3 含旋转有 **24 种**等价铺法（只许平移只有 2 种）→ 拼成哪一种都必须判成功，
#      这正是 ERR-021"看画面判成败"的回归用例；本 tb 走其中最短的那一种，
#      sim/tb_puzzle_ctrl.py 走的是**另一组锚点**（(2,2)(2,1)(3,3)(3,2)）。
PLAN_L2_PAT3 = (["down"] + ["select"] + ["left"] * 3 + ["rot"] + ["down"] * 2 +
                ["select"] + ["right"] * 2 + ["select"] + ["up"] * 2 + ["left"] +
                ["select"] + ["down"] * 3 + ["right"] + ["down"] + ["select"] * 2 +
                ["up"] * 2 + ["select"] * 2 + ["rot"] + ["right"] * 2 +
                ["confirm"] * 4)
PLAN_L2 = PLAN_L2_PAT3
# 各关拼完后的**完整 32 位 o_pos**（断言 ⑩/⑪/⑪b 用）：槽 k 占字节 (3-k)
#   （一关只用槽 0..2，槽 3 恒为 0）；与 scripts/check_plans.py 的
#   L1/L2/L3_EXPECT_POS 必须一致。
L1_EXPECT_POS = 0x22323200
L2_EXPECT_POS = 0x53212223

# 第三关（A2：图案从库里**随机选**；本 tb 用 DLD_L3PAT 把随机值钉住以便写走法）
#   模式 A（FORCE_PAT=0，田/4x4 方块）：20 条命令 + 4 次确认；
#           终点槽 0..3 → (2,2)(2,5)(3,2)(3,3)，朝向全 2
PLAN_L3_PAT0 = (["rot"] + ["right"] + ["down"] + ["right"] + ["down"] + ["select"] +
                ["rot"] + ["right"] + ["down"] * 2 + ["select"] + ["right"] * 2 +
                ["select"] + ["left"] + ["up"] + ["select"] * 3 + ["up"] +
                ["confirm"] * 4)
#   模式 B（FORCE_PAT=2，S/Z 锯齿）：26 条命令 + 4 次确认；
#           终点槽 0..3 → (2,1)(4,4)(3,1)(2,4)，朝向 (2,2,1,0)
PLAN_L3_PAT2 = (["rot"] + ["right"] + ["down"] * 2 + ["select"] + ["down"] * 3 +
                ["left"] + ["rot"] + ["down"] + ["select"] + ["up"] + ["rot"] * 3 +
                ["select"] + ["up"] * 2 + ["rot"] * 2 + ["select"] * 2 + ["right"] +
                ["select"] + ["right"] + ["confirm"] * 4)
PLAN_L3 = PLAN_L3_PAT2 if FORCE_PAT == 2 else PLAN_L3_PAT0
# 第三关拼完后的锚点元组（断言 ⑪b 用）；与 scripts/check_plans.py 的 L3_EXPECT_POS 一致
L3_EXPECT_POS = {0: 0x22253233, 2: 0x21443124}[FORCE_PAT]

HOLD = 22          # 按住多少轮（消抖要 4 轮，留 18 轮余量）
GAP_NEW = 25       # 换一个键：间隔轮数（松开 3 轮即可，因为换了键号）
GAP_SAME = 44      # **同一个键要再按一次**：必须先让扫描器看到"松开"——
                   # keypad_scan 的消抖是"连续 DEBOUNCE_MAX+1 轮不同才改 stable"，
                   # 所以松开窗口必须 > 4 轮，否则第二次按同一个键根本不会被识别。

# ---------------------------------------------------------------------------
# 消抖轮数/偏移见文件上方（DB_ROUNDS / DB_SHIFT，定义在 KEY_PLAN 之前）。
# ---------------------------------------------------------------------------

# SW7 再拨上去之后的基轮号（自检 2 s = 200 轮之后）
K2_START = 1980 + DB_SHIFT  # 待机里按【开始】
K2_L1 = 2600 + DB_SHIFT     # 第一关第一个动作（预览 5 s = 500 轮之后，留 100 轮余量）


def _plan_keys(k0, names):
    """命令名序列 -> [(首轮, 末轮, 行, 列, 名字)]，返回 (按键计划, 下一个可用轮号)。

    ⚠️ 间隔必须看**下一个**命令用的是不是同一个键：`_plan_keys` 第一版按"当前命令
    与上一个命令是否同键"来留间隔（差一位），于是 `down,down` 之间只隔了 25 轮 ——
    松开窗口只有 3 轮，扫描器的消抖（连续 DEBOUNCE_MAX+1 轮不同才改 stable）看不到松开，
    第二次按同一个键会被**静默丢掉**。离线复盘脚本 .tmp/plan_top.py 把这个排期
    打印出来才发现（按键计划也要能"看到"自己的时间表，不能只看走法对不对）。
    """
    out, k = [], k0
    for i, nm in enumerate(names):
        r, c = CTRL_KEY[nm]
        out.append((k, k + HOLD - 1, r, c, nm))
        nxt = names[i + 1] if (i + 1) < len(names) else None
        k += GAP_SAME if (nxt == nm) else GAP_NEW
    return out, k


KEYS_L1, _k_after_l1 = _plan_keys(K2_L1, PLAN_L1)
# 第一关最后一次确认 -> 判据最多 1 帧(40 ms)发布 -> 进第二关预览 5 s(=500 轮) -> 对局
# 21 轮 = 最后一次确认的消抖余量；80 轮 = 余量
K2_L2 = _k_after_l1 + 21 + 500 + 80
KEYS_L2, _k_after_l2 = _plan_keys(K2_L2, PLAN_L2)
# 第二关最后一次确认 -> 进**第三关**预览 5 s(=500 轮) -> 对局（D2 新增的一关）
K2_L3 = _k_after_l2 + 21 + 500 + 80
KEYS_L3, _k_after_l3 = _plan_keys(K2_L3, PLAN_L3)

KEY_PLAN2 = ([(K2_START, K2_START + HOLD - 1, 0, 1, "start(第二场景)")] +
             KEYS_L1 + KEYS_L2 + KEYS_L3)

# ---- 各阶段时间点（ns）----
T_SELFTEST = (300_000.0, 3_100_000.0)
T_IDLE = (3_225_000.0, 3_385_000.0)        # 进待机(3.20 ms)之后、按开始生效之前
T_PREVIEW = (4_500_000.0, 10_800_000.0)
T_PLAY = (11_900_000.0, 15_000_000.0)      # 散落完成后的对局（sel = 0）
T_PLAY_SEL = (15_800_000.0, 17_300_000.0)  # 按过"选择"之后
T_DIR = (17_600_000.0, 19_900_000.0)       # ★ 按方向键的时段（ERR-020 的回归窗口）
T_SW_OFF = 23_000_000.0                    # SW7 拨下去（B1）
                                           # ⚠️ 2026-10-09：原来 21.2 ms —— A4 的三个
                                           # 旋转键（同键间隔 GAP_SAME=44 轮）放不进去，
                                           # 所以把"拨下去"推到 23.0 ms；关灯时段
                                           # （23.0~27.0 ms）仍然远大于断言 ⑥ 需要的窗口。
T_OFF = (23_400_000.0, 24_200_000.0)       # SW7=0 之后
T_SW_ON2 = 27_000_000.0                    # SW7 再拨上去（自检 2 s -> 待机）
T_L1_CONF = S0 + (KEYS_L1[-1][0] + 24) * ROUND       # 第一关最后一次确认之后
T_L1_PREVIEW = T_L1_CONF + 1_000_000.0               # 应已进入**第二关预览**（预览 8 ms）
T_L2_CONF = S0 + (KEYS_L2[-1][0] + 24) * ROUND       # 第二关最后一次确认之后
T_L2_PREVIEW = T_L2_CONF + 1_000_000.0               # 应已进入**第三关预览**（D2）
T_L3_CONF = S0 + (KEYS_L3[-1][0] + 24) * ROUND       # 第三关最后一次确认之后
T_WIN = T_L3_CONF + 1_000_000.0                      # 应已进入胜利状态（D2：出口在第三关）
# 结算画面"先闪 2 个 2 Hz 周期（4×400 us = 1.6 ms）再常亮"，所以要留出观察常亮的窗口
DURATION = T_WIN + 6_000_000.0

# 胜利结算画面（设计值；tb 里独立抄一份当参考模型）：**粗绿对勾**（只点绿列），逐行掩码
#   ..............##  0x80      ##......####....  0x31
#   ............####  0xC0      ####..####......  0x1B
#   ..........######  0xE0      ##########......  0x1F（两臂交汇）
#   ........######..  0x70      ..######........  0x0E（顶点在左半边）
# 颜色：2026-10-09 由"粗红对勾"改成**只点绿列**（绿对勾 / 红叉的交通灯配色）。
WIN_ROWS = [0x80, 0xC0, 0xE0, 0x70, 0x31, 0x1B, 0x1F, 0x0E]
# 失败结算画面（原样保留的"叉"，独立抄一份）：注意它只点红列
#   ........  0x00      ..####..  0x3C
#   ##....##  0xC3      ..####..  0x3C
#   .##..##.  0x66      .##..##.  0x66
#   ..####..  0x3C      ##....##  0xC3
FAIL_ROWS = [0x00, 0xC3, 0x66, 0x3C, 0x3C, 0x66, 0xC3, 0x00]

# ============================================================================
# ⭐ 2026-10-10 新增：**整机音效断言的采样点**
#
# 【为什么要补这一组】此前整机 tb **只把 `buzz` 记进波形、没有任何音效断言** ——
#   文档里反复写着"音效的证据始终是 buzzer_ctrl rNN + game_fsm rNN，不是整机那一轮"。
#   也就是说："音效码真的从 game_fsm 走到 buzzer_ctrl 了吗？"在**整机层面**从来没被验过。
#   现在观测 `u_fsm|sound_p`（4 位音效码）与 `u_buzz|on_now`（这一步响不响），
#   把这条链路在整机上钉死。
#
# ⚠️ 采样点**必须避开"瞬时事件码"的保持窗口**（`snd_hold` = 2 个旋律步 = 500 ms 标称
#    = 本 tb 折算 800 us）：确认/旋转/过关/拼错之后 800 us 内音效码是**事件码**，
#    不是常驻码。下面的 `+1_500_000`（1.5 ms）就是为绕开它。
# ============================================================================
T_CONF1 = S0 + (1192 + DB_SHIFT + 10) * ROUND   # 第一场景【确认】被接受之后（码应=1100）
T_ROT1 = S0 + (ROT_KEYS[0][0] + 10) * ROUND     # 第一场景【旋转】被接受之后（码应=1010）
T_L2_PLAY = T_L1_PREVIEW + 9_000_000.0          # 第二关对局（预览 8 ms 之后，码应=1001）
T_L3_PLAY = T_L2_PREVIEW + 9_000_000.0          # 第三关对局（预览 8 ms 之后，码应=1011）
# SW7 关→开之后的自检窗口：**恒 8 个 tick_4hz**（ERR-051 修法），本 tb 折算 8 x 400 us。
# ⚠️ **不能用 `T_SW_ON2 + 8 x 400 us` 当窗口上界**：`tick_4hz` 是**自由走**的
#    （相位由复位后的分频链决定，与 SW7 的拨动时刻无关），所以"SW7 拉高 → 8 个 tick"
#    的实际结束时刻落在 **[T+2.8 ms, T+3.2 ms]** 之间（8 个脉冲跨 7 个周期）。
#    窗口取到 +3.4 ms 才能把两种极端都罩住；越过自检之后音效码变成 SND_NONE
#    ⇒ `on_now` 恒 0，**不会多算一声**。
T_SW2_SELF_MIN = T_SW_ON2 + 2_500_000.0         # 一定还在自检里（最早结束是 +2.8 ms）
T_SW2_SELF_SCAN = (T_SW_ON2 + 50_000.0, T_SW_ON2 + 3_400_000.0)   # 数"响了几声"的窗口

# ---- 第四场景：胜利画面之后按【开始】再开一局，故意"三块全确认但不摆位" ----
# 目的：B9/B10 的**失败图案**是基本要求，而第三场景永远以胜利收场 —— 改版前
#       顶层的失败分支没有任何仿真断言覆盖。这里补上：散落后（rnd 钉 0 → 回退锚点）
#       直接确认三次 → 全部锁定但画面不对 → 失败图案（红色叉）。
# ⚠️ ERR-034（2026-10-09 第 11 工作阶段）：起点**必须从走法计划末尾推导**，不能写死。
#   原来写的是 `4950 + DB_SHIFT`（按"第二关 27 条命令"标定的）。第 11 工作阶段第二关
#   走法变成 **42 条命令**（异形零片要走的路更长），计划末尾比原来晚约 300 轮 —— 于是
#   第四场景的【开始】会在**第三场景还没拼完**时按下去，状态序列变成
#   "…→ 预览 → 对局 → 预览 → 对局 → **失败**"（r25 第一次跑就是这个假失败；
#   波形复盘见 .tmp/opt/probe_top.py：按【开始】那一刻 pos 还在动、只锁了 1 块）。
#   现在改为：**第三关**最后一次确认 + 消抖余量 24 轮 + **320 轮观察窗**
#   （= 5.12 ms > 断言 ⑬⑭ 需要的 4.6 ms：2 Hz 闪 2 个周期 1.6 ms 再常亮 + 余量）。
K3_START = KEYS_L3[-1][0] + 24 + 320
K3_CONF = K3_START + 21 + 500 + 80                  # 预览 5 s(=500 轮) 之后再按确认
KEYS_FAIL, _k_after_fail = _plan_keys(K3_CONF, ["confirm"] * 3)
KEY_PLAN3 = ([(K3_START, K3_START + HOLD - 1, 0, 1, "start(第四场景)")] + KEYS_FAIL)
T_FAIL_CONF = S0 + (KEYS_FAIL[-1][0] + 24) * ROUND  # 第三次确认之后
T_FAIL_SCREEN = T_FAIL_CONF + 1_000_000.0           # 应已显示失败图案
DURATION = T_FAIL_SCREEN + 5_000_000.0              # 留出失败画面的观察窗口

OBSERVE = ["clk", "sw7", "btn", "kp_row", "kp_col",
           "dot_row", "dot_colr", "dot_colg", "seg", "cat", "buzz",
           # 中间信号：顶层自己的 mrow/mat_r 在网表里存在；其余内部信号按
           # 「实例标签|信号名」的层次写法（已用探针实测确认能匹配上）
           "mrow", "mat_r",
           "u_clk|t2", "u_keypad|key_r", "u_keypad|stable", "u_seg|idx",
           "u_fsm|st", "u_fsm|cnt", "u_fsm|level", "u_fsm|lvl3",
           "u_fsm|up_r", "u_fsm|down_r", "u_fsm|left_r", "u_fsm|right_r",
           "u_fsm|move_r", "u_fsm|conf_r", "u_fsm|sel_r",
           "u_puzzle|pos", "u_puzzle|locked", "u_puzzle|mv_dir",
           "u_puzzle|mv_pend", "u_puzzle|chk_pos",
           "u_puzzle|ori", "u_puzzle|sel",        # A4：朝向 + 选中槽
           # ⭐ 2026-10-10（补音效断言）：`buzz` 只是**方波输出**，看它判"响没响"
           #    要数方波；要判"**该响哪个音效**"必须看 4 位**音效码**本身。
           #    `u_fsm|sound_p` = game_fsm 里那个寄存器（= o_sound 的源），
           #    `u_buzz|on_now` = buzzer 侧"这一步响不响"的寄存输出。
           #    两个名字都用 `scripts/probe_nodes.py` 对**仿真器节点表**核对过
           #    （41823 条全名里确认存在），不是猜的。
           "u_fsm|sound_p", "u_buzz|on_now"]

# 段码 -> 数字（与 rtl/seg_scan.vhd 的共阴译码表一致；blank = 0x00）
DIGITS = {0x3F: "0", 0x06: "1", 0x5B: "2", 0x4F: "3", 0x66: "4",
          0x6D: "5", 0x7D: "6", 0x07: "7", 0x7F: "8", 0x6F: "9", 0x00: " "}
# 结算画面的字母段码（2026-10-08：胜利 "PASS"、失败 "FAIL"）
#   ⚠️ 0x6D 既是 '5' 也是 'S'（段完全一样）、'I' 就是 '1' 的形状 —— 物理限制
SEG_LETTER = {0x73: "P", 0x77: "A", 0x6D: "S", 0x71: "F", 0x38: "L", 0x06: "I"}


# ---------------------------------------------------------------- 激励
def _buried(b, name, width):
    for n in [name] + ["%s[%d]" % (name, i) for i in range(width)]:
        sig = b.vf.signals.get(n)
        if sig is not None:
            sig.direction = "BURIED"


def _tl(duration, spans, default):
    ev = []
    for (a, bb, v) in spans:
        ev.append((a, 0, v))
        ev.append((bb, 1, default))
    ev.sort(key=lambda x: (x[0], x[1]))
    segs, t, cur = [], 0.0, default
    for (tt, _k, v) in ev:
        if tt > t:
            segs.append((tt - t, cur))
            t = tt
        cur = v
    if t < duration:
        segs.append((duration - t, cur))
    return segs


def _round_windows(k, r, c):
    """第 k 轮里按下 (r,c) 时行 r 应为低的窗口。

    采样时刻（用 kp_col 的相序**实测校准**，见文件头）：
      · row_all 在 SETTLE 结束时锁存 —— 落在 S+1320 附近；
      · 第 c 列在 RELEASE 第 c 相末尾采样 —— 落在 S+1340+1280c 附近。
    所以窗口取"锁存/采样时刻前后各留 100 ns"，而不是紧贴理论值 ——
    理论值只要差一个时钟，扫描器就会把这一列判成"没按下"。
    """
    t0 = S0 + k * ROUND
    return [(t0 + 20.0, t0 + 1400.0),
            (t0 + 1240.0 + 1280.0 * c, t0 + 1440.0 + 1280.0 * c)]


def build(b):
    b.input_bit("clk")
    b.input_bit("sw7")
    b.input_bit("btn")
    b.input_bus("kp_row", 4)
    b.output_bus("kp_col", 4)
    b.output_bus("dot_row", 8)
    b.output_bus("dot_colr", 8)
    b.output_bus("dot_colg", 8)
    b.output_bus("seg", 8)
    b.output_bus("cat", 8)
    b.output_bit("buzz")
    for n, w in (("mrow", 3), ("mat_r", 8),
                 ("u_clk|t2", 1), ("u_keypad|key_r", 4), ("u_keypad|stable", 4),
                 ("u_seg|idx", 3), ("u_fsm|st", 3), ("u_fsm|cnt", 6),
                 ("u_fsm|level", 1), ("u_fsm|lvl3", 1),
                 ("u_fsm|up_r", 1), ("u_fsm|down_r", 1),
                 ("u_fsm|left_r", 1), ("u_fsm|right_r", 1),
                 ("u_fsm|move_r", 1), ("u_fsm|conf_r", 1), ("u_fsm|sel_r", 1),
                 ("u_puzzle|pos", 32), ("u_puzzle|locked", 4),
                 ("u_puzzle|mv_dir", 4), ("u_puzzle|mv_pend", 1),
                 ("u_puzzle|chk_pos", 8),
                 ("u_puzzle|ori", 8), ("u_puzzle|sel", 2),
                 # 音效码 + buzzer 侧"这一步响不响"的门控（见 OBSERVE 的说明）
                 ("u_fsm|sound_p", 4), ("u_buzz|on_now", 1)):
        if w == 1:
            b.output_bit(n)
        else:
            b.output_bus(n, w)
        _buried(b, n, w)

    b.clock("clk", CLK)
    # BTN0 空闲为低（按下才是高）—— 不按，交给上电复位
    b.segments("btn", [(DURATION, 0)])
    # SW7：前 21.2 ms 为 1；随后拨下去（B1：关掉开关全部不显示）；
    #      27 ms 再拨上去 —— 第二场景要在一局"完整的两关"上跑
    # ⚠️ 这里**不能**用 _tl()：本文件的 _tl 是按"事件排序"实现的，两段**首尾相接**
    #    的区间在同一时刻上一段结束、下一段开始，排序会把"恢复默认 1"排在后面，
    #    于是 0 那一段被吃掉（实测断言 ⑥ 立刻报"SW7=0 后点阵仍亮 12 格"）。
    #    直接给 (时长, 值) 序列最稳。
    b.segments("sw7", [(T_SW_OFF, 1),
                       (T_SW_ON2 - T_SW_OFF, 0),
                       (DURATION - T_SW_ON2, 1)])

    spans = []
    for (k0, k1, r, c, _n) in (KEY_PLAN + KEY_PLAN2 + KEY_PLAN3):
        for k in range(k0, k1 + 1):
            for (a, bb) in _round_windows(k, r, c):
                spans.append((a, bb, 0xF & ~(1 << r)))
    b.bus_segments("kp_row", _tl(DURATION, spans, 0xF))


# ---------------------------------------------------------------- 采样工具
def _find_zero_bit(v, width=8):
    """v 里恰好一位为 0 时返回该位的**位号**（从 0 = LSB 数），否则 None。"""
    if v is None:
        return None
    bits = [(v >> i) & 1 for i in range(width)]
    if bits.count(0) != 1:
        return None
    return bits.index(0)


def scan_panel(vf, t0, t1, step=100.0):
    """在 [t0,t1] 内扫描，重建：每行红/绿列掩码、每个数码管位置遇到的段码集合。"""
    row_r = [0] * 8
    row_g = [0] * 8
    row_seen = [False] * 8
    digits = {}
    t = t0
    while t <= t1:
        rw = vf.bus_value_at("dot_row", t)
        j = _find_zero_bit(rw)
        if j is not None:
            r = 7 - j                      # 逻辑行号（0 = 最上面）
            cr = vf.bus_value_at("dot_colr", t)
            cg = vf.bus_value_at("dot_colg", t)
            if cr is not None:
                row_r[r] |= cr
            if cg is not None:
                row_g[r] |= cg
            row_seen[r] = True
        cat = vf.bus_value_at("cat", t)
        d = _find_zero_bit(cat)
        if d is not None:
            seg = vf.bus_value_at("seg", t)
            if seg is not None:
                digits.setdefault(d, set()).add(seg)
        t += step
    return row_r, row_g, row_seen, digits


def panel_state(vf, t):
    """某一瞬间被点亮的那一行是什么颜色（用于判断 2 Hz 闪烁的两半）。"""
    rw = vf.bus_value_at("dot_row", t)
    if _find_zero_bit(rw) is None:
        return None
    return vf.bus_value_at("dot_colr", t), vf.bus_value_at("dot_colg", t)


def digit_of(digits, idx):
    """某个数码管位置在窗口里出现过的段码 -> 数字（优先非空白）。"""
    ss = digits.get(idx, set())
    vals = [DIGITS.get(s, "?") for s in ss]
    nz = [v for v in vals if v not in (" ", "?")]
    return nz[0] if nz else (vals[0] if vals else "-")


def cells(row_r, row_g):
    n = 0
    for r in range(8):
        n += bin(row_r[r]).count("1") + bin((row_g[r]) & ~row_r[r]).count("1")
    return n


def green_cells(row_r, row_g):
    out = set()
    for r in range(8):
        g = row_g[r] & ~row_r[r]
        for c in range(8):
            if (g >> c) & 1:
                out.add((r, c))
    return out


def check(vf):
    res = []

    # ① B1 自检：点阵全黄 + 2 Hz 方波闪烁 + 8 位数码管全 "8"
    n_yellow = n_dark = n_other = 0
    t = T_SELFTEST[0]
    while t <= T_SELFTEST[1]:
        st = panel_state(vf, t)
        if st is not None:
            cr, cg = st
            if cr == 0xFF and cg == 0xFF:
                n_yellow += 1
            elif cr == 0x00 and cg == 0x00:
                n_dark += 1
            else:
                n_other += 1
        t += 20_000.0                       # 20 us 一个采样点（远小于 400 us 半周期）
    _, _, _, dig_s = scan_panel(vf, T_SELFTEST[0], T_SELFTEST[1], 2000.0)
    all8 = all("8" in [DIGITS.get(s, "?") for s in dig_s.get(i, set())] for i in range(8))
    res.append((
        "① B1 自检：点阵**全黄**并以 2 Hz 方波闪烁（亮/灭各占约一半，ERR-011 回归），"
        "8 位数码管全部出现 \"8\"",
        n_yellow > 5 and n_dark > 5 and n_other == 0 and all8,
        "采样 %d 个：全黄 %d、全灭 %d、其它 %d；8 位数码管都出现过 '8' = %s"
        % (n_yellow + n_dark + n_other, n_yellow, n_dark, n_other, all8),
    ))

    # ② B2 待机
    row_r, row_g, seen, dig = scan_panel(vf, *T_IDLE, step=1000.0)
    lit = cells(row_r, row_g)
    res.append((
        "② B2 待机：点阵全灭，DISP7='5'、DISP0='1'，其余位空白",
        lit == 0 and digit_of(dig, 7) == "5" and digit_of(dig, 0) == "1"
        and all(digit_of(dig, i) == " " for i in (1, 2, 3, 4, 5, 6)),
        "点阵点亮格数=%d；数码管 DISP7=%s DISP6..1=%s DISP0=%s"
        % (lit, digit_of(dig, 7),
           [digit_of(dig, i) for i in (6, 5, 4, 3, 2, 1)], digit_of(dig, 0)),
    ))

    # ③ B4 预览：完整图 4-1（红、12 格）+ DISP7 倒计时
    row_r, row_g, seen, dig = scan_panel(vf, *T_PREVIEW, step=3000.0)
    want = [0x1C if 2 <= r <= 5 else 0x00 for r in range(8)]
    res.append((
        "③ B4 预览：点阵显示完整图 4-1（第 2~5 行 x 第 2~4 列，每行 0x1C，共 12 格），"
        "且 DISP7 出现 1~5 的倒计时",
        row_r == want and all(g == 0 for g in row_g) and cells(row_r, row_g) == 12
        and digit_of(dig, 7) in ("1", "2", "3", "4", "5"),
        "实测每行红掩码=%s（期望 %s）；绿=%s；共 %d 格；DISP7 出现过的值=%s"
        % ([hex(x) for x in row_r], [hex(x) for x in want],
           [hex(x) for x in row_g], cells(row_r, row_g),
           sorted(v for v in [DIGITS.get(s, "?") for s in dig.get(7, set())])),
    ))

    # ④ B5 散落：出现零片（12 格、不再等于完整矩形）+ DISP4:DISP3 限时倒计时
    rA, gA, _, digA = scan_panel(vf, *T_PLAY, step=3000.0)
    n_lit = cells(rA, gA)
    tens = digit_of(digA, 4)
    ones = digit_of(digA, 3)
    num = None
    if tens in "0123456789" and ones in "0123456789":
        num = int(tens) * 10 + int(ones)
    res.append((
        "④ B5 预览结束进入对局：点阵出现零片（3+6+3 = 12 格，且不再是完整 4x3 矩形 →"
        " 说明真的散落了），DISP4:DISP3 显示 30 秒限时倒计时",
        n_lit == 12 and rA != [0x1C if 2 <= r <= 5 else 0 for r in range(8)]
        and num is not None and 25 <= num <= 30,
        "点亮格数=%d（期望 12）；每行红=%s；DISP4:DISP3 = %s%s = %s"
        % (n_lit, [hex(x) for x in rA], tens, ones, num),
    ))

    # ⑤ B6 选择：绿色零片切换（选中的零片变绿）
    g_before = green_cells(rA, gA)
    rB, gB, _, _ = scan_panel(vf, *T_PLAY_SEL, step=3000.0)
    g_after = green_cells(rB, gB)
    res.append((
        "⑤ B6 按【选择】后：绿色零片从一块切换到另一块（选中零片变绿、且未被选中的"
        "仍是红色）；两次点亮总格数都保持 12（面积守恒，散落不重叠的整机回归）",
        len(g_before) == 3 and len(g_after) == 6 and g_before != g_after
        and cells(rB, gB) == 12,
        "按选择前绿色格数=%d（第一块 = 1x3 横条）、之后=%d（第二块 = 6 格楼梯形）；"
        "绿色集合已改变；之后点亮总格数=%d"
        % (len(g_before), len(g_after), cells(rB, gB)),
    ))

    # ⑥ B1 SW7=0：全部不显示
    row_r, row_g, _, dig = scan_panel(vf, *T_OFF, step=2000.0)
    res.append((
        "⑥ B1 SW7=0：点阵全灭、8 位数码管全部熄灭（\"所有显示器件不显示\"）",
        cells(row_r, row_g) == 0
        and all(digit_of(dig, i) in (" ", "-") for i in range(8)),
        "点阵点亮格数=%d；数码管读数=%s"
        % (cells(row_r, row_g), [digit_of(dig, i) for i in range(7, -1, -1)]),
    ))

    # ⑦ 状态机确实按 自检→待机→预览→对局 走
    seq = []
    for (tt, v) in _bus_trace(vf, "u_fsm|st"):
        if not seq or seq[-1][1] != v:
            seq.append((tt, v))
    names = {0: "自检", 1: "待机", 2: "预览", 3: "对局", 4: "胜利", 5: "失败"}
    got = [names.get(v, str(v)) for (_t, v) in seq]
    res.append((
        "⑦ 整机状态序列按需求推进：自检 → 待机 → 预览 → 对局（按【开始】启动）",
        got[:4] == ["自检", "待机", "预览", "对局"],
        "状态序列 = %s" % " → ".join(got),
    ))

    # ⑧ ★ 方向协议不变量（ERR-020 的回归判据）
    #   只要 game_fsm 发出了方向脉冲（up_r/down_r/left_r/right_r 任一为 1），
    #   引擎在**同拍或其后两拍内**必须把非 0 的 mv_dir 锁进去。
    #   —— 这条判据与 key_of() 的映射无关：它测的是 FSM↔引擎之间的**接口协议**。
    dirbits = ["u_fsm|up_r", "u_fsm|down_r", "u_fsm|left_r", "u_fsm|right_r"]
    pulses, viol = 0, []
    t = T_DIR[0]
    while t <= T_DIR[1]:
        if any(vf.value_at(n, t) == "1" for n in dirbits):
            pulses += 1
            ok = False
            for dt in (0.0, CLK, 2 * CLK):
                v = vf.bus_value_at("u_puzzle|mv_dir", t + dt)
                if v not in (None, 0):
                    ok = True
            if not ok and len(viol) < 5:
                viol.append("t=%.0f ns 方向脉冲已发但 mv_dir 仍为 0" % t)
        t += CLK
    res.append((
        "⑧ ★ 方向协议不变量：FSM 每发出一次方向脉冲，引擎都必须在 2 拍内锁进非 0 的 "
        "mv_dir（ERR-020 的回归判据；与键位映射无关）",
        pulses > 0 and not viol,
        "方向脉冲 %d 次；%s" % (pulses, "；".join(viol) if viol else "每次都在 2 拍内锁进非 0 方向"),
    ))

    # ⑨ 方向键按下去之后，引擎的候选锚点至少要变过一次（整条链路真的动了）
    anchors = set()
    t = T_DIR[0]
    while t <= T_DIR[1]:
        v = vf.bus_value_at("u_puzzle|chk_pos", t)
        if v is not None:
            anchors.add(v)
        t += CLK
    cur = set()
    for k in range(4):
        b = (vf.bus_value_at("u_puzzle|pos", T_DIR[0] + 1000.0) >> (24 - 8 * k)) & 0xFF
        cur.add(b)
    res.append((
        "⑨ 方向键按下后，引擎的候选锚点 chk_pos 至少出现过 1 个**与当前锚点不同**的值"
        "（说明方向真的参与了「夹紧 + 边界/重叠判定」，而不是原地重算）",
        len(anchors - cur) > 0,
        "方向窗口内 chk_pos 出现过的值 = %s；当前各块锚点 = %s"
        % (sorted(hex(a) for a in anchors), sorted(hex(c) for c in cur)),
    ))

    # ================================================================
    # 第三场景：整机端到端连过两关（ERR-023 / ERR-024 的回归判据）
    # ================================================================
    # ⑩ ★ 第一关：真实按键拼回目标锚点 + 逐块确认 → 必须进**第二关预览**
    pos1 = vf.bus_value_at("u_puzzle|pos", T_L1_CONF)
    lock1 = vf.bus_value_at("u_puzzle|locked", T_L1_CONF)
    st_l1 = vf.bus_value_at("u_fsm|st", T_L1_PREVIEW)
    lv_l1 = vf.value_at("u_fsm|level", T_L1_PREVIEW)
    l3_l1 = vf.value_at("u_fsm|lvl3", T_L1_PREVIEW)
    res.append((
        "⑩ ★【整机·第一关】用真实矩阵按键把三块拼成图 4-1 的 4x3 矩形（并集逐格一致；"
        "终点锚点 (2,2)(3,2)(3,2) 是**等价铺法**，不是 pkg 里写的那组见证锚点）"
        "并逐块确认后，状态机必须进入**第二关预览**（o_level=1、o_lvl3=0）—— "
        "修复前这里是判负出叉（ERR-023：对局态喂给引擎的目标图案被置零，"
        "成功判据永远不可能成立）",
        pos1 == L1_EXPECT_POS and lock1 is not None and (lock1 & 0x7) == 0x7
        and st_l1 == 2 and lv_l1 == "1" and l3_l1 == "0",
        "确认后锚点=0x%s（期望 0x%08X）、locked=%s；1 ms 后 o_state=%s（2=预览）、"
        "o_level=%s o_lvl3=%s"
        % ("--------" if pos1 is None else format(pos1, "08X"), L1_EXPECT_POS,
           "----" if lock1 is None else format(lock1, "04b"), st_l1, lv_l1, l3_l1),
    ))

    # ⑩b ★ D2：第二关拼完 → 进入**第三关预览**（A2"增加游戏关数"）
    st_l2 = vf.bus_value_at("u_fsm|st", T_L2_PREVIEW)
    l3_l2 = vf.value_at("u_fsm|lvl3", T_L2_PREVIEW)
    res.append((
        "⑩b ★【D2/A2】第二关拼完并全部确认后 → 状态机进入**第三关预览**"
        "（o_state=2 预览、**o_lvl3=1**）—— D2 之前这里直接是胜利；"
        "「增加游戏关数」正是提高要求 2 的前半句",
        st_l2 == 2 and l3_l2 == "1",
        "1 ms 后 o_state=%s（期望 2 预览）、o_lvl3=%s（期望 1）" % (st_l2, l3_l2),
    ))

    # ⑯ ★ B10：第二关预览显示的必须是**固定的那一幅**（D2：PAT3 阶梯，不再随机）
    #    这条断言是「第二关固定图案 → pattern_rom 按 (level,pat) 选图案 → 顶层预览切片」
    #    整条链路的回归判据：写错图案下标、接线错、行切片错位，逐行掩码立刻不符。
    wantP2 = pat_rows(3)
    rP, gP, _sP, _dP = scan_panel(vf, T_L1_PREVIEW + 1_000_000.0,
                                  T_L1_PREVIEW + 4_000_000.0, step=2000.0)
    res.append((
        "⑯ ★【B10 第二关 = 固定图案】第二关预览逐行显示 **PAT3（阶梯）**（共 %d 格，"
        "只点红列）—— D2 之后第二关图案**不随随机源变化**（随机选择属提高要求 2，已移到第三关）"
        % sum(bin(p).count("1") for p in wantP2),
        rP == wantP2 and gP == [0] * 8,
        "实测红=%s\n期望红=%s（PAT3）\n绿=%s"
        % ([hex(x) for x in rP], [hex(x) for x in wantP2], [hex(x) for x in gP]),
    ))

    # ⑯b ★ A2：第三关预览显示的必须是**随机选中的那一幅**（本 tb 用 DLD_L3PAT 钉住）
    wantP3 = pat_rows(FORCE_PAT)
    rQ, gQ, _sQ, _dQ = scan_panel(vf, T_L2_PREVIEW + 1_000_000.0,
                                  T_L2_PREVIEW + 4_000_000.0, step=2000.0)
    res.append((
        "⑯b ★【A2 第三关 = 随机图案】第三关预览逐行显示**图案库第 %d 幅**"
        "（本 tb 把随机值钉在 %d；共 %d 格，只点红列）—— 证明「进入第三关时锁存 rnd_val → "
        "pattern_rom 按 (level,pat) 选图」真的作用到了预览画面"
        % (FORCE_PAT, FORCE_PAT, sum(bin(p).count("1") for p in wantP3)),
        rQ == wantP3 and gQ == [0] * 8,
        "实测红=%s\n期望红=%s（图案 %d）\n绿=%s"
        % ([hex(x) for x in rQ], [hex(x) for x in wantP3], FORCE_PAT,
           [hex(x) for x in gQ]),
    ))

    # ⑪ ★ 第二关（**固定** PAT3）：四块异形零片拼成一种等价铺法 + 全确认 → 进第三关预览
    pos2 = vf.bus_value_at("u_puzzle|pos", T_L2_CONF)
    lock2 = vf.bus_value_at("u_puzzle|locked", T_L2_CONF)
    res.append((
        "⑪ ★【整机·第二关 = 固定 PAT3】四块异形零片（3+2+5+6 格）拼成 PAT3 阶梯的"
        "**第 0 种等价铺法**（画面与目标图案逐格一致）并全部确认 → 状态机推进到第三关"
        "（ERR-021 的整机回归：判据只看画面，RTL 里没有任何锚点常量；PAT3 有 2 种铺法"
        "都被判成功）",
        pos2 == L2_EXPECT_POS and lock2 == 0xF,
        "确认后锚点=0x%s（期望 0x%08X）、locked=%s"
        % ("--------" if pos2 is None else format(pos2, "08X"), L2_EXPECT_POS,
           "----" if lock2 is None else format(lock2, "04b")),
    ))

    # ⑪b ★ 第三关（**随机**图案）：拼成该图案 + 全确认 → 胜利
    pos3 = vf.bus_value_at("u_puzzle|pos", T_L3_CONF)
    lock3 = vf.bus_value_at("u_puzzle|locked", T_L3_CONF)
    st_l3 = vf.bus_value_at("u_fsm|st", T_WIN)
    res.append((
        "⑪b ★【整机·第三关 = 随机图案 %d】四块异形零片拼成**图案 %d**（%s）的唯一铺法"
        "并全部确认 → **胜利状态**（A2「增加游戏关数 + 多种拼图图案随机选择」的整机出口；"
        "换一幅图案照样能玩通、判据照样成立）"
        % (FORCE_PAT, FORCE_PAT, "田/4x4 方块" if FORCE_PAT == 0 else "S/Z 锯齿"),
        pos3 == L3_EXPECT_POS and lock3 == 0xF and st_l3 == 4,
        "确认后锚点=0x%s（期望 0x%08X）、locked=%s；1 ms 后 o_state=%s（4=胜利）"
        % ("--------" if pos3 is None else format(pos3, "08X"), L3_EXPECT_POS,
           "----" if lock3 is None else format(lock3, "04b"), st_l3),
    ))

    # ⑫ 整个第三场景的状态序列：自检 → 待机 → 预览 → 对局 → 预览 → 对局 → **预览 → 对局** → 胜利
    #    ⚠️ 窗口从 **T_SW_OFF**（拨下去那一刻）开始数，不是 T_SW_ON2：SW7=0 期间
    #    状态机就停在"自检"上，拨回来时不会再产生一次跳变，所以从 T_SW_ON2 起数会
    #    看不到开头那个"自检"（第一版就是这么错的）。
    seq2 = []
    for (tt, v) in _bus_trace(vf, "u_fsm|st"):
        if tt >= T_SW_OFF and (not seq2 or seq2[-1][1] != v):
            seq2.append((tt, v))
    got2 = [names.get(v, str(v)) for (_t, v) in seq2]
    res.append((
        "⑫ 第三场景的状态序列 = 自检 → 待机 → 预览 → 对局 → 预览 → 对局 → **预览 → 对局** "
        "→ 胜利（即真的**连过三关**：D2 在原来的两关之间插入了第三关；也说明没有"
        "「还没散落就判胜/判负」的残留状态跳变）",
        got2[:9] == ["自检", "待机", "预览", "对局", "预览", "对局", "预览", "对局", "胜利"],
        "状态序列 = %s" % " → ".join(got2),
    ))

    # ================================================================
    # 胜利结算画面（2026-10-08 改进：细对勾 -> 黄色笑脸 + 先闪后常亮）
    # ================================================================
    # ⚠️ 不能用 `t > T_L2_CONF` 去找胜利跳变：T_L2_CONF 是"最后一次确认按下 + 24 轮"，
    #    而按键是按下后第 3 轮（DEBOUNCE_MAX）被消抖接受的，判决再晚一个整帧（64 us）——
    #    所以真正进 S_WIN 的时刻比 T_L2_CONF **早** 几十微秒（r15 就是这么误判成
    #    "仿真窗口内没有进入胜利状态"）。改用第三场景开始（SW7 拨上去）之后即可。
    wins = [t for (t, v) in _bus_trace(vf, "u_fsm|st") if v == 4 and t > T_SW_ON2]
    t_win = wins[0] if wins else None
    # ⚠️ 结算画面的观察窗必须**止于胜利态结束**（第四场景按【开始】那一刻），不能取到
    #    DURATION —— 否则下一个场景（预览图案 / 零片 / 失败叉）会被 OR 进来，
    #    ⑬ 的"逐行比对"与 ⑭ 的"常亮"都会假失败（r17 就是这么挂的）。
    st_all = _bus_trace(vf, "u_fsm|st")
    t_win_end = DURATION
    for _i, (_t, _v) in enumerate(st_all):
        if _v == 4 and _t > T_SW_ON2:
            t_win_end = st_all[_i + 1][0] if (_i + 1) < len(st_all) else DURATION
            break
    if t_win is None:
        res.append(("⑬ 胜利结算画面", False, "仿真窗口内没有进入胜利状态"))
        res.append(("⑭ 结算画面闪烁节奏", False, "仿真窗口内没有进入胜利状态"))
    else:
        # ⑬ 形状 + 颜色：**只点绿列**（红列必须全 0）→ 绿色粗对勾
        rr, rg, _seen, dig_w = scan_panel(vf, t_win + 50_000.0, t_win_end - 50_000.0,
                                         step=500.0)
        # 结算信息（2026-10-08 用户拍板）：最左四位拼 "PASS"，其余四位全灭
        want_disp = {7: 0x73, 6: 0x77, 5: 0x6D, 4: 0x6D}      # P A S S
        got_disp = {k: sorted(v) for k, v in dig_w.items()}
        disp_ok = (all(got_disp.get(k) == [want_disp[k]] for k in want_disp)
                   and all(got_disp.get(k, [0]) == [0] for k in (0, 1, 2, 3)))
        word = "".join(SEG_LETTER.get(want_disp[k], "?") for k in (7, 6, 5, 4))
        res.append((
            "⑬ ★ 胜利结算画面 = **绿色粗对勾**（8 行逐行比对；**只点绿列、红列不亮**——"
            "\"绿对勾 / 红叉\"交通灯配色，颜色本身即判读线索），数码管最左四位拼出 **PASS**。"
            "演进：细对勾 → 黄笑脸 → 粗红对勾 → **粗绿对勾**（2026-10-09 用户拍板）；"
            "数码管原来是随意挑的 \"75\"",
            rr == [0] * 8 and rg == WIN_ROWS and disp_ok,
            "实测红=%s\n绿=%s\n期望红=全 0、绿=%s\n数码管 DISP7..DISP4 段码 = %s（读作 %r）"
            % ([hex(x) for x in rr], [hex(x) for x in rg], [hex(x) for x in WIN_ROWS],
               [got_disp.get(k) for k in (7, 6, 5, 4)], word),
        ))

        # ⑭ 节奏：先按 2 Hz 闪 2 个周期，然后常亮（自拟改进项 S5：便于远距离判读）
        def _lit(t):
            st = panel_state(vf, t)
            if st is None:
                return None
            cr, cg = st
            return ((cr or 0) | (cg or 0)) != 0

        flash = [x for x in (_lit(t_win + 200_000.0 + i * 100_000.0)
                             for i in range(26)) if x is not None]
        steady = [x for x in (_lit(t_win + 3_600_000.0 + i * 100_000.0)
                              for i in range(9)) if x is not None]
        res.append((
            "⑭ ★ 结算画面节奏：**先按 2 Hz 闪 2 个周期**（抓注意力）再**常亮**"
            "（远距离可读）—— 自拟改进项 S5；一直闪反而不利于判读",
            bool(flash) and (not all(flash)) and len(steady) >= 5 and all(steady)
            and (t_win_end - t_win) > 4_600_000.0,
            "胜利态持续 %.2f ms（须 > 4.6 ms，否则常亮窗口落在下一个场景里）；"
            "前 2.6 ms 采样 %d 次：亮 %d、灭 %d（有'灭'说明真的在闪）；"
            "3.6~4.4 ms 采样 %d 次：亮 %d（应全亮 = 常亮）"
            % ((t_win_end - t_win) / 1e6, len(flash), sum(flash),
               len(flash) - sum(flash), len(steady), sum(steady)),
        ))

    # ================================================================
    # 第四场景：失败结算画面（B9/B10 的"失败图案"—— 基本要求里唯一
    # 一直没有仿真断言覆盖的显示分支）
    # ================================================================
    fails = [t for (t, v) in _bus_trace(vf, "u_fsm|st") if v == 5 and t > T_SW_ON2]
    t_fail1 = fails[0] if fails else None
    if t_fail1 is None:
        res.append(("⑮ 失败结算画面（红色叉）", False, "仿真窗口内没有进入失败状态"))
    else:
        rr_f, rg_f, _sf, dig_f = scan_panel(vf, t_fail1 + 50_000.0, DURATION - 500.0,
                                           step=500.0)
        want_f = {7: 0x71, 6: 0x77, 5: 0x06, 4: 0x38}          # F A I L
        got_f = {k: sorted(v) for k, v in dig_f.items()}
        disp_f_ok = (all(got_f.get(k) == [want_f[k]] for k in want_f)
                     and all(got_f.get(k, [0]) == [0] for k in (0, 1, 2, 3)))
        word_f = "".join(SEG_LETTER.get(want_f[k], "?") for k in (7, 6, 5, 4))
        res.append((
            "⑮ ★ 失败结算画面 = 原来的**红色叉**（逐行比对 FAIL_MASK；只点红列、绿列不亮），"
            "数码管最左四位拼出 **FAIL**——第四场景：开新一局后三块直接确认（不摆位）→ "
            "全部锁定但画面不对 → 判负（B9/B10 的失败图案；改版前这条路径无断言覆盖）",
            rr_f == FAIL_ROWS and rg_f == [0] * 8 and disp_f_ok,
            "进入失败态时刻=%.0f ns；实测红=%s\n绿=%s\n期望红=%s、绿=全 0\n"
            "数码管 DISP7..DISP4 段码 = %s（读作 %r）"
            % (t_fail1, [hex(x) for x in rr_f], [hex(x) for x in rg_f],
               [hex(x) for x in FAIL_ROWS], [got_f.get(k) for k in (7, 6, 5, 4)], word_f),
        ))

    # ⑰ ★【A4 旋转 · 整机】在真实矩阵键盘上按 KEY8 三次（原始键号 11 = 行2/列3）
    #     A4 要求"零片不仅能上下左右移动，还可以 90° 旋转"。整机这一条要同时证明：
    #       ① 旋转键真的被扫描器识别、经 game_fsm 的 o_rot 送到引擎（i_rot）；
    #       ② 旋转**只改朝向、不改位置** —— 锚点 o_pos 整字一个字节都不许变；
    #       ③ 每按一次朝向要么不变（越界 / 会重叠 → 被拒），要么**恰好 +1（mod 4）**；
    #       ④ 点阵上被点亮的格子数**守恒**（旋转不改零片面积，且拒绝时画面不动）。
    #     ⚠️ 不假设"一定被接受"：散落是随机的，贴边的零片转过去可能越界 —— 那正是
    #        stage 2b 的边界判据在起作用，所以判据写成"不变 或 +1"。
    rot_ok, rot_notes = True, []
    t_first = S0 + ROT_KEYS[0][0] * ROUND
    # 取多位数用本文件的 vf.bus_value_at（_bus 是 tb_puzzle_ctrl 的辅助，这里没有）
    def _rd(nm, tt):
        return vf.bus_value_at(nm, tt)

    pos_ref = _rd("u_puzzle|pos", t_first - 2000.0)
    ori_ref = _rd("u_puzzle|ori", t_first - 2000.0)
    cells_ref = None
    for i, (k0, k1, _r, _c, _n) in enumerate(ROT_KEYS):
        t_a = S0 + (k1 + 8) * ROUND                  # 按键被接受 + 旋转检查（≤16 拍）之后
        pos_a = _rd("u_puzzle|pos", t_a)
        ori_a = _rd("u_puzzle|ori", t_a)
        sel_a = _rd("u_puzzle|sel", t_a)
        if None in (pos_a, ori_a, sel_a):
            rot_ok = False
            rot_notes.append("第%d次: 观测点缺失" % (i + 1))
            continue
        kb = (ori_ref >> (2 * sel_a)) & 3
        ka = (ori_a >> (2 * sel_a)) & 3
        good = (ka == kb) or (ka == (kb + 1) % 4)
        rrr, ggg, _s, _d = scan_panel(vf, t_a - 60_000.0, t_a + 60_000.0, step=1000.0)
        n_cells = cells(rrr, ggg)
        if cells_ref is None:
            cells_ref = n_cells
        rot_ok = rot_ok and good and (pos_a == pos_ref) and (n_cells == cells_ref)
        rot_notes.append("第%d次 sel=%d ori %d->%d(%s) pos%s 格数%d"
                         % (i + 1, sel_a, kb, ka, "OK" if good else "非法",
                            "不变" if pos_a == pos_ref else "**变了**", n_cells))
        ori_ref = ori_a
    res.append((
        "⑰ ★【A4 旋转 · 整机】按 KEY8 三次：朝向每次要么不变、要么恰好 +1（mod 4）；"
        "锚点 o_pos 全程不变；点亮格数守恒",
        rot_ok,
        "；".join(rot_notes) + "（参考格数 %s）" % cells_ref,
    ))

    # ========================================================================
    # ⭐ 2026-10-10 新增：**音效 · 整机**（此前这一块在整机层面完全没有断言）
    # ========================================================================
    def _snd(t):
        return _rd("u_fsm|sound_p", t)

    def _bursts(nm, t0, t1, step=20_000.0):
        """[t0,t1] 内 `nm` 为 '1' 的**连续区间个数**（= 响了几"声"）。
        方波本身在音频频率上翻转，所以判"响没响"要看 buzzer 侧的 `on_now` 门控，
        而不是直接数 `buzz` 的边沿。"""
        n, prev, t = 0, "0", t0
        while t <= t1:
            v = vf.value_at(nm, t) or "0"
            if v == "1" and prev != "1":
                n += 1
            prev, t = v, t + step
        return n

    # ⑱ 六个常驻场景的音效码（自检/待机/预览/一关对局/胜利/失败）
    cases = [
        (T_SELFTEST[0] + 200_000.0, 0x1, "自检 = POST 单声短鸣（0001）"),
        ((T_IDLE[0] + T_IDLE[1]) / 2, 0x0, "待机 = 静音（0000）"),
        ((T_PREVIEW[0] + T_PREVIEW[1]) / 2, 0x2, "预览 = 金币音（0010）"),
        ((T_PLAY[0] + T_PLAY[1]) / 2, 0x8, "第一关对局 = BGM1（1000）"),
        (T_WIN + 1_500_000.0, 0x6, "通关胜利 = 过关号角（0110）"),
        (T_FAIL_SCREEN + 1_500_000.0, 0x7, "失败 = Game Over（0111）"),
    ]
    bad = ["%s：实测 %s" % (nm, ("%04d" % bin(v)[2:]) if v is not None else "缺观测点")
           for (t, want, nm) in cases for v in [_snd(t)] if v != want]
    res.append((
        "⑱ ★【音效 · 整机】六个常驻场景的音效码经 `game_fsm.sound_p → buzzer_ctrl.i_sel` "
        "真的走到了蜂鸣器：自检 0001 / 待机 0000 / 预览 0010 / 一关 1000 / 胜利 0110 / 失败 0111",
        not bad,
        "；".join("%s t=%.0f 码=%s（期望 %s）"
                  % (nm, t, _snd(t), format(want, "04b")) for (t, want, nm) in cases)
        + ("；✗ " + "；".join(bad) if bad else ""),
    ))

    # ⑲ 三关三首 BGM 逐关不同
    #    ⚠️ 2026-10-10 第一次跑时的**假失败**（教训值得留档）：原来在"第三关对局开始后 2 ms"
    #       单点采样，结果读到 **1010（旋转音）** 而不是 1011 —— 因为走法计划的**第一条命令
    #       就是【旋转】**，而瞬时事件码会被 `snd_hold` 保持 **2 个旋律步（800 us）**，
    #       单点采样正好落在它的保持窗口里。⇒ 改成**扫描整个对局窗口**、
    #       判"这一关的 BGM 码**出现过**"（对按键事件码免疫）。
    #       这是"单点采样 vs 事件保持窗口"这类假失败的第二次出现（第一次在 ⑱ 的注释里）。
    def _codes_in(t0, t1, step=100_000.0):
        s, t = set(), t0
        while t <= t1:
            v = _snd(t)
            if v is not None:
                s.add(v)
            t += step
        return s

    lvl_win = [(T_L1_PREVIEW + 7_000_000.0, T_L2_CONF, 0x9, "第二关"),
               (T_L2_PREVIEW + 7_000_000.0, T_L3_CONF, 0xB, "第三关")]
    got = [(nm, want, _codes_in(a, b)) for (a, b, want, nm) in lvl_win]
    bad2 = ["%s：窗口内音效码集合 %s 不含 %s"
            % (nm, sorted(format(c, "04b") for c in s), format(want, "04b"))
            for (nm, want, s) in got if want not in s]
    res.append((
        "⑲ ★【音效 · 整机】**每一关一首不同的背景音乐**：一关 1000（⑱ 已测）、"
        "二关 1001、三关 1011 —— A1 的『不同情况播放不同音乐』在整机上成立"
        "（**扫描整段对局窗口**，对按键事件码免疫）",
        not bad2,
        "；".join("%s 对局窗口内音效码集合 = %s（应含 %s）"
                  % (nm, sorted(format(c, "04b") for c in s), format(want, "04b"))
                  for (nm, want, s) in got)
        + ("；✗ " + "；".join(bad2) if bad2 else ""),
    ))

    # ⑳ 按键音效：确认 1100 / 旋转 1010 / 移动与选择**保持 BGM 不变**
    sel_c = _snd((T_PLAY_SEL[0] + T_PLAY_SEL[1]) / 2)      # 【选择】之后
    dir_c = _snd((T_DIR[0] + T_DIR[1]) / 2)                # 方向键之后
    conf_c = _snd(T_CONF1)
    rot_c = _snd(T_ROT1)
    ok20 = (conf_c == 0xC and rot_c == 0xA and sel_c == 0x8 and dir_c == 0x8)
    res.append((
        "⑳ ★【音效 · 整机】对局里只有两个按键反馈音：**【确认】= 1100、【旋转】= 1010**；"
        "而**【选择】与方向键保持背景音乐码 1000 不变**（用户原话：上下左右不要额外音效）",
        ok20,
        "选择后=%s（期望 1000）；方向上/下/左/右后=%s（期望 1000）；"
        "确认=%s（期望 1100）；旋转=%s（期望 1010）"
        % (format(sel_c or 0, "04b"), format(dir_c or 0, "04b"),
           format(conf_c or 0, "04b"), format(rot_c or 0, "04b")),
    ))

    # ㉑ SW7=0 期间蜂鸣器恒不响（B1：所有显示器件不显示；`i_en` 同时门控蜂鸣器）
    off_hi = []
    t = T_OFF[0]
    while t <= T_OFF[1]:
        if (vf.value_at("buzz", t) or "0") == "1":
            off_hi.append("%.0f" % t)
        t += 20_000.0
    res.append((
        "㉑ ★【音效 · 整机】SW7=0 期间 `buzz` 恒为 '0'（B1：开关关掉时全部不显示，"
        "蜂鸣器也由 `i_en` 一起门控）",
        not off_hi,
        "在 [%.0f, %.0f] 内采样 %d 点，高电平点 %s"
        % (T_OFF[0], T_OFF[1], int((T_OFF[1] - T_OFF[0]) / 20_000.0) + 1,
           off_hi or "无"),
    ))

    # ㉒ ★【ERR-051 回归 · 整机】SW7 关→开之后的自检**恰好一声**
    #    自检音效的发声步是第 0/8 步，而 buzzer 的 `step` 是自由走的；
    #    窗口**恒 8 步**（㉓ 的时长判据 + tb_game_fsm ㉘ 的节拍判据）⇒ 8 个连续步
    #    **必然恰好包含**第 0 或第 8 步中的一个 ⇒ **恒为一声**。
    #    旧实现的窗口是 (1,2] s = 4~8 步 ⇒ 某些相位**一声都不响**（板上"自检没声音"）。
    n_burst = _bursts("u_buzz|on_now", T_SW2_SELF_SCAN[0], T_SW2_SELF_SCAN[1])
    st_mid = _rd("u_fsm|st", T_SW2_SELF_MIN)
    res.append((
        "㉒ ★【ERR-051 回归 · 整机】SW7 关→开之后自检窗口内蜂鸣器**恰好响一声**，"
        "且窗口中段仍在自检态（窗口恒 8 个旋律步 ⇒ 必含第 0 或第 8 步之一）",
        n_burst == 1 and st_mid == 0,
        "扫描窗口 [%.0f, %.0f]：`u_buzz|on_now` 连续区间 **%d** 个（期望 1）；"
        "t=%.0f 时状态=%s（期望 0 自检）"
        % (T_SW2_SELF_SCAN[0], T_SW2_SELF_SCAN[1], n_burst, T_SW2_SELF_MIN, st_mid),
    ))

    return res


def _bus_trace(vf, name):
    sig = vf.signals[name]
    times = set()
    for bit in range(sig.width):
        for (t, _lv) in vf.trace("%s[%d]" % (name, bit)):
            times.add(t)
    out = []
    for t in sorted(times):
        v = vf.bus_value_at(name, t + 1e-9)
        if not out or out[-1][1] != v:
            out.append((t, v))
    return out
