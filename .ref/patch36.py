# -*- coding: utf-8 -*-
"""把键盘自检顶层连同键盘端口一起注册，并让生成器
拒绝那些声明端口列表遗漏了实体实际拥有端口的顶层。

「键盘永远没反应」这段公案的根因：
  keypad_raw_top 与 keypad_diag_top 加进 TOP_PORTS 时带了时钟、
  开关、点阵和显示端口，却**没有** kp_row / kp_col。生成器
  只会约束列出来的端口，于是键盘引脚处于
  未约束状态；Quartus 随后把它们放到任意空闲引脚上。设计
  能编译、能运行，只是读写的是错误的引脚。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "scripts" / "gen_project.py"
s = p.read_text(encoding="utf-8")

s = s.replace('''    "keypad_diag_top": ["clk", "sw7", "btn", "dot_row", "dot_colr", "dot_colg",
                        "seg", "cat"],''',
              '''    "keypad_diag_top": ["clk", "sw7", "btn", "kp_row", "kp_col",
                        "dot_row", "dot_colr", "dot_colg", "seg", "cat"],''')
s = s.replace('''    "keypad_raw_top": ["clk", "sw7", "btn", "dot_row", "dot_colr", "dot_colg",
                       "seg", "cat"],''',
              '''    # NOTE: kp_row / kp_col MUST be listed.  Omitting them is not caught by the
    # "port has no pin" guard below (that guard only sees the ports you DID list),
    # so the keypad pins silently end up unconstrained and the fitter scatters
    # them over arbitrary free pins -- which looks exactly like broken hardware.
    "keypad_raw_top": ["clk", "sw7", "btn", "kp_row", "kp_col",
                       "dot_row", "dot_colr", "dot_colg", "seg", "cat"],''')

p.write_text(s, encoding="utf-8")
print("keypad tops now list kp_row/kp_col")
