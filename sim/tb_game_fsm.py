# -*- coding: utf-8 -*-
"""tb_game_fsm.py —— game_fsm 功能仿真（整条游戏流程 B1~B11）

【这一轮要回答什么】
    `game_fsm` 掌管**时间与判决**：自检 2 s、预览 5 s、一关 30 s、二关 40 s、
    超时/拼错判负、过关换关、随时重开。它是本项目"限时"类缺陷的集中地 ——
    ERR-005（进关时限时**从未加载**，不到 1 秒就判负）和 ERR-006（散落握手没有
    "完成"记忆 → 无限重复散落）就出在这里，而且**两条都不是看波形能看出来的**。

    所以本轮不摆"好看的波形"，而是**按需求逐条对时序下判据**：
      ① 复位后进自检，2 个 1 Hz 节拍后进待机（B1/B2）；
      ② 待机时按"开始"→ 预览，且 o_time = 5（B4）；
      ③ 预览结束时 **o_time 必须被加载成 30**（B5，ERR-005 的回归判据）；
      ④ 对局中 6 个控制键各自产生**恰好一次、1 个时钟宽**的动作脉冲（B6/B7/B8）；
         —— 且待机/预览时按键**不产生**任何动作脉冲（只在 S_PLAYING 生效）；
      ⑤ 散落请求 o_go 每局**只上升一次**（ERR-006 的回归判据）；
      ⑥ 一关 30 秒到 → 失败（B9 超时判负）；
      ⑦ 失败后按"开始"可重开，且回到**第一关**（B11）；
      ⑧ 一关 i_solved=1 → 进第二关，预览后 **o_time = 40**（B10）；
      ⑨ 二关 i_solved=1 → 胜利（B10）；
      ⑩ 胜利后按"开始"又能进预览（B11）；
      ⑪ 对局中 i_all_lock=1 且引擎空闲 → 判负（B9"拼错"）；
      ⑫ SW7=0 → 立刻回到自检并清空（B1）；
      ⑬ o_blink 是 **2 Hz 方波（电平持续半个周期）**，不是单时钟脉冲（ERR-011）。

【时间刻度】这里用一个"仿真秒" = 2000 ns（100 个 20 ns 时钟）。
    1 Hz 节拍在 t = 2000, 4000, 6000 ... 各来一个时钟宽；2 Hz 节拍每 1000 ns。
    模块只数节拍、不关心真实频率，所以整局游戏能在 126 us 内跑完 —— 这也是
    "仿真时间与真实时间可以解耦"的一个实例（真实节拍来自 clk_gen 的分频链）。
"""

CLK = 20.0
T1 = 2000.0          # "1 Hz"节拍周期
T2 = 1000.0          # "2 Hz"节拍周期
GRID_PERIOD = 10.0
DURATION = 158000.0

S_SELF, S_IDLE, S_PREV, S_PLAY, S_WIN, S_FAIL = 0, 1, 2, 3, 4, 5
T_PREVIEW, T_L1, T_L2 = 5, 30, 40          # 课程要求 B4 / B5 / B10

# 键码（模块内部译码前的**原始键号** = 4*行 + 列，与 game_fsm.key_of 的映射表一致）
#
# ⚠️ 2026-10-08 全量重跑时抓到的一处 **tb 陈旧常量**（不是 RTL 缺陷）：
#    键位表按板子手册附图26 重排后（开始=1/KEY14、选择=3/KEY16、上=10/KEY7、
#    下=2/KEY15、左=5/KEY10、右=7/KEY12、确认=6/KEY11），本文件的 RAW_UP/DOWN/
#    LEFT/RIGHT 仍是**旧表**的 (4,5,0,2) —— 在新表里这四码分别译成
#    K_NONE / K_LEFT / K_NONE / K_DOWN，于是"上""右"两键根本没产生动作脉冲。
#    当时 game_fsm 的轮次记录（r04, 17:56）是**重排之前**跑的，所以没暴露；
#    重排提交（18:45）之后一直没人重跑这个模块 → 记录是"陈旧绿"。
#    教训：改了 key_of() 必须重跑 game_fsm；汇总"全部通过"时要看每条的**时间戳**。
RAW_START, RAW_SELECT, RAW_CONFIRM = 1, 3, 6
RAW_UP, RAW_DOWN, RAW_LEFT, RAW_RIGHT = 10, 2, 5, 7

# 按键事件：(时刻, 原始键号, 备注)
PRESSES = [
    (4600,   RAW_UP,      "待机时按上 —— 不应产生动作"),
    (5000,   RAW_START,   "待机 -> 预览"),
    (7000,   RAW_CONFIRM, "预览时按确认 —— 不应产生动作"),
    (17000,  RAW_SELECT,  "一关对局：选择"),
    (19000,  RAW_UP,      "一关对局：上"),
    (21000,  RAW_CONFIRM, "一关对局：确认"),
    (23000,  RAW_DOWN,    "一关对局：下"),
    (25000,  RAW_LEFT,    "一关对局：左"),
    (27000,  RAW_RIGHT,   "一关对局：右"),
    (76000,  RAW_START,   "超时失败后重开"),
    (104000, RAW_START,   "胜利后重开"),
    (128000, RAW_START,   "第三场景：SW7 再拨上后开始（自检 2 s 已过）"),
    (142000, RAW_START,   "第四场景：残留判负后重开"),
]

# i_solved / i_all_lock / i_shuf_busy 的时间窗
# ⚠️ 第三/第四场景是 ERR-024 的回归激励：**故意让上一局的 i_solved / i_all_lock
#    残留到新一局对局开始之后**（上板现象：退出重进直接跳第二关 / 刚开局就判负），
#    而 i_shuf_busy 故意晚 2 个时钟才起来（引擎要等"散落请求"那一两拍），
#    这样就能精确复现"判决发生在散落之前"的窗口。
SOLVED_WINS = [(88000.0, 90000.0), (100000.0, 102000.0), (142500.0, DURATION)]
ALL_LOCK_WINS = [(116000.0, 118000.0), (122000.0, DURATION)]
# ⚠️ 2026-10-08 修正：本表原来只给**两个**对局建了散落忙窗，可 `game_fsm` 现在要求
#    "本局至少看到过一次散落"（ERR-024）；而真实引擎**每一局**都会散落，所以这里
#    给 6 个对局各建一个"开局后不久"的忙窗（也顺便更贴近真实时序：玩家不可能在
#    散落还没跑完时就拼好）。第一版漏建的两局直接把 ⑨⑩⑪⑬⑰ 拖挂（r08 = 12/17）。
SHUF_BUSY_WINS = [(14060.0, 15000.0), (86060.0, 87000.0), (98060.0, 99000.0),
                  (114060.0, 115000.0), (138060.0, 140060.0), (152060.0, 154060.0)]
T_SW_ON2 = 122000.0                       # SW7 再拨上去（自检 2 s -> 待机）
T_PLAY3 = 138020.0                        # 第三局对局开始（推算：见 §1.2 时间表）
SW_OFF = (120000.0, T_SW_ON2)

OBSERVE = ["i_clk", "i_sw", "i_press", "i_key", "i_tick_1hz", "i_tick_2hz",
           "i_solved", "i_all_lock", "i_shuf_busy",
           "o_state", "o_level", "o_time", "o_blink", "o_go",
           "o_sel", "o_conf", "o_move", "o_up", "o_down", "o_left", "o_right",
           "st", "cnt", "level", "req_go", "go_done", "blink_r"]


# ---------------------------------------------------------------- 激励
def _buried(b, name, width):
    for n in [name] + ["%s[%d]" % (name, i) for i in range(width)]:
        sig = b.vf.signals.get(n)
        if sig is not None:
            sig.direction = "BURIED"


def _tl(duration, spans, default):
    """[(起, 止, 值)] -> [(时长, 值)]，覆盖 [0, duration)。

    ⚠️ 不能靠"事件排序"来实现：两段**首尾相接**的区间（如 i_sw 的 1→0 翻转点）
    会落在同一时刻，排序结果依赖插入顺序，很容易把后一段吃掉（本文件第一版就
    这样把 i_sw 的下降沿推迟到了仿真末尾）。所以这里按**区间求值**：
    对每个划分点求"包含该时刻的区间值"，重叠时取最后一个匹配的区间。
    """
    pts = sorted(set([0.0, float(duration)]
                     + [a for (a, _b, _v) in spans]
                     + [b for (_a, b, _v) in spans]))
    segs = []
    for i in range(len(pts) - 1):
        t0, t1 = pts[i], pts[i + 1]
        v = default
        for (a, b, val) in spans:
            if a <= t0 < b:
                v = val
        segs.append((t1 - t0, v))
    return segs


def _tick(duration, period):
    """在 t = period, 2*period, ... 处各来一个 CLK 宽的节拍脉冲。"""
    n = int(duration // period)
    return _tl(duration, [(k * period, k * period + CLK, 1) for k in range(1, n + 1)], 0)


def build(b):
    b.input_bit("i_clk")
    b.input_bit("i_rst")
    b.input_bit("i_sw")
    b.input_bit("i_tick_1hz")
    b.input_bit("i_tick_2hz")
    b.input_bit("i_press")
    b.input_bus("i_key", 4)
    b.input_bit("i_solved")
    b.input_bit("i_all_lock")
    b.input_bit("i_shuf_busy")
    b.output_bus("o_state", 3)
    b.output_bit("o_level")
    b.output_bus("o_time", 6)
    b.output_bit("o_blink")
    b.output_bit("o_go")
    b.output_bit("o_sel")
    b.output_bit("o_conf")
    b.output_bit("o_move")
    b.output_bit("o_up")
    b.output_bit("o_down")
    b.output_bit("o_left")
    b.output_bit("o_right")
    for n, w in (("st", 3), ("cnt", 6), ("level", 1), ("req_go", 1),
                 ("go_done", 1), ("blink_r", 1)):
        if w == 1:
            b.output_bit(n)
        else:
            b.output_bus(n, w)
        _buried(b, n, w)

    b.clock("i_clk", CLK)
    b.segments("i_rst", [(100.0, 1), (DURATION - 100.0, 0)])
    b.segments("i_sw", _tl(DURATION, [(0.0, SW_OFF[0], 1),
                                      (SW_OFF[0], SW_OFF[1], 0),
                                      (SW_OFF[1], DURATION, 1)], 1))
    b.segments("i_tick_1hz", _tick(DURATION, T1))
    b.segments("i_tick_2hz", _tick(DURATION, T2))

    # i_press: 一个时钟宽的脉冲；i_key: 脉冲前后各放宽 100 ns（保证建立时间）
    b.segments("i_press", _tl(DURATION, [(t, t + CLK, 1) for (t, _k, _n) in PRESSES], 0))
    b.bus_segments("i_key", _tl(DURATION, [(t - 100.0, t + 100.0, k)
                                           for (t, k, _n) in PRESSES], 0))

    b.segments("i_solved", _tl(DURATION, [(a, b_, 1) for (a, b_) in SOLVED_WINS], 0))
    b.segments("i_all_lock", _tl(DURATION, [(a, b_, 1) for (a, b_) in ALL_LOCK_WINS], 0))
    b.segments("i_shuf_busy", _tl(DURATION, [(a, b_, 1) for (a, b_) in SHUF_BUSY_WINS], 0))


# ---------------------------------------------------------------- 断言工具
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


def _bus_at(vf, name, t):
    return vf.bus_value_at(name, t)


def _bit_at(vf, name, t):
    """单比特信号取电平（声明成 output_bit 的节点不是总线）。"""
    return vf.value_at(name, t)


def _rises(vf, name):
    """所有上升沿时刻。"""
    out, prev = [], None
    for (t, v) in vf.trace(name):
        if v == "1" and prev is not None and prev != "1":
            out.append(t)
        prev = v
    return out


def _first_state(vf, want, after=0.0):
    for (t, v) in _bus_trace(vf, "o_state"):
        if v == want and t >= after:
            return t
    return None


def check(vf):
    res = []
    st_tr = _bus_trace(vf, "o_state")

    # ① 复位 -> 自检；2 个 1 Hz 节拍后 -> 待机
    t_idle = _first_state(vf, S_IDLE)
    res.append((
        "① 复位后进自检，2 个 1 Hz 节拍后进待机（B1/B2：自检 2 秒）",
        _bus_at(vf, "o_state", 1000.0) == S_SELF and t_idle is not None
        and abs(t_idle - (2 * T1 + CLK)) < CLK,
        "t=1000ns 状态=%s（期望 %d 自检）；进入待机时刻=%.0f ns（期望 %.0f ns = 2 个节拍）"
        % (_bus_at(vf, "o_state", 1000.0), S_SELF, -1 if t_idle is None else t_idle,
           2 * T1 + CLK),
    ))

    # ② 待机按开始 -> 预览，o_time = 5
    t_prev = _first_state(vf, S_PREV)
    res.append((
        "② 待机时按【开始】→ 预览状态，且 o_time = 5（B4：预览 5 秒）",
        t_prev is not None and _bus_at(vf, "o_time", t_prev + 100.0) == T_PREVIEW,
        "进预览时刻=%.0f ns，o_time=%s（期望 %d）"
        % (-1 if t_prev is None else t_prev,
           _bus_at(vf, "o_time", (t_prev or 0) + 100.0), T_PREVIEW),
    ))

    # ③ ★ ERR-005 回归：预览结束进对局时，限时**必须**被加载
    t_play = _first_state(vf, S_PLAY)
    res.append((
        "③ ★ 预览结束进对局时 o_time 被加载为 30（B5：一关 30 秒）——"
        " ERR-005 的回归判据（限时从未加载会让对局不到 1 秒就判负）",
        t_play is not None and _bus_at(vf, "o_time", t_play + 100.0) == T_L1,
        "进对局时刻=%.0f ns，o_time=%s（期望 %d）"
        % (-1 if t_play is None else t_play,
           _bus_at(vf, "o_time", (t_play or 0) + 100.0), T_L1),
    ))

    K1 = t_play or 0.0
    K1_END = 74000.0

    # ④ 六个控制键 → 恰好一次、1 时钟宽的动作脉冲
    def pulses_in(name, lo, hi):
        return [t for t in _rises(vf, name) if lo <= t <= hi]

    man = [("o_sel", 17020.0, "选择"), ("o_up", 19020.0, "上"),
           ("o_conf", 21020.0, "确认"), ("o_down", 23020.0, "下"),
           ("o_left", 25020.0, "左"), ("o_right", 27020.0, "右")]
    bad = []
    for (nm, want_t, cn) in man:
        got = pulses_in(nm, K1, K1_END)
        if len(got) != 1 or abs(got[0] - want_t) > CLK + 1:
            bad.append("%s(%s) 脉冲=%s（期望 1 个、约 %.0f ns）" % (nm, cn, got, want_t))
    moves = pulses_in("o_move", K1, K1_END)
    if len(moves) != 4:
        bad.append("o_move 脉冲=%s（期望 4 个：上下左右各一次）" % moves)
    res.append((
        "④ 一关对局中 6 个控制键各产生恰好一次动作脉冲（选择/确认各 1 次，"
        "方向键 4 次 o_move）",
        not bad,
        "；".join(bad) if bad else
        "o_sel@%.0f o_up@%.0f o_conf@%.0f o_down@%.0f o_left@%.0f o_right@%.0f，"
        "o_move 共 %d 次"
        % tuple([pulses_in(n, K1, K1_END)[0] for n, _t, _c in man] + [len(moves)]),
    ))

    # ⑤ 待机/预览时按键不得产生动作脉冲（动作只在 S_PLAYING 生效）
    early = []
    for nm in ("o_sel", "o_conf", "o_move", "o_up", "o_down", "o_left", "o_right"):
        early += [t for t in _rises(vf, nm) if t < K1]
    res.append((
        "⑤ 待机(4600ns 按上)与预览(7000ns 按确认)期间**不产生**任何动作脉冲",
        not early,
        "对局前出现的动作脉冲：%s" % (early or "无"),
    ))

    # ⑥ ★ ERR-006 回归：每局散落请求 o_go 只上升一次
    go_r = _rises(vf, "o_go")
    res.append((
        "⑥ ★ o_go 每局只上升一次、全流程共 6 局 = 6 次（ERR-006：散落握手必须有"
        "'完成'记忆，否则会无限重复散落、清掉选中/锁定，按键全部失效）",
        len(go_r) == 6,
        "o_go 上升沿时刻：%s（共 %d 次，期望 6）"
        % (", ".join("%.0f" % t for t in go_r), len(go_r)),
    ))

    # ⑦ 一关 30 秒到 -> 失败
    t_fail = _first_state(vf, S_FAIL)
    expect_fail = (K1 // T1) * T1 + T_L1 * T1 + CLK
    res.append((
        "⑦ 一关对局 30 秒（30 个 1 Hz 节拍）到 → 失败状态（B9 超时判负）",
        t_fail is not None and abs(t_fail - expect_fail) < 2 * CLK,
        "进失败时刻=%.0f ns，期望 %.0f ns（= 进对局那一拍 + 30 个节拍）"
        % (-1 if t_fail is None else t_fail, expect_fail),
    ))

    # ⑧ 失败后按开始重开，且回到第一关
    t_prev2 = _first_state(vf, S_PREV, after=(t_fail or 0) + 1.0)
    res.append((
        "⑧ 超时失败后按【开始】可重开新一轮，且关卡回到第一关（B11；o_level=0、o_time=5）",
        t_prev2 is not None and _bit_at(vf, "o_level", t_prev2 + 100.0) == "0"
        and _bus_at(vf, "o_time", t_prev2 + 100.0) == T_PREVIEW,
        "重开时刻=%.0f ns，o_level=%s，o_time=%s"
        % (-1 if t_prev2 is None else t_prev2,
           _bit_at(vf, "o_level", (t_prev2 or 0) + 100.0),
           _bus_at(vf, "o_time", (t_prev2 or 0) + 100.0)),
    ))

    # ⑨ 一关拼对 -> 第二关（level=1），预览 5 秒
    cand = [t for (t, v) in st_tr if v == S_PREV and t > 86000.0]
    t_l2prev = cand[0] if cand else None
    res.append((
        "⑨ 一关对局中 i_solved=1 → 关卡变 1 并回到预览（B9：拼对进入第二关，预览仍 5 秒）",
        t_l2prev is not None and _bit_at(vf, "o_level", t_l2prev + 100.0) == "1"
        and _bus_at(vf, "o_time", t_l2prev + 100.0) == T_PREVIEW,
        "二关预览时刻=%.0f ns，o_level=%s，o_time=%s"
        % (-1 if t_l2prev is None else t_l2prev,
           _bit_at(vf, "o_level", (t_l2prev or 0) + 100.0),
           _bus_at(vf, "o_time", (t_l2prev or 0) + 100.0)),
    ))

    # ⑩ 二关对局限时 = 40 秒
    cand2 = [t for (t, v) in st_tr if v == S_PLAY and t > 96000.0]
    t_p2 = cand2[0] if cand2 else None
    res.append((
        "⑩ 第二关对局 o_time 被加载为 40（B10：二关 40 秒）",
        t_p2 is not None and _bus_at(vf, "o_time", t_p2 + 100.0) == T_L2,
        "二关对局时刻=%.0f ns，o_time=%s（期望 %d）"
        % (-1 if t_p2 is None else t_p2,
           _bus_at(vf, "o_time", (t_p2 or 0) + 100.0), T_L2),
    ))

    # ⑪ 二关拼对 -> 胜利
    t_win = _first_state(vf, S_WIN)
    res.append((
        "⑪ 第二关对局中 i_solved=1 → 胜利状态（B10）",
        t_win is not None,
        "进胜利状态时刻=%s" % ("%.0f ns" % t_win if t_win else "从未进入"),
    ))

    # ⑫ 胜利后按开始 -> 预览
    t_prev3 = [t for (t, v) in st_tr if v == S_PREV and t > 100500.0]
    res.append((
        "⑫ 胜利后按【开始】再次进入预览（B11：游戏结束后可开新一轮）",
        len(t_prev3) > 0,
        "胜利后的预览时刻：%s" % (["%.0f" % t for t in t_prev3] or "无"),
    ))

    # ⑬ 拼错判负：i_all_lock=1 且引擎空闲
    res.append((
        "⑬ 对局中 i_all_lock=1 且 i_shuf_busy=0 → 判负（B9：全部锁定但位置形状不对）",
        _bus_at(vf, "o_state", 116100.0) == S_FAIL,
        "i_all_lock 置位后的状态 = %s（期望 %d 失败）"
        % (_bus_at(vf, "o_state", 116100.0), S_FAIL),
    ))

    # ⑭ SW7=0 立刻回自检并清空
    res.append((
        "⑭ SW7=0 立刻回到自检并清零（B1：开关关掉时全部不显示）",
        _bus_at(vf, "o_state", 120100.0) == S_SELF
        and _bit_at(vf, "o_level", 120100.0) == "0"
        and _bus_at(vf, "o_time", 120100.0) == 0,
        "SW 拉低后 o_state=%s（期望 %d）、o_level=%s、o_time=%s"
        % (_bus_at(vf, "o_state", 120100.0), S_SELF,
           _bit_at(vf, "o_level", 120100.0), _bus_at(vf, "o_time", 120100.0)),
    ))

    # ⑮ o_blink 是 2 Hz 方波（电平），不是单时钟脉冲
    n_t2 = int(DURATION // T2)
    rises = _rises(vf, "o_blink")
    hi_w, last_rise = [], None
    for (t, v) in vf.trace("o_blink"):
        if v == "1" and last_rise is None:
            last_rise = t
        elif v != "1" and last_rise is not None:
            hi_w.append(t - last_rise)
            last_rise = None
    med = sorted(hi_w)[len(hi_w) // 2] if hi_w else -1
    res.append((
        "⑮ o_blink 是 2 Hz **方波**：每次节拍翻转一次、高电平持续半个周期（%.0f ns），"
        "不是'单时钟脉冲当闪烁电平'（ERR-011）" % T2,
        len(rises) >= 20 and hi_w and abs(med - T2) < 2 * CLK,
        "上升沿 %d 次（期望约 %d）；高电平宽度中位数=%.0f ns"
        % (len(rises), n_t2 // 2, med),
    ))

    # ================================================================
    # 第三/第四场景：ERR-024（新一局开头拿上一局的残留状态判决）
    # ================================================================
    # ⑯ 残留的 i_all_lock=1 不得在散落之前判负
    st_after_play = _bus_at(vf, "o_state", T_PLAY3 + 60.0)     # 对局开始后 3 拍
    fails3 = [t for (t, v) in st_tr if v == S_FAIL and t > 135000.0]
    t_fail3 = fails3[0] if fails3 else None
    res.append((
        "⑯ ★【ERR-024】新一局对局刚开始、散落还没起来时，上一局残留的 i_all_lock=1 "
        "**不得**判负：状态机必须在 S_PLAYING 里等散落（忙→闲）之后才判决",
        st_after_play == S_PLAY and t_fail3 is not None and t_fail3 > 140060.0,
        "对局开始后 3 拍仍是 %s（期望 %d 对局）；本轮首次判负时刻=%s（必须晚于散落结束 140060 ns）"
        % (st_after_play, S_PLAY, "-" if t_fail3 is None else "%.0f ns" % t_fail3),
    ))

    # ⑰ 残留的 i_solved=1 不得在散落之前把关卡推进到第二关
    prevs4 = [t for (t, v) in st_tr if v == S_PREV and t > 150000.0]
    t_prev4 = prevs4[0] if prevs4 else None
    st_wait = _bus_at(vf, "o_state", 152100.0)                 # 对局开始后 4 拍
    res.append((
        "⑰ ★【ERR-024】新一局对局刚开始时残留的 i_solved=1 **不得**立刻推进关卡："
        "必须先看到散落（忙→闲），之后才允许按 i_solved 进第二关预览（o_level=1）",
        st_wait == S_PLAY and t_prev4 is not None and t_prev4 > 154060.0
        and _bit_at(vf, "o_level", t_prev4 + 100.0) == "1",
        "对局开始后 4 拍仍是 %s（期望 %d 对局）；进第二关预览时刻=%s"
        "（必须晚于散落结束 154060 ns）、此刻 o_level=%s"
        % (st_wait, S_PLAY, "-" if t_prev4 is None else "%.0f ns" % t_prev4,
           _bit_at(vf, "o_level", (t_prev4 or 0) + 100.0)),
    ))

    return res
