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
    tick_1hz = 1.6 ms（"1 秒"）    tick_2hz = 800 us（2 Hz 半周期）
    上电复位 ~16 us；矩阵扫描 SETTLE 拍在 32 + 16k us。
"""

CLK = 20.0
GRID_PERIOD = 10.0

RTL_PATCHES = [("puzzle_pkg.vhd", "50_000_000", "80_000"),
               # 第三场景要按"哪一块会落到哪里"写出按键计划，所以把随机源钉成 0
               # （只作用于 .tmp 隔离工程）：rnd_val 恒 0 → 每块候选恒为 (0,0)
               # → 16 次重试后落到**确定性回退锚点**
               ("puzzle_pkg.vhd", 'x"5A"', 'x"00"')]

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

# 按键计划：(首轮, 末轮, 行, 列, 说明)
#   原始键号 1 = (行0,列1) → game_fsm 译为【开始】
#   原始键号 3 = (行0,列3) → 【选择】
#   ★ 方向键：按**新映射**的十字键各按一次（键号 = 4*行+列）：
#     下=键号2(KEY15) 左=键号5(KEY10) 右=键号7(KEY12) 上=键号10(KEY7) 确认=键号6(KEY11)
#     （键号 0 = KEY13 永远不用：扫描器用 0 表示"无键"）
#     窗口取 21 轮（消抖要 16 个样本，留足余量），相邻按键间隔 25 轮。
KEY_PLAN = [
    (196, 228, 0, 1, "开始 KEY14"),
    (950, 985, 0, 3, "选择 KEY16"),
    (1092, 1112, 0, 2, "下 KEY15"),
    (1117, 1137, 1, 1, "左 KEY10"),
    (1142, 1162, 1, 3, "右 KEY12"),
    (1167, 1187, 2, 2, "上 KEY7"),
    (1192, 1212, 1, 2, "确认 KEY11"),
]
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
            "up": (2, 2), "down": (0, 2), "left": (1, 1), "right": (1, 3)}

# 一关：三块从回退锚点搬到目标锚点 (0,0)->(2,2)、(0,4)->(3,2)、(4,0)->(4,3)
PLAN_L1 = (["select"] + ["down"] * 3 + ["left"] * 2 +
           ["select"] + ["down"] * 2 + ["right"] * 3 + ["up"] * 2 +
           ["select"] + ["down"] * 2 + ["right"] * 2 +
           ["confirm"] * 3)
# 二关：四块 2x2 摆成目标锚点集的**一个置换**（P0 与 P2 交换）—— 画面仍是目标图案，
#       但锚点元组 != 写死的 L2_TGT，正是 ERR-021 的回归点
PLAN_L2 = (["right"] * 2 + ["down"] * 4 +
           ["select"] + ["down"] * 2 +
           ["select"] + ["up"] * 2 + ["right"] * 2 +
           ["select"] + ["confirm"] * 4)

HOLD = 22          # 按住多少轮（消抖要 16 轮，留 6 轮余量）
GAP_NEW = 25       # 换一个键：间隔轮数（松开 3 轮即可，因为换了键号）
GAP_SAME = 44      # **同一个键要再按一次**：必须先让扫描器看到"松开"——
                   # keypad_scan 的消抖是"连续 16 轮不同才改 stable"，所以松开窗口
                   # 必须 > 16 轮，否则第二次按同一个键根本不会被识别。

# SW7 再拨上去之后的基轮号（自检 2 s = 200 轮之后）
K2_START = 1980    # 待机里按【开始】
K2_L1 = 2600       # 第一关第一个动作（预览 5 s = 500 轮之后，留 100 轮余量）


def _plan_keys(k0, names):
    """命令名序列 -> [(首轮, 末轮, 行, 列, 名字)]，返回 (按键计划, 下一个可用轮号)。

    ⚠️ 间隔必须看**下一个**命令用的是不是同一个键：`_plan_keys` 第一版按"当前命令
    与上一个命令是否同键"来留间隔（差一位），于是 `down,down` 之间只隔了 25 轮 ——
    松开窗口只有 3 轮，扫描器的消抖（连续 16 轮不同才改 stable）根本看不到松开，
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

KEY_PLAN2 = ([(K2_START, K2_START + HOLD - 1, 0, 1, "start(第二场景)")] +
             KEYS_L1 + KEYS_L2)

# ---- 各阶段时间点（ns）----
T_SELFTEST = (300_000.0, 3_100_000.0)
T_IDLE = (3_225_000.0, 3_385_000.0)        # 进待机(3.20 ms)之后、按开始生效之前
T_PREVIEW = (4_500_000.0, 10_800_000.0)
T_PLAY = (11_900_000.0, 15_000_000.0)      # 散落完成后的对局（sel = 0）
T_PLAY_SEL = (15_800_000.0, 17_300_000.0)  # 按过"选择"之后
T_DIR = (17_600_000.0, 19_900_000.0)       # ★ 按方向键的时段（ERR-020 的回归窗口）
T_SW_OFF = 21_200_000.0                    # SW7 拨下去（B1）
T_OFF = (21_800_000.0, 22_600_000.0)       # SW7=0 之后
T_SW_ON2 = 27_000_000.0                    # SW7 再拨上去（自检 2 s -> 待机）
T_L1_CONF = S0 + (KEYS_L1[-1][0] + 24) * ROUND       # 第一关最后一次确认之后
T_L1_PREVIEW = T_L1_CONF + 1_000_000.0               # 应已进入第二关预览（预览 8 ms）
T_L2_CONF = S0 + (KEYS_L2[-1][0] + 24) * ROUND       # 第二关最后一次确认之后
T_WIN = T_L2_CONF + 1_000_000.0                      # 应已进入胜利状态
DURATION = T_WIN + 4_000_000.0

OBSERVE = ["clk", "sw7", "btn", "kp_row", "kp_col",
           "dot_row", "dot_colr", "dot_colg", "seg", "cat", "buzz",
           # 中间信号：顶层自己的 mrow/mat_r 在网表里存在；其余内部信号按
           # 「实例标签|信号名」的层次写法（已用探针实测确认能匹配上）
           "mrow", "mat_r",
           "u_clk|t2", "u_keypad|key_r", "u_keypad|stable", "u_seg|idx",
           "u_fsm|st", "u_fsm|cnt", "u_fsm|level",
           "u_fsm|up_r", "u_fsm|down_r", "u_fsm|left_r", "u_fsm|right_r",
           "u_fsm|move_r", "u_fsm|conf_r", "u_fsm|sel_r",
           "u_puzzle|pos", "u_puzzle|locked", "u_puzzle|mv_dir",
           "u_puzzle|mv_pend", "u_puzzle|chk_pos"]

# 段码 -> 数字（与 rtl/seg_scan.vhd 的共阴译码表一致；blank = 0x00）
DIGITS = {0x3F: "0", 0x06: "1", 0x5B: "2", 0x4F: "3", 0x66: "4",
          0x6D: "5", 0x7D: "6", 0x07: "7", 0x7F: "8", 0x6F: "9", 0x00: " "}


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
                 ("u_fsm|level", 1),
                 ("u_fsm|up_r", 1), ("u_fsm|down_r", 1),
                 ("u_fsm|left_r", 1), ("u_fsm|right_r", 1),
                 ("u_fsm|move_r", 1), ("u_fsm|conf_r", 1), ("u_fsm|sel_r", 1),
                 ("u_puzzle|pos", 32), ("u_puzzle|locked", 4),
                 ("u_puzzle|mv_dir", 4), ("u_puzzle|mv_pend", 1),
                 ("u_puzzle|chk_pos", 8)):
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
    for (k0, k1, r, c, _n) in (KEY_PLAN + KEY_PLAN2):
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
        t += 20_000.0                       # 20 us 一个采样点（远小于 800 us 半周期）
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
    res.append((
        "⑩ ★【整机·第一关】用真实矩阵按键把三块摆回目标锚点并逐块确认后，"
        "状态机必须进入**第二关预览**（o_level=1）—— 修复前这里是判负出叉"
        "（ERR-023：对局态喂给引擎的目标图案被置零，成功判据永远不可能成立）",
        pos1 == 0x22324300 and lock1 is not None and (lock1 & 0x7) == 0x7
        and st_l1 == 2 and lv_l1 == "1",
        "确认后锚点=0x%s（期望 0x22324300）、locked=%s；1 ms 后 o_state=%s（2=预览）、"
        "o_level=%s"
        % ("--------" if pos1 is None else format(pos1, "08X"),
           "----" if lock1 is None else format(lock1, "04b"), st_l1, lv_l1),
    ))

    # ⑪ ★ 第二关：四块 2x2 摆成目标锚点集的**一个置换**（画面与目标一致）+ 全确认 → 胜利
    pos2 = vf.bus_value_at("u_puzzle|pos", T_L2_CONF)
    lock2 = vf.bus_value_at("u_puzzle|locked", T_L2_CONF)
    st_l2 = vf.bus_value_at("u_fsm|st", T_WIN)
    res.append((
        "⑪ ★【整机·第二关】四块摆成目标锚点集的**一个置换**（画面与目标图案逐格一致，"
        "但锚点元组 != 写死的 L2_TGT）并全部确认 → **胜利状态**（B10；ERR-021 的整机回归）",
        pos2 == 0x42242244 and lock2 == 0xF and st_l2 == 4,
        "确认后锚点=0x%s（期望 0x42242244）、locked=%s；1 ms 后 o_state=%s（4=胜利）"
        % ("--------" if pos2 is None else format(pos2, "08X"),
           "----" if lock2 is None else format(lock2, "04b"), st_l2),
    ))

    # ⑫ 整个第三场景的状态序列：自检 → 待机 → 预览 → 对局 → 预览 → 对局 → 胜利
    #    ⚠️ 窗口从 **T_SW_OFF**（拨下去那一刻）开始数，不是 T_SW_ON2：SW7=0 期间
    #    状态机就停在"自检"上，拨回来时不会再产生一次跳变，所以从 T_SW_ON2 起数会
    #    看不到开头那个"自检"（第一版就是这么错的）。
    seq2 = []
    for (tt, v) in _bus_trace(vf, "u_fsm|st"):
        if tt >= T_SW_OFF and (not seq2 or seq2[-1][1] != v):
            seq2.append((tt, v))
    got2 = [names.get(v, str(v)) for (_t, v) in seq2]
    res.append((
        "⑫ 第三场景的状态序列 = 自检 → 待机 → 预览 → 对局 → **预览 → 对局 → 胜利**"
        "（即真的连过两关；也说明没有「还没散落就判胜/判负」的残留状态跳变）",
        got2[:7] == ["自检", "待机", "预览", "对局", "预览", "对局", "胜利"],
        "状态序列 = %s" % " → ".join(got2),
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
