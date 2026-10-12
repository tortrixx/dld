#!/usr/bin/env node
/**
 * gen-architecture-drawio.mjs —— 生成可编辑的 draw.io 架构图源文件
 *
 * 为什么要有生成器而不是手画一个 .drawio 入库：
 *   · 手画的图会随 RTL 漂移，而且"图上写的模块名"没人能核对；
 *   · 图里的每个方框与每条连线都来自下面这份数据结构，改 RTL 之后改这里、
 *     重跑一次脚本即可 —— 与 `quartus/puzzle.qsf` 由 `gen_project.py` 生成同一个道理。
 *
 * 与网页里那张带图的区别：
 *   · 网页带图为了可读性**只画相邻层之间的主干**，跨层连线（clk_gen 广播 tick、
 *     game_fsm 直接命令 puzzle_ctrl 等）刻意不画，只列进对照表；
 *   · 这份 draw.io 图**把跨层连线也画全**，因为它可以被缩放、拖拽、折叠 ——
 *     正好用来回答"每个模块之间的数据传输通道到底有哪些"。
 *
 * 输出：docs/图/dld-架构.drawio（纯文本 XML，可直接在 app.diagrams.net / VS Code 插件里改）
 *
 * 用法：node site/scripts/gen-architecture-drawio.mjs
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '..', '..');
const outFile = join(repoRoot, 'docs', '图', 'dld-架构.drawio');

/* ------------------------------------------------------------------ *
 * 画布与主题
 * ------------------------------------------------------------------ */

const W = 1600;
const H = 1180;

const C = {
  ink: '#131311',
  muted: '#6b7280',
  border: '#9ca3af',
  acc: '#c8370a',
  tick: '#b45309',
  cmd: '#1d4ed8',
  fb: '#b91c1c',
  fill: '#f6f7f9',
  fillStore: '#f3f4f6',
  fillCore: '#fdeee8',
};

const bandLabelStyle = `text;html=1;align=left;verticalAlign=middle;fontSize=11;fontColor=${C.muted};spacing=2;fontStyle=1`;

function bandLabel(id, text, x, y) {
  return cell(id, text, bandLabelStyle, x, y, 320, 20, { vertex: true });
}

/** 一个模块方框（draw.io 的 vertex）。 */
function box(id, value, x, y, w, h, tone = 'io') {
  const fill = tone === 'core' ? C.fillCore : tone === 'store' ? C.fillStore : C.fill;
  const stroke = tone === 'core' ? C.acc : C.border;
  const style = [
    'rounded=0',
    'whiteSpace=wrap',
    'html=1',
    `fillColor=${fill}`,
    `strokeColor=${stroke}`,
    'strokeWidth=1',
    'align=left',
    'verticalAlign=top',
    'spacingLeft=8',
    'spacingTop=6',
    'fontSize=12',
    'fontFamily=JetBrains Mono',
    `fontColor=${C.ink}`,
  ].join(';');
  return cell(id, value, style, x, y, w, h, { vertex: true });
}

/** 一条带箭头的正交连线（draw.io 自己布线）。 */
function edge(id, source, target, label, kind = 'data') {
  const color = kind === 'tick' ? C.tick : kind === 'cmd' ? C.cmd : kind === 'fb' ? C.fb : C.muted;
  const style = [
    'edgeStyle=orthogonalEdgeStyle',
    'rounded=1',
    'html=1',
    'endArrow=block',
    'endFill=1',
    `strokeColor=${color}`,
    `fontColor=${color}`,
    'fontSize=10',
    'fontFamily=JetBrains Mono',
    kind === 'fb' ? 'dashed=1;dashPattern=6 4' : '',
    kind === 'tick' ? 'dashed=1;dashPattern=2 4' : '',
    'labelBackgroundColor=#ffffff',
    'exitX=0.5;exitY=1;exitDx=0;exitDy=0',
    'entryX=0.5;entryY=0;entryDx=0;entryDy=0',
  ]
    .filter(Boolean)
    .join(';');
  return cell(id, label ?? '', style, 0, 0, 0, 0, { edge: true, source, target });
}

/** 图例条目（装饰性，直接放文字）。 */
function legend(id, text, x, y, color) {
  return cell(
    id,
    text,
    `text;html=1;align=left;verticalAlign=middle;fontSize=11;fontColor=${color};fontFamily=JetBrains Mono`,
    x,
    y,
    420,
    18,
    { vertex: true },
  );
}

const cells = [];
const seenIds = new Set();
let seq = 0;
function cell(id, value, style, x, y, w, h, extra = {}) {
  // 重复 id 会让 draw.io 静默丢元素：宁可在这里就报错
  if (seenIds.has(id)) throw new Error(`drawio 元素 id 重复：${id}`);
  seenIds.add(id);
  const attrs = [
    `id="${id}"`,
    `value="${escapeXml(value)}"`,
    `style="${style}"`,
    extra.vertex ? 'vertex="1"' : '',
    extra.edge ? 'edge="1"' : '',
    'parent="1"',
  ]
    .filter(Boolean)
    .join(' ');
  const geom = extra.edge
    ? '        <mxGeometry relative="1" as="geometry" />\n'
    : `        <mxGeometry x="${x}" y="${y}" width="${w}" height="${h}" as="geometry" />\n`;
    const body = extra.edge
    ? `      <mxCell ${attrs}${extra.source ? ` source="${extra.source}" target="${extra.target}"` : ''}>\n${geom}      </mxCell>\n`
    : `      <mxCell ${attrs}>\n${geom}      </mxCell>\n`;
  seq += 1;
  cells.push(body);
  return id;
}

function escapeXml(s) {
  return (
    String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      // ⚠️ 换行必须转成字符引用：XML 1.0 §3.3.3 规定属性值里的 #xA 在解析时被
      //    替换成空格 ⇒ draw.io 打开时多行标签会塌成一行（中文串没有空格可折行）。
      .replace(/\r\n|\r|\n/g, '&#10;')
  );
}

/* ------------------------------------------------------------------ *
 * 版面：六条横带（与网页带图同序，方便对照）
 * ------------------------------------------------------------------ */

const PAD = 40;
const FULL = W - PAD * 2; // 1520

function row(count, y, h, gap = 20) {
  const w = (FULL - gap * (count - 1)) / count;
  return Array.from({ length: count }, (_, i) => ({ x: PAD + i * (w + gap), y, w, h }));
}

const BANDS = [
  { y: 40, h: 52, label: '板级输入 / Board I/O', count: 4 },
  { y: 132, h: 58, label: '时钟与输入 / Clock & Input', count: 2 },
  { y: 230, h: 58, label: '时间与决策 / Time & Decisions', count: 1 },
  { y: 328, h: 58, label: '常量与随机 / Constants & RNG', count: 3 },
  { y: 426, h: 72, label: '空间引擎与输出驱动 / Engine & Drivers', count: 5 },
  { y: 538, h: 52, label: '板级输出 / Board Out', count: 3 },
];

const R = BANDS.map((b) => row(b.count, b.y, b.h));

BANDS.forEach((b, i) => {
  bandLabel(`band${i}`, b.label, PAD, b.y - 18);
});

// ---- 方框 ----
const N = {};

const inputs = [
  ['clk', 'clk 50 MHz\nPIN_18 · 20 ns'],
  ['sw7', 'sw7 系统开关\nPIN_125 · i_en'],
  ['btn', 'btn 复位键\nPIN_61 · 高有效'],
  ['kp', '4×4 矩阵键盘\nkp_row[3:0] · PIN_111..114'],
];
inputs.forEach(([k, v], i) => {
  N[k] = box(`in_${k}`, v, R[0][i].x, R[0][i].y, R[0][i].w, R[0][i].h);
});

N.clk_gen = box(
  'clk_gen',
  'clk_gen\n级联分频链 + 上电/按键复位\n7 路 tick：1k / 200 / 100 / 4 / 1 / 2 / 40 Hz',
  R[1][0].x,
  R[1][0].y,
  R[1][0].w,
  R[1][0].h,
  'core',
);
N.keypad = box('keypad_scan', 'keypad_scan\n四相扫描 + 消抖（4 轮 = 40 ms）\no_key / o_press / o_release', R[1][1].x, R[1][1].y, R[1][1].w, R[1][1].h);

N.fsm = box(
  'game_fsm',
  'game_fsm　时间与决策\n3 位状态：SELF_TEST / IDLE / PREVIEW / PLAYING / WIN / FAIL\n倒计时 5 s 预览 · 30/40/60 s 限时 · 关卡 1/2/3 · 键号译码 · 4 位音效码',
  R[2][0].x,
  R[2][0].y,
  R[2][0].w,
  R[2][0].h,
  'core',
);

const stores = [
  ['piece_rom', 'piece_rom\n零片形状库（常量折叠 ⇒ 0 LE）\ni_sh0..3 / i_h0..3 / i_w0..3'],
  ['pattern_rom', 'pattern_rom\n图案库 4 幅（level=0 时忽略下标）\ni_target[63:0]'],
  ['rng_lfsr', 'rng_lfsr\nx⁸+x⁶+x⁵+x⁴+1 · 周期 255\ni_step → o_val[7:0]'],
];
stores.forEach(([k, v], i) => {
  N[k] = box(k, v, R[3][i].x, R[3][i].y, R[3][i].w, R[3][i].h, 'store');
});

const drivers = [
  ['puzzle_ctrl', 'puzzle_ctrl　空间引擎\n落位 · 移动 · 旋转 · 边界 · 精确重叠 · 锁定 · 着色\no_rowr / o_rowg（64 位列平面）· o_solved / o_all_lock / o_busy'],
  ['disp_format', 'disp_format\n状态 → 数码管内容（纯组合）\no_data[31:0] / o_blank[7:0]'],
  ['seg_scan', 'seg_scan\n8 位动态扫描 + 7 段译码\n每位 125 Hz'],
  ['dot_matrix_scan', 'dot_matrix_scan\n8 行扫描译码 + 输出寄存\n125 Hz 帧 · 占空比 1/8'],
  ['buzzer_ctrl', 'buzzer_ctrl\n÷256 预分频 · 8 音高 · 16 步乐句\ni_sel[3:0] → o_buzz'],
];
drivers.forEach(([k, v], i) => {
  N[k] = box(k, v, R[4][i].x, R[4][i].y, R[4][i].w, R[4][i].h, k === 'puzzle_ctrl' ? 'core' : 'io');
});

const outputs = [
  ['out_dot', '点阵行 / 红列 / 绿列\ndot_row[7:0] · dot_colr[7:0] · dot_colg[7:0]（同亮 = 黄）'],
  ['out_seg', '数码管段选 / 位选\nseg[7:0] · cat[7:0]'],
  ['out_buzz', '蜂鸣器方波\nbuzz · PIN_60'],
];
outputs.forEach(([k, v], i) => {
  N[k] = box(k, v, R[5][i].x, R[5][i].y, R[5][i].w, R[5][i].h);
});

// ---- 连线（把跨层连线也画全：这正是这份图存在的理由） ----
edge('e_clk', N.clk, N.clk_gen, 'clk');
edge('e_btn', N.btn, N.clk_gen, 'i_btn');
edge('e_sw7', N.sw7, N.fsm, 'i_sw / i_en');
edge('e_kp', N.kp, N.keypad, 'kp_row[3:0]');

edge('e_t1k_fsm', N.clk_gen, N.fsm, 't_1hz / t_4hz', 'tick');
edge('e_t200_kp', N.clk_gen, N.keypad, 't_200', 'tick');
edge('e_t1k_puzzle', N.clk_gen, N.puzzle_ctrl, 't_1k（行渲染节拍）', 'tick');
edge('e_t1k_dot', N.clk_gen, N.dot_matrix_scan, 't_1k（mrow 行推进）', 'tick');
edge('e_t1k_seg', N.clk_gen, N.seg_scan, 't_1k（位选）', 'tick');
edge('e_t4hz_buzz', N.clk_gen, N.buzzer_ctrl, 't_4hz（换步）', 'tick');

edge('e_key_fsm', N.keypad, N.fsm, 'o_key[3:0] / o_press / o_release');
edge('e_lvl', N.fsm, N.piece_rom, 'o_level / o_lvl3', 'cmd');
edge('e_cmd', N.fsm, N.puzzle_ctrl, '命令脉冲 + o_go（散落握手）', 'cmd');
edge('e_fb', N.puzzle_ctrl, N.fsm, 'o_solved / o_all_lock / o_busy（判决反馈）', 'fb');
edge('e_shp', N.piece_rom, N.puzzle_ctrl, 'i_sh0..3 / i_h0..3 / i_w0..3');
edge('e_tgt', N.pattern_rom, N.puzzle_ctrl, 'i_target[63:0]');
edge('e_rng_req', N.puzzle_ctrl, N.rng_lfsr, 'rnd_step', 'cmd');
edge('e_rng_val', N.rng_lfsr, N.puzzle_ctrl, 'rnd_val[7:0]');
edge('e_frame', N.puzzle_ctrl, N.dot_matrix_scan, 'o_rowr / o_rowg → mat_r / mat_g');
edge('e_state', N.fsm, N.disp_format, 'o_state / o_time / o_blink / o_level', 'cmd');
edge('e_sound', N.fsm, N.buzzer_ctrl, 'o_sound[3:0]', 'cmd');
edge('e_data', N.disp_format, N.seg_scan, 'o_data / o_blank');
edge('e_pin_dot', N.dot_matrix_scan, N.out_dot, 'dot_row / dot_colr / dot_colg');
edge('e_pin_seg', N.seg_scan, N.out_seg, 'seg / cat');
edge('e_pin_buzz', N.buzzer_ctrl, N.out_buzz, 'buzz');

// ---- 图例 ----
const LEG_Y = 626;
legend('lg_title', '图例（连线颜色 = 通路的性质）', PAD, LEG_Y, C.ink);
legend('lg_tick', '橙色虚线：时钟/节拍广播（t_1k / t_200 / t_4hz / t_1hz）', PAD, LEG_Y + 20, C.tick);
legend('lg_cmd', '蓝色实线：命令脉冲与握手（o_go / rnd_step / o_sound / o_level）', PAD, LEG_Y + 40, C.cmd);
legend('lg_fb', '红色虚线：引擎 → 状态机的反向反馈（o_solved / o_all_lock / o_busy）', PAD, LEG_Y + 60, C.fb);
legend('lg_data', '灰色实线：数据通路（键号 / 形状 / 目标图案 / 位平面 / 数码管数据）', PAD, LEG_Y + 80, C.muted);
legend(
  'lg_note',
  '注：方框是 rtl/ 里真实的 entity；信号名取自 rtl/puzzle_top.vhd 的端口关联（:251 声明 / :419 实例化区）。',
  PAD,
  LEG_Y + 108,
  C.muted,
);
legend(
  'lg_gen',
  '本文件由 site/scripts/gen-architecture-drawio.mjs 生成 —— 改 RTL 后改脚本、重跑一次即可，别手改。',
  PAD,
  LEG_Y + 128,
  C.muted,
);

/* ------------------------------------------------------------------ *
 * 输出
 * ------------------------------------------------------------------ */

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" type="device" version="24.0.0">
  <diagram id="dld-architecture" name="puzzle_top 架构与数据通路">
    <mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="${W}" pageHeight="${H}" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
${cells.join('')}      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
`;

mkdirSync(dirname(outFile), { recursive: true });
writeFileSync(outFile, xml, 'utf8');
const kb = (Buffer.byteLength(xml, 'utf8') / 1024).toFixed(1);
console.log(`  drawio  ${outFile.replace(repoRoot + '\\', '').replace(repoRoot + '/', '')}  (${kb} KB, ${seq} 个元素)`);
