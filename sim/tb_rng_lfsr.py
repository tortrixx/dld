# -*- coding: utf-8 -*-
"""tb_rng_lfsr.py —— rng_lfsr 功能仿真激励与断言

【本模块的特殊性】
    ① **不接任何时钟节拍**：它接原始 `i_clk`，但只在 `i_step='1'` 的那一拍推进。
       —— 这一条本身就是"可复现的随机"的硬约束（自由振荡的随机源没法复现、
       没法仿真）。所以 tb 里 `i_step` 是**受控**的：一段连续 255 拍 + 一次单拍脉冲。
    ② 它是**时序**模块：综合后网表寄存器初值是 **X 不是 0**
       → **必须显式给复位**（本 tb 在 0~100 ns 拉高 i_rst）。
    ③ 全零是 LFSR 的**吸收态**：一旦落进去永远出不来，所以初值/复位值必须非零。

【判据的独立来源（不许自证）】
    · 初值：从 `rtl/puzzle_pkg.vhd`（唯一真值源）里**读** `SEED_DEFAULT`，
      而不是在 tb 里抄一个字面量；并断言它 ≠ 0。
    · 序列：tb 里**独立推演** x^8 + x^6 + x^5 + x^4 + 1（抽头 bit7/5/4/3）的
      Fibonacci LFSR，逐拍与实测比对 255 拍。RTL 里的抽头表达式**没有被抄进 tb** ——
      断言 ⑧ 反过来从波形里的中间节点 `fb` 实测出抽头关系，作为交叉证据。
    · 周期 255 / 255 个状态两两不同 / 每 bit 恰 128 个 1：最大长度序列的数学性质，
      由 tb 独立计算后与实测序列比对。

【中间信号】（课件 p59 / docs/03 §3.1：波形里必须有中间信号）
    综合后**功能仿真**网表里的内部节点（用探针跑确认过，非猜测）：
        reg  sr[0..7]   —— 8 位状态寄存器（o_val 就是它的组合拷贝）
        comb fb~0       —— 反馈异或树**第一级**的中间项（实测 == sr(7) ^ sr(5)）
    注：VHDL 里的进程变量 `fb` 在 post-map 数据库里有名字，但功能仿真网表里
    只剩下组合节点 `fb~0`（声明 `fb` 会被报 `Can't find node "fb"`）。
    内部节点在网表里是 **Buried**，整条/逐位声明为 BURIED 才能被仿真器认出来。

【时间线】（单位 ns，CLK = 20，上升沿在 10 + 20k）
    0    ~ 100     i_rst=1（复位）→ sr = SEED_DEFAULT
    115            采样 seq[0]（复位初值）
    120  ~ 5215    i_step=1 连续 255 拍 → 采样 seq[1..255]（seq[255] 应回到初值）
    5240/5260/5280 空闲（i_step=0）连续 3 个时钟沿 → 状态必须纹丝不动
    5400 ~ 5415    单拍 i_step=1（恰好覆盖上升沿 5410）→ 恰好前进 1 步
    5440/5460      脉冲之后再空闲 2 个沿 → 状态保持（证明不是"每拍都推进"）
"""

import pathlib
import re

CLK = 20.0
DURATION = 5600.0
GRID_PERIOD = 10.0

# ---- 从 puzzle_pkg 读初值（唯一真值源），不在 tb 里抄字面量 ----
def _seed_default():
    p = pathlib.Path(__file__).resolve().parent.parent / "rtl" / "puzzle_pkg.vhd"
    txt = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'constant\s+SEED_DEFAULT\s*:\s*std_logic_vector\(7\s+downto\s+0\)\s*'
                  r':=\s*x"([0-9A-Fa-f]{2})"', txt)
    if not m:
        raise RuntimeError("puzzle_pkg 里没找到 SEED_DEFAULT（x\"..\" 形式）")
    return int(m.group(1), 16)


SEED = _seed_default()

# ---- 独立推演：Fibonacci LFSR，抽头 bit7/5/4/3 ----
TAPS = (7, 5, 4, 3)


def ref_next(s):
    fb = 0
    for b in TAPS:
        fb ^= (s >> b) & 1
    return ((s << 1) & 0xFF) | fb


def ref_seq(seed, n):
    out = [seed]
    s = seed
    for _ in range(n):
        s = ref_next(s)
        out.append(s)
    return out


REF = ref_seq(SEED, 255)

# ---- 关键时刻 ----
T_INIT = 115.0                  # 复位后、首次步进前的采样点
STEP_EDGE0 = 130.0              # 第 1 次步进的上升沿
RUN_END = 5215.0                # 255 拍推进结束（i_step 拉低，早于下一个上升沿 5230）
T_HOLD = [5240.0, 5260.0, 5280.0]
T_PULSE = 5420.0                # 单拍脉冲（覆盖上升沿 5410）之后
T_AFTER = [5440.0, 5460.0]


def sample_time(k):
    """第 k 拍状态的采样时刻（k=0 复位初值，k>=1 第 k 次步进之后）。"""
    if k == 0:
        return T_INIT
    return STEP_EDGE0 + CLK * (k - 1) + 10.0


RST_SPANS = [(0.0, 100.0, 1), (100.0, DURATION, 0)]
STEP_SPANS = [(0.0, 120.0, 0), (120.0, RUN_END, 1), (RUN_END, 5400.0, 0),
              (5400.0, 5415.0, 1), (5415.0, DURATION, 0)]

# ---- 观测点 ----
# 综合后网表里内部节点是 Buried（声明成 OUTPUT 会报
# "Wrong node type ... Design node is of type Buried"）。
# ⚠️ 节点名要在**功能仿真网表**里真实存在：VHDL 里的进程变量 `fb` 在 post-map
#    数据库里有名字（`fb`），但 fnsim 网表里只剩下它的组合节点 `fb~0`
#    —— 实测：声明 `fb` 会被报 `Can't find node "fb" for functional simulation`。
OBSERVE = ["i_clk", "i_rst", "i_step", "o_val", "sr", "fb~0"]
BURIED = {"sr": 8, "fb~0": 1}


def _buried(b, name, width):
    for n in [name] + ["%s[%d]" % (name, i) for i in range(width)]:
        sig = b.vf.signals.get(n)
        if sig is not None:
            sig.direction = "BURIED"


def _segs(spans):
    return [(b - a, lv) for (a, b, lv) in spans]


def build(b):
    b.input_bit("i_clk")
    b.input_bit("i_rst")
    b.input_bit("i_step")
    b.output_bus("o_val", 8)
    b.output_bus("sr", 8)
    b.output_bit("fb~0")
    _buried(b, "sr", 8)
    _buried(b, "fb~0", 1)

    b.clock("i_clk", CLK)
    # ⚠️ 时序模块必须显式复位：综合后网表寄存器初值是 X
    b.segments("i_rst", _segs(RST_SPANS))
    b.segments("i_step", _segs(STEP_SPANS))


def _hex(v):
    return "X" if v is None else "0x%02X" % v


def check(vf):
    res = []

    meas = [vf.bus_value_at("o_val", sample_time(k)) for k in range(256)]

    # ---- ① 复位初值 == SEED_DEFAULT 且非零 ----
    res.append((
        "① 复位后 o_val == puzzle_pkg 的 SEED_DEFAULT(%s) 且 ≠ 0（未落在全零吸收态）"
        % _hex(SEED),
        meas[0] == SEED and SEED != 0,
        "实测 %s；pkg 的 SEED_DEFAULT = %s；是否为零 = %s"
        % (_hex(meas[0]), _hex(SEED), meas[0] == 0),
    ))

    # ---- ② 与独立推演序列逐拍比对 255 拍 ----
    mism = [(k, meas[k], REF[k]) for k in range(256) if meas[k] != REF[k]]
    res.append((
        "② 实测 255 拍状态序列与【tb 独立推演】的 x^8+x^6+x^5+x^4+1（抽头 bit7/5/4/3）"
        "逐拍完全一致",
        not mism,
        "逐拍比对 256 个状态：全部一致" if not mism else
        "不一致 %d 处，前 5 处：%s" % (len(mism), "；".join(
            "第%d拍 实测%s 期望%s" % (k, _hex(m), _hex(r)) for (k, m, r) in mism[:5])),
    ))

    # ---- ③ 周期恰为 255 ----
    back = [k for k in range(1, 255) if meas[k] == SEED]
    res.append((
        "③ 周期恰为 255：第 255 拍回到初值，且第 1~254 拍都没有回到初值",
        meas[255] == SEED and not back,
        "第 255 拍 = %s（期望 %s）；1~254 拍中提前回到初值的次数 = %d"
        % (_hex(meas[255]), _hex(SEED), len(back)),
    ))

    # ---- ④ 最大长度序列的三条数学性质 ----
    vals = meas[0:255]
    zeros = [k for k in range(256) if meas[k] == 0]
    ones = [sum((v >> b) & 1 for v in vals if v is not None) for b in range(8)]
    res.append((
        "④ 最大长度序列性质：255 个状态两两不同、全程不出现 0、每个 bit 恰 128 个 1",
        len(set(vals)) == 255 and not zeros and all(c == 128 for c in ones),
        "不同状态数 = %d/255；出现 0 的拍号 = %s；各 bit 的 1 计数(bit7→bit0) = %s"
        % (len(set(vals)), zeros or "无", ones),
    ))

    # ---- ⑤ i_step='0' → 状态纹丝不动 ----
    hold = [vf.bus_value_at("o_val", t) for t in T_HOLD]
    after = [vf.bus_value_at("o_val", t) for t in T_AFTER]
    ok = (len(set(hold)) == 1 and hold[0] == REF[255]
          and len(set(after)) == 1 and after[0] == REF[1])
    res.append((
        "⑤ i_step='0' 时状态**保持**（255 拍跑完后 3 个时钟沿不动；单拍脉冲后再 2 个沿不动）",
        ok,
        "跑完后 3 点 = %s（应保持 %s）；脉冲后 2 点 = %s（应保持 %s）"
        % ([_hex(x) for x in hold], _hex(REF[255]),
           [_hex(x) for x in after], _hex(REF[1])),
    ))

    # ---- ⑥ 单拍 i_step=1 恰好推进一次 ----
    v = vf.bus_value_at("o_val", T_PULSE)
    res.append((
        "⑥ 单拍 i_step='1'（恰好覆盖 1 个上升沿）→ 恰好推进 1 步：%s → %s"
        % (_hex(REF[255]), _hex(REF[1])),
        v == REF[1] and REF[1] != REF[255],
        "实测 %s，期望 next(%s) = %s（若没推进会是 %s）"
        % (_hex(v), _hex(REF[255]), _hex(REF[1]), _hex(REF[255])),
    ))

    # ---- ⑦ 中间信号 sr（状态寄存器）与 o_val 逐拍相同 ----
    sr = [vf.bus_value_at("sr", sample_time(k)) for k in range(256)]
    bad = [(k, sr[k], meas[k]) for k in range(256) if sr[k] != meas[k]]
    res.append((
        "⑦ 中间信号 sr（8 位状态寄存器）与端口 o_val 逐拍相同（o_val 是它的组合拷贝）",
        not bad,
        "不一致 %d 处" % len(bad) if bad else "256 拍全部一致（sr == o_val）",
    ))

    # ---- ⑧ ⭐ 从波形里的中间节点 fb~0 实测出抽头关系（不是抄 RTL 的表达式）----
    #    实测（穷举 8 位抽头的全部 2^8 种组合 + ±2 拍移位，唯一命中）：
    #        fb~0 == sr(7) ^ sr(5)
    #    它是反馈异或树 **第一级** 的中间项；后面几级被综合折进了 LUT 方程，
    #    网表里没有单独节点。所以这条断言查的是"抽头链的前两级"，
    #    完整抽头集合 {7,5,4,3} 由断言 ② / ③ 从**序列**独立验证。
    samples = [sample_time(k) for k in range(256)]
    bad = []
    fb_vals = []
    for t in samples:
        s = vf.bus_value_at("sr", t)
        f = vf.value_at("fb~0", t)
        fb_vals.append(f)
        if s is None or f is None:
            bad.append((t, s, f))
            continue
        want = str(((s >> 7) & 1) ^ ((s >> 5) & 1))
        if f != want:
            bad.append((t, _hex(s), "fb~0=%s 而 sr(7)^sr(5)=%s" % (f, want)))
    res.append((
        "⑧ ⭐ 中间信号 fb~0 在全部 256 个采样点上都 == sr(7) ^ sr(5)"
        "（反馈异或树第一级；对应关系由波形穷举抽头组合实测得到，不是照抄 RTL 表达式）",
        not bad and len(set(fb_vals)) == 2,
        ("不一致 %d 处：%s" % (len(bad), bad[:4])) if bad else
        "256 点全部满足；fb~0 出现过的电平 = %s（两种，说明反馈位真的在变）"
        % sorted(set(fb_vals)),
    ))

    # ---- ⑨ 复位后输出全程为确定值（无 X/Z）----
    undef = [k for k in range(256) if meas[k] is None]
    res.append((
        "⑨ 复位后 256 个采样点 o_val 全部为确定值（无 X/Z）—— 复位真的把状态拉出来了",
        not undef,
        "含 X 的采样点 = %s" % (undef or "无"),
    ))

    return res
