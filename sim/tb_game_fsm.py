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
      ⑨ 二关 i_solved=1 → 进**第三关**预览（A2"增加游戏关数"），预览后 o_time = 40；
      ⑩ 三关 i_solved=1 → **胜利**（A2/D2：第三关是最后一关）；
      ⑪ 胜利后按"开始"又能进预览（B11，且关卡回第一关）；
      ⑫ 对局中 i_all_lock=1 且引擎空闲 → 判负（B9"拼错"）；
      ⑬ SW7=0 → 立刻回到自检并清空（B1）；
      ⑭ o_blink 是 **2 Hz 方波（电平持续半个周期）**，不是单时钟脉冲（ERR-011）。

【D2（2026-10-09 第 12 工作阶段）：第三关的时间轴】
    场景 2 现在要连过三关（二关拼对不再直接胜利），所以 104000 之后的**全部**事件、
    判据窗口与采样时刻统一后移 `D3_SHIFT`（= 20000 ns）；第三关自己新增了一对窗口
    （散落忙窗 110060~111000、拼对窗 116000~118000）→ 第三关拼对后进胜利。
    所有尾段常量都由 `D3_SHIFT` 推导，不许写死字面量（ERR-034 的教训）。

【时间刻度】这里用一个"仿真秒" = 2000 ns（100 个 20 ns 时钟）。
    1 Hz 节拍在 t = 2000, 4000, 6000 ... 各来一个时钟宽；2 Hz 节拍每 1000 ns。
    模块只数节拍、不关心真实频率，所以整局游戏能在 126 us 内跑完 —— 这也是
    "仿真时间与真实时间可以解耦"的一个实例（真实节拍来自 clk_gen 的分频链）。
"""

CLK = 20.0
T1 = 2000.0          # "1 Hz"节拍周期
T2 = 1000.0          # tick_2hz（500 ms 一个脉冲；本 tb 只把它接进端口，不再当闪烁）
T4 = 500.0           # tick_4hz（250 ms，= 2 Hz 方波的半周期）—— B1"2 Hz 闪烁"用它
GRID_PERIOD = 10.0

# ---- D2（第三关）时间轴后移量 ---------------------------------------------------
# ⚠️ 2026-10-09（第 12 工作阶段）：场景 2 现在**多了一关** —— 二关拼对（100000）
#    → 三关预览 → 三关对局（40 s）→ 三关拼对 → 胜利；原来是"二关拼对 = 胜利"。
#    为了让这三步有时间跑，把 **104000 之后的全部事件**（按键、判据窗口、SW7 拨动、
#    所有采样时刻）整体后移 D3_SHIFT ns。**尾段常量一律由它推导**，不再手改字面量：
#    ERR-034 的教训就是"按旧时间轴标定的常量在流程变长后失效，而那种错只有整机重跑才暴露"。
#    后移后每一局的"散落忙窗 / 判据窗"仍与该局的对局起点保持原来的相对关系
#    （它们一起平移），所以 ERR-024 的残留场景语义不变。
D3_SHIFT = 20000.0

DURATION = 192000.0 + D3_SHIFT

S_SELF, S_IDLE, S_PREV, S_PLAY, S_WIN, S_FAIL = 0, 1, 2, 3, 4, 5
T_PREVIEW, T_L1, T_L2 = 5, 30, 40          # 课程要求 B4 / B5 / B10
T_L3 = 40                                  # A2 第三关（题目没规定 → 自拟 40 s，= T_LEVEL3）

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
    (104000 + D3_SHIFT, RAW_START, "**胜利**后重开（D2 之后胜利发生在第三关，见 ⑪c）"),
    (128000 + D3_SHIFT, RAW_START, "第三场景：SW7 再拨上后开始（自检 2 s 已过）"),
    (142000 + D3_SHIFT, RAW_START, "第四场景：残留判负后重开"),
    (166000 + D3_SHIFT, RAW_START, "第五场景：SW7 再拨一次后开始（B11 的'游戏结束后重开'已测过，"
                          "这里专测**对局中**重开）"),
    (180000 + D3_SHIFT, RAW_START, "第五场景：**对局中**按开始 —— B11 要求可以随时开新一轮"),
]

# i_solved / i_all_lock / i_shuf_busy 的时间窗
# ⚠️ 第三/第四场景是 ERR-024 的回归激励：**故意让上一局的 i_solved / i_all_lock
#    残留到新一局对局开始之后**（上板现象：退出重进直接跳第二关 / 刚开局就判负），
#    而 i_shuf_busy 故意晚 2 个时钟才起来（引擎要等"散落请求"那一两拍），
#    这样就能精确复现"判决发生在散落之前"的窗口。
#    窗口到 154100 为止：之后的第五场景必须是"干干净净的新一局"（solved/all_lock 全 0），
#    否则对局中重开这条会被残留的胜利判据搅乱。
SOLVED_WINS = [(88000.0, 90000.0),                 # 一关拼对 → 第二关预览
               (100000.0, 102000.0),               # 二关拼对 → **第三关预览**（D2 新增的一关）
               (116000.0, 118000.0),               # ★ 三关拼对 → **胜利**（D2 新增）
               (142500.0 + D3_SHIFT, 154100.0 + D3_SHIFT)]
ALL_LOCK_WINS = [(116000.0 + D3_SHIFT, 118000.0 + D3_SHIFT),
                 (122000.0 + D3_SHIFT, 154100.0 + D3_SHIFT)]
# ⚠️ 2026-10-08 修正：本表原来只给**两个**对局建了散落忙窗，可 `game_fsm` 现在要求
#    "本局至少看到过一次散落"（ERR-024）；而真实引擎**每一局**都会散落，所以这里
#    给每一局各建一个"开局后不久"的忙窗（也顺便更贴近真实时序：玩家不可能在
#    散落还没跑完时就拼好）。第一版漏建的两局直接把 ⑨⑩⑪⑬⑰ 拖挂（r08 = 12/17）。
#    ⚠️ 2026-10-09（D2）：第三关那一局（对局起点 110020）也要有自己的忙窗 —— 见
#       下面 (110060, 111000)；"第三关拼对 → 胜利"必须在**看见了第三关的散落**之后
#       才允许，否则那个"胜利"是拿上一局的残留判据判出来的（正是 ERR-024 的形态）。
SHUF_BUSY_WINS = [(14060.0, 15000.0), (86060.0, 87000.0), (98060.0, 99000.0),
                  (110060.0, 111000.0),            # ★ 第三关对局开局散落（D2 新增）
                  (114060.0 + D3_SHIFT, 115000.0 + D3_SHIFT),
                  (138060.0 + D3_SHIFT, 140060.0 + D3_SHIFT),
                  (152060.0 + D3_SHIFT, 154060.0 + D3_SHIFT),
                  (176060.0 + D3_SHIFT, 177000.0 + D3_SHIFT)]
T_SW_OFF2 = 120000.0 + D3_SHIFT           # SW7 拨下去（⑭）
T_SW_ON2 = 122000.0 + D3_SHIFT             # SW7 再拨上去（自检 2 s -> 待机）
T_SW_OFF3 = 158000.0 + D3_SHIFT            # 第二次拨下去
T_SW_ON3 = 160000.0 + D3_SHIFT             # 第三次拨上去
T_PLAY3 = 138020.0 + D3_SHIFT              # 第三局对局开始（推算：见 §1.2 时间表）
# SW7 的拨动序列：(时刻, 电平)。第五场景需要**再清一次**，才能从干净的自检重新开局。
SW_SPANS = [(0.0, T_SW_OFF2, 1), (T_SW_OFF2, T_SW_ON2, 0), (T_SW_ON2, T_SW_OFF3, 1),
            (T_SW_OFF3, T_SW_ON3, 0), (T_SW_ON3, DURATION, 1)]

OBSERVE = ["i_clk", "i_sw", "i_press", "i_key", "i_tick_1hz", "i_tick_2hz", "i_tick_4hz",
           "i_solved", "i_all_lock", "i_shuf_busy",
           "o_state", "o_level", "o_lvl3", "o_time", "o_blink", "o_go",
           "o_sel", "o_conf", "o_move", "o_up", "o_down", "o_left", "o_right",
           "st", "cnt", "level", "lvl3", "req_go", "go_done", "blink_r"]


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
    b.input_bit("i_tick_4hz")
    b.input_bit("i_press")
    b.input_bus("i_key", 4)
    b.input_bit("i_solved")
    b.input_bit("i_all_lock")
    b.input_bit("i_shuf_busy")
    b.output_bus("o_state", 3)
    b.output_bit("o_level")
    b.output_bit("o_lvl3")
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
    for n, w in (("st", 3), ("cnt", 6), ("level", 1), ("lvl3", 1), ("req_go", 1),
                 ("go_done", 1), ("blink_r", 1)):
        if w == 1:
            b.output_bit(n)
        else:
            b.output_bus(n, w)
        _buried(b, n, w)

    b.clock("i_clk", CLK)
    b.segments("i_rst", [(100.0, 1), (DURATION - 100.0, 0)])
    b.segments("i_sw", _tl(DURATION, [(a, b_, v) for (a, b_, v) in SW_SPANS], 1))
    b.segments("i_tick_1hz", _tick(DURATION, T1))
    b.segments("i_tick_2hz", _tick(DURATION, T2))
    b.segments("i_tick_4hz", _tick(DURATION, T4))

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
    #    ⚠️ 2026-10-09（D2）：期望值不再写死"8 局"——**从前面的状态轨迹独立数出**
    #    "进入对局的次数"（每次进 S_PLAYING 必须且只许有一次散落请求）。加一关之后
    #    局数本来就变了，写死的数字只会变成下一个 ERR-034。
    go_r = _rises(vf, "o_go")
    play_entries = [t for i, (t, v) in enumerate(st_tr)
                    if v == S_PLAY and (i == 0 or st_tr[i - 1][1] != S_PLAY)]
    res.append((
        "⑥ ★ o_go 每局只上升一次，且次数 == 进入对局的次数（从状态轨迹独立数出）；"
        "ERR-006：散落握手必须有'完成'记忆，否则会无限重复散落、清掉选中/锁定，按键全部失效",
        len(go_r) == len(play_entries) and len(go_r) > 0,
        "o_go 上升沿时刻：%s（共 %d 次）| 进入对局 %d 次（时刻 %s）"
        % (", ".join("%.0f" % t for t in go_r), len(go_r), len(play_entries),
           ", ".join("%.0f" % t for t in play_entries)),
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

    # ⑪ 二关拼对 -> **进第三关**（A2"增加游戏关数"；D2 之前这里是"直接胜利"）
    cand3 = [t for (t, v) in st_tr if v == S_PREV and t > 100000.0]
    t_l3prev = cand3[0] if cand3 else None
    res.append((
        "⑪ 第二关对局中 i_solved=1 → 进入**第三关预览**（A2『增加游戏关数』）："
        "o_level=1 且 o_lvl3=1、o_time=5（预览仍是 5 秒）",
        t_l3prev is not None and _bit_at(vf, "o_level", t_l3prev + 100.0) == "1"
        and _bit_at(vf, "o_lvl3", t_l3prev + 100.0) == "1"
        and _bus_at(vf, "o_time", t_l3prev + 100.0) == T_PREVIEW,
        "三关预览时刻=%s（o_level=%s o_lvl3=%s o_time=%s）"
        % ("%.0f ns" % t_l3prev if t_l3prev else "无",
           _bit_at(vf, "o_level", (t_l3prev or 0) + 100.0),
           _bit_at(vf, "o_lvl3", (t_l3prev or 0) + 100.0),
           _bus_at(vf, "o_time", (t_l3prev or 0) + 100.0)),
    ))

    # ⑪b 三关对局限时 = 40 s（自拟 T_LEVEL3；题目只规定了 B5 的 30 s 与 B10 的 40 s）
    cand_l3play = [t for (t, v) in st_tr if v == S_PLAY and t > 105000.0]
    t_p3 = cand_l3play[0] if cand_l3play else None
    res.append((
        "⑪b 第三关对局 o_time 被加载为 %d（A2 第三关自拟 40 s = pkg.T_LEVEL3）" % T_L3,
        t_p3 is not None and _bus_at(vf, "o_time", t_p3 + 100.0) == T_L3
        and _bit_at(vf, "o_lvl3", t_p3 + 100.0) == "1",
        "三关对局时刻=%s，o_time=%s（期望 %d）、o_lvl3=%s"
        % ("%.0f ns" % t_p3 if t_p3 else "无",
           _bus_at(vf, "o_time", (t_p3 or 0) + 100.0), T_L3,
           _bit_at(vf, "o_lvl3", (t_p3 or 0) + 100.0)),
    ))

    # ⑪c 三关拼对 -> 胜利（"胜利图案"现在由第三关给出：第三关是最后一关）
    t_win = _first_state(vf, S_WIN)
    res.append((
        "⑪c 第三关对局中 i_solved=1 → **胜利**状态（A2：第三关是最后一关，"
        "这是胜利图案真正的出口；D2 之前出口在第二关）",
        t_win is not None and t_win > 110000.0,
        "进胜利状态时刻=%s（必须晚于第三关对局起点 110020 ns）"
        % ("%.0f ns" % t_win if t_win else "从未进入"),
    ))

    # ⑫ 胜利后按开始 -> 预览（且关卡号与第三关标志都回到第一关）
    t_prev3 = ([t for (t, v) in st_tr if v == S_PREV and t > t_win] if t_win else [])
    res.append((
        "⑫ 胜利后按【开始】再次进入预览，且 o_level=0、o_lvl3=0（B11：游戏结束后可开新一轮）",
        len(t_prev3) > 0 and _bit_at(vf, "o_level", t_prev3[0] + 100.0) == "0"
        and _bit_at(vf, "o_lvl3", t_prev3[0] + 100.0) == "0",
        "胜利后的预览时刻：%s；o_level=%s o_lvl3=%s"
        % (["%.0f" % t for t in t_prev3] or "无",
           _bit_at(vf, "o_level", (t_prev3[0] if t_prev3 else 0) + 100.0),
           _bit_at(vf, "o_lvl3", (t_prev3[0] if t_prev3 else 0) + 100.0)),
    ))

    # ⑬ 拼错判负：i_all_lock=1 且引擎空闲
    T13 = 116100.0 + D3_SHIFT
    res.append((
        "⑬ 对局中 i_all_lock=1 且 i_shuf_busy=0 → 判负（B9：全部锁定但位置形状不对）",
        _bus_at(vf, "o_state", T13) == S_FAIL,
        "i_all_lock 置位后的状态 = %s（期望 %d 失败）"
        % (_bus_at(vf, "o_state", T13), S_FAIL),
    ))

    # ⑭ SW7=0 立刻回自检并清空
    T14 = 120100.0 + D3_SHIFT
    res.append((
        "⑭ SW7=0 立刻回到自检并清零（B1：开关关掉时全部不显示）",
        _bus_at(vf, "o_state", T14) == S_SELF
        and _bit_at(vf, "o_level", T14) == "0"
        and _bit_at(vf, "o_lvl3", T14) == "0"
        and _bus_at(vf, "o_time", T14) == 0,
        "SW 拉低后 o_state=%s（期望 %d）、o_level=%s、o_lvl3=%s、o_time=%s"
        % (_bus_at(vf, "o_state", T14), S_SELF,
           _bit_at(vf, "o_level", T14), _bit_at(vf, "o_lvl3", T14),
           _bus_at(vf, "o_time", T14)),
    ))

    # ⑮ o_blink 是 2 Hz 方波（电平），不是单时钟脉冲
    n_t4 = int(DURATION // T4)
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
        "⑮ o_blink 是**真正的 2 Hz 方波**：在 4 Hz 节拍上翻转一次，高电平持续半个 2 Hz "
        "周期（= 250 ms = 4 Hz 节拍周期，本 tb 折算 %.0f ns），不是'单时钟脉冲当闪烁电平'"
        "（ERR-011 / ERR-038）" % T4,
        len(rises) >= 20 and hi_w and abs(med - T4) < 2 * CLK,
        "上升沿 %d 次（期望约 %d）；高电平宽度中位数=%.0f ns"
        % (len(rises), n_t4 // 2, med),
    ))

    # ================================================================
    # 第三/第四场景：ERR-024（新一局开头拿上一局的残留状态判决）
    # ================================================================
    # ⑯ 残留的 i_all_lock=1 不得在散落之前判负
    st_after_play = _bus_at(vf, "o_state", T_PLAY3 + 60.0)     # 对局开始后 3 拍
    fails3 = [t for (t, v) in st_tr if v == S_FAIL and t > 135000.0 + D3_SHIFT]
    t_fail3 = fails3[0] if fails3 else None
    T16_END = 140060.0 + D3_SHIFT
    res.append((
        "⑯ ★【ERR-024】新一局对局刚开始、散落还没起来时，上一局残留的 i_all_lock=1 "
        "**不得**判负：状态机必须在 S_PLAYING 里等散落（忙→闲）之后才判决",
        st_after_play == S_PLAY and t_fail3 is not None and t_fail3 > T16_END,
        "对局开始后 3 拍仍是 %s（期望 %d 对局）；本轮首次判负时刻=%s（必须晚于散落结束 %.0f ns）"
        % (st_after_play, S_PLAY, "-" if t_fail3 is None else "%.0f ns" % t_fail3, T16_END),
    ))

    # ⑰ 残留的 i_solved=1 不得在散落之前把关卡推进到第二关
    prevs4 = [t for (t, v) in st_tr if v == S_PREV and t > 150000.0 + D3_SHIFT]
    t_prev4 = prevs4[0] if prevs4 else None
    T17 = 152100.0 + D3_SHIFT                                  # 对局开始后 4 拍
    T17_END = 154060.0 + D3_SHIFT
    st_wait = _bus_at(vf, "o_state", T17)
    res.append((
        "⑰ ★【ERR-024】新一局对局刚开始时残留的 i_solved=1 **不得**立刻推进关卡："
        "必须先看到散落（忙→闲），之后才允许按 i_solved 进第二关预览（o_level=1）",
        st_wait == S_PLAY and t_prev4 is not None and t_prev4 > T17_END
        and _bit_at(vf, "o_level", t_prev4 + 100.0) == "1",
        "对局开始后 4 拍仍是 %s（期望 %d 对局）；进第二关预览时刻=%s"
        "（必须晚于散落结束 %.0f ns）、此刻 o_level=%s"
        % (st_wait, S_PLAY, "-" if t_prev4 is None else "%.0f ns" % t_prev4, T17_END,
           _bit_at(vf, "o_level", (t_prev4 or 0) + 100.0)),
    ))

    # ---------------------------------------------------------
    # ⑱ ★ B11：**对局中**按【开始】也要能重开一轮
    #    此前只覆盖了"超时判负后重开"（76000）与"胜利后重开"（104000），对局中这条
    #    分支（game_fsm 的 S_PLAYING 里判 K_START）一直没有断言 —— 收尾时补上。
    #    判定方式：按下去之后必须**回到预览**，并且**再走满 5 秒预览后重新散落**
    #    （o_go 再次上升），这才叫"完整重开一轮"而不是停在原地。
    # ---------------------------------------------------------
    prev_after = [t for (t, v) in st_tr if v == S_PREV and t > 179000.0 + D3_SHIFT]
    play_after = [t for (t, v) in st_tr if v == S_PLAY and t > 179000.0 + D3_SHIFT]
    go_after = [t for t in go_r if t > 179000.0 + D3_SHIFT]
    d_prev = (prev_after[0] - (180000.0 + D3_SHIFT)) if prev_after else -1
    d_go = (go_after[0] - prev_after[0]) if (prev_after and go_after) else -1
    res.append((
        "⑱ ★【B11】**对局中**按【开始】→ 立刻回到预览，并**完整重开一轮**"
        "（预览 5 秒后再次散落）；此前只测了'失败后重开''胜利后重开'",
        bool(prev_after) and 0 <= d_prev <= 2 * T1 and bool(play_after)
        and len(go_after) >= 1 and 0.9 * T_PREVIEW * T1 <= d_go <= 1.1 * T_PREVIEW * T1,
        "按下后进预览时刻=%s（比按键晚 %.0f ns，期望 0~%0.f）；此后再次散落时刻=%s"
        "（距进预览 %.0f ns，期望约 %d）"
        % ("%.0f" % prev_after[0] if prev_after else "无", d_prev, 2 * T1,
           "%.0f" % go_after[0] if go_after else "无", d_go, T_PREVIEW * T1),
    ))

    return res
