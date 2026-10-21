# 🎓 老师答辩抽查冲刺速查宝典

> **专为现场答辩设计**：老师在看完实际硬件操作演示后，通常会**随机挑选一个模块或一个技术难点**进行深入提问。<br>
> 查阅本页可实现**“3秒定位模块、先讲通俗大白话、再报硬核架构、最后摆出实测数据”**的满分应答。

---

## 🧭 现场答辩三步应答心法

遇到老师提问任何模块，切忌长篇大论背诵代码，牢记**“结论先行 → 微架构破局 → 数据收尾”**：
1. **第一句（大白话定性）**：“老师，这个模块的核心职责是【一句话通俗功能】，为了解决【具体硬件痛点】；”
2. **第二句（微架构硬核）**：“在硬件上我们采用了【核心算法/电路微架构】，坚决避免了【常见初学者陷阱】；”
3. **第三句（实测数据收尾）**：“在板卡实测中，该设计【给出具体的 LE / Fmax / 误差 / 刷新率数据】，100% 达到了设计指标。”

---

## 📌 随机抽查模块一：时钟与分频 (`clk_gen`)

<div class="defense-box">
  <div class="defense-title">⚡ 抽查模块 1：时钟与复位管理 (clk_gen)</div>

  <div class="defense-q">Q1：为什么全系统只用一个 50 MHz 主时钟？为什么不把分频后的 1 Hz 慢时钟直接接给状态机作为 clk？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    老师，这是数字系统设计中至关重要的<strong>“同步单时钟域”</strong>原则。<br>
    如果在代码里把计数器分频出来的信号直接作为下游触发器的时钟（门控时钟或分频时钟），该信号在布线网络中会产生严重的<strong>时钟偏斜（Clock Skew）和组合毛刺</strong>，破坏触发器的建立与保持时间，极易发生亚稳态。<br>
    我们的做法是全工程所有寄存器<strong>唯一挂载在 50 MHz 晶振上升沿</strong>，分频模块仅输出宽度严格为 1 个时钟周期（20 ns）的<strong>同步使能脉冲（Tick）</strong>。下游模块采用 <code>if rising_edge(clk) then if tick = '1' then</code> 采样，全时钟树零毛刺，TimeQuest 静态时序分析的 Fmax 稳定收敛到 54.27 MHz。
  </div>

  <div class="defense-q">Q2：你们是怎么做到只用极少量资源分出 7 路脉冲的？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    我们采用了<strong>级联分频（Cascaded Divider Chain）</strong>与资源合并：<br>
    只有第 1 级面对 50 MHz（数 50000 出 1 kHz）；随后的 200 Hz 只需要 3 位计数器数到 5；100 Hz 仅用 1 位触发器翻转；4 Hz 由 5 位计数器数到 25，而 2 Hz 和 1 Hz 直接复用 4 Hz 节拍的 2 位状态。<br>
    整条分频链的触发器开销从最初独立的 18 个骤降到仅 7 个，为仅有 1,270 LE 的 MAX II 芯片节省了宝贵资源。
  </div>

  <div class="defense-q">Q3：复位按键 BTN0 是怎么消抖的？上电会发生未定义状态吗？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    我们设计了双保险：<br>
    1. <strong>硬件上电复位 (POR)</strong>：内部计数器在上电初期强制将 <code>rst</code> 拉高 8 ms，确保所有触发器安全完成初始化；<br>
    2. <strong>5 位饱和计数器滤波</strong>：外部复位键在 1 kHz 节拍下连续检测到 20 次按下（20 ms）才判定有效复位，有效滤除机械抖动；松开立即释放，消除时序关键路径。
  </div>
</div>

---

## 📌 随机抽查模块二：矩阵键盘与消抖 (`keypad_scan`)

<div class="defense-box">
  <div class="defense-title">⌨️ 抽查模块 2：4×4 矩阵键盘扫描 (keypad_scan)</div>

  <div class="defense-q">Q1：你们的键盘消抖时间是多少？为什么消抖太长或太短都不行？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    老师，我们的消抖时间是严格的 <strong>40 ms（连续 4 轮一致判稳）</strong>。<br>
    机械按键在按下和弹起瞬间有 5～15 ms 的弹跳抖动。如果消抖时间太短（比如 < 10 ms），就会把抖动误认为连续按键，零片会飞出屏幕；<br>
    早期版本我们曾误将消抖设为 160 ms（ERR-031），结果导致玩家快速连击时严重“吞键”。最终我们收紧为 40 ms（由 200 Hz 驱动，每轮 10 ms，数 4 轮），既完全覆盖了 15 ms 机械抖动上限，又远低于人手连击极限（100 ms），手感极其灵敏跟手。
  </div>

  <div class="defense-q">Q2：玩家按住按键一直不放手，零片会持续移动吗？你们是怎么防止连发的？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    绝对不会连发。我们设计了<strong>“单拍边缘脉冲提取”</strong>机制：<br>
    当消抖判稳后，输出的 <code>o_press</code> 信号只维持<strong>严格的一个 50 MHz 主时钟周期（20 ns）</strong>的高电平，主状态机只在该瞬间响应一次动作。<br>
    只要按键没有松开，内部标志 <code>accepted</code> 会持续锁死；只有当按键完全释放后才允许下一次触发。长按只会触发恰好一次移动。
  </div>
</div>

---

## 📌 随机抽查模块三：游戏规则状态机 (`game_fsm`)

<div class="defense-box">
  <div class="defense-title">🕹️ 抽查模块 3：游戏主控状态机 (game_fsm)</div>

  <div class="defense-q">Q1：请介绍状态机的 6 个状态及转移条件？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    我们严格按照 ASM 规范划分为 6 个核心状态：<br>
    1. <code>S_SELF_TEST</code>（自检）：上电停留 2.0 秒，数码管与点阵以 2 Hz 闪烁，蜂鸣器奏响 POST 短鸣；<br>
    2. <code>S_IDLE</code>（待机）：数码管显示当前关卡，按【开始】（KEY14）进入预览；<br>
    3. <code>S_PREVIEW</code>（预览）：点阵全红显示目标图案，倒计时 5 秒，结束自动散落；<br>
    4. <code>S_PLAYING</code>（对局）：装载 30s/40s/60s 倒计时，响应平移/旋转/锁定；倒计时 ≤10s 触发绿色告急幽灵；<br>
    5. <code>S_WIN</code>（通关）：全图 100% 吻合时进入，数码管显示 PASS，自动升关；第三关胜利大通关；<br>
    6. <code>S_FAIL</code>（失败）：超时归零或错拼锁定进入，显示 FAIL，等待玩家按【开始】重新开局。
  </div>

  <div class="defense-q">Q2：在增加第三关时，为什么不直接把 level 改为 2 位宽的总线？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    这是经过实测数据验证的<strong>关键时序优化</strong>！<br>
    在芯片利用率已达 98% 时，若将 <code>level</code> 改为 2 位宽，下游三个模块的解码输入都会增加，Quartus 会插入多级级联比较器，实测导致整机 Fmax 从 48.87 MHz 跌落到 46 MHz 以下；<br>
    我们保留原有的 1 位 <code>level</code> 寄存器不动，仅额外增加一个 1 位的 <code>lvl3</code> 独立标志，使整机 Fmax 稳定收敛在 54.27 MHz，零时序代价达成需求。
  </div>
</div>

---

## 📌 随机抽查模块四：拼图引擎与面积优化 (`puzzle_ctrl`)

<div class="defense-box">
  <div class="defense-title">🧩 抽查模块 4：拼图核心引擎 (puzzle_ctrl)</div>

  <div class="defense-q">Q1：芯片只有 1270 个 LE 且无 RAM，你们是怎么把拼图引擎做进去的？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    老师，这是我们全项目最具突破性的<strong>五代微架构面积演进成果</strong>：<br>
    早期版本为每个零片保持 64 位全局位图，综合出来高达 4,690 个 LE，溢出了三倍多。<br>
    我们进行了两项重大重构：<br>
    1. <strong>行扫描渲染管线</strong>：利用硬件点阵 1 kHz 一拍扫一行的本质，将引擎重构为<strong>“一拍只计算即将显示的那一行（8 位宽）”</strong>，组合逻辑规模骤降 80%；<br>
    2. <strong>碰撞检测串行化</strong>：按键发生时，利用 50 MHz 在 100～320 ns 内串行轮询邻块，替代了庞大的 16 组宽比较器。<br>
    最终整机仅消耗 <strong>1,264 个 LE（99.5%）</strong>，奇迹般地压榨进了 EPM1270 芯片！
  </div>

  <div class="defense-q">Q2：如果玩家把相同形状的零片调换了位置，但拼出的图案完全正确，系统会判定通关吗？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    <strong>绝对会判定通关！</strong>这就是我们在开发中排查出的 <strong>ERR-021 等效多解性缺陷</strong>。<br>
    拼图在几何上存在等价摆法（如第二关阶梯有 2 种合法拼法，多块同形时甚至有多达 24 种拼法）。若按坐标比对，玩家拼对了却会被硬件判负；<br>
    我们的引擎采用了<strong>“整帧像素并集比对法”</strong>：在一帧周期内逐行累积全部已锁定零片的点亮像素，并与目标图案逐行比对。只要合成出的画面 100% 重合且无重叠，硬件立即判定通关！
  </div>

  <div class="defense-q">Q3：零片顺时针旋转 90° 是如何防止越界和重叠的？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    旋转操作完全复用了<strong>串行碰撞检测管线</strong>。<br>
    按【旋转】键时，引擎首先在局部包围盒内根据 \((r', c') = (c, h - 1 - r)\) 计算出旋转后的新形状；<br>
    随后新形状直接输入碰撞检测单元，一旦发现旋转后超出 8×8 边界或者与已锁定的邻块重叠，硬件内部的 <code>chk_hit</code> 当拍拉高，坐标与朝向寄存器被锁死禁止写入。因此零片绝对不会穿模。
  </div>
</div>

---

## 📌 随机抽查模块五：固化图库与随机数 (`rom` & `rng_lfsr`)

<div class="defense-box">
  <div class="defense-title">🎲 抽查模块 5：图库与随机源 (pattern_rom, piece_rom, rng_lfsr)</div>

  <div class="defense-q">Q1：怎么证明第二关和第三关随机抽取的图案一定能被四块零片拼出来？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    我们在编码前编写了专用离散几何穷举脚本 <code>scripts/check_geometry.py</code> 进行了数学证明：<br>
    1. <strong>面积绝对守恒</strong>：四块异形零片面积分别为 3+2+5+6 = 16 格，图案也严格为 16 格；<br>
    2. <strong>单平移可解性证明</strong>：脚本穷举遍历了状态空间，证明田字、十字、SZ 和阶梯图案在<strong>只许平移、不许旋转</strong>的严格限制下，均至少存在 1 种合法的完美铺满解，保证了游戏 100% 有解。
  </div>

  <div class="defense-q">Q2：LFSR 随机数发生器的原理是什么？遇到全 0 怎么办？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    我们采用 8 位 Galois LFSR，特征多项式为国际标准的本原多项式 \(x^8 + x^6 + x^5 + x^4 + 1\)，满周期严格为 255 拍；<br>
    全 0 是 LFSR 的<strong>吸收死锁态</strong>，我们在硬件中设计了双重防死锁电路：复位装载非零种子 <code>0x5A</code>；移位末端增加全零比较器，若偶发陷入全 0 瞬间强行弹回非零初值，确保永不死机。
  </div>
</div>

---

## 📌 随机抽查模块六：显示驱动与格式化 (`disp_format`, `seg_scan`, `dot_matrix_scan`)

<div class="defense-box">
  <div class="defense-title">💡 抽查模块 6：数码管与点阵驱动</div>

  <div class="defense-q">Q1：计算倒计时的十位和个位时，为什么坚决不能用硬件除法器 / 10？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    老师，在 MAX II 这种没有硬件乘除法核的 CPLD 上写 <code>/ 10</code> 会推断出 2 个 <code>lpm_divide</code> IP 核，消耗超过 100 个 LE；更致命的是除法器进位链长达 <strong>26 ns</strong>，直接把系统主频拉低到 39 MHz，造成严重时序违例！<br>
    我们根据倒计时最大 60 秒的特征，采用了 <strong>64 项常量 CASE 查找表</strong>。综合后只生成了极轻量的 LUT 门电路，<strong>实测仅耗费 17 个 LE</strong>，延时不到 3 ns，彻底根除了关键路径瓶颈。
  </div>

  <div class="defense-q">Q2：点阵屏和数码管的刷新率是多少？为什么不会产生重影与闪烁？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    刷新率均为 <strong>125 Hz</strong>（由 1 kHz 节拍轮询 8 位得出），远高于人眼 60 Hz 的临界闪烁融合频率，因此视觉极其稳定；<br>
    没有重影的原因在于<strong>“寄存器同拍同步更新”</strong>：行选通与双色列数据（以及数码管的段码与位选）全部在 50 MHz 主时钟的同一上升沿原子性锁存，引脚状态在同一个 20 ns 周期内瞬间切换，无需任何死区消隐也能做到绝对无重影。
  </div>
</div>

---

## 📌 随机抽查模块七：蜂鸣器音效合成 (`buzzer_ctrl`)

<div class="defense-box">
  <div class="defense-title">🎵 抽查模块 7：音频与音乐合成 (buzzer_ctrl)</div>

  <div class="defense-q">Q1：单音蜂鸣器是怎么播放马里奥背景音乐的？音准如何保证？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    我们采用<strong>数控分频（NCO）技术</strong>：将 50 MHz 经 ÷256 预分频得到 195.3125 kHz，随后的 8 位半周期计数器查表装载音符分频值，向蜂鸣器输出 50% 占空比方波；<br>
    实测 E5～G6 八个音符的频率误差仅在 <strong>0.08%～0.45%</strong> 之间，远优于人耳 1.5% 容差，音准极其精确。
  </div>

  <div class="defense-q">Q2：什么是“连奏填音 (Legato Infill)”？为什么它反而能节省 5 个 LE？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    原曲休止符占比超过 50%，方波频繁通断使得蜂鸣器声音干瘪断续（ERR-050）。我们把休止符全部填成下一个音符的音高，实现 16 步连奏，声音立刻变得圆润好听；<br>
    填补后旋律表相邻项大量重复，Quartus 在逻辑综合时能够将这些相同项大面积合并化简，<strong>整机 LE 面积反而奇迹般地节约了 5 个（从 1269 降至 1264 LE）</strong>！
  </div>
</div>

---

## 📌 随机抽查模块八：整机引脚与时序收敛 (`puzzle_top`)

<div class="defense-box">
  <div class="defense-title">👑 抽查模块 8：整机系统顶层与时序收敛</div>

  <div class="defense-q">Q1：你们整机占用了多少芯片资源？最差路径的裕量是多少？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    根据 Quartus II 9.1 TimeQuest 静态时序分析器（STA）对网表的真实报告：<br>
    1. <strong>逻辑资源利用</strong>：<strong>1,264 / 1,270 个逻辑单元（99.5% 极限占满）</strong>，127 / 127 个 LAB 全部排满；<br>
    2. <strong>引脚分配</strong>：52 个物理引脚 100% 显式锁定，无任何悬空漏配；<br>
    3. <strong>时序性能</strong>：在 50 MHz（20.000 ns）时钟约束下，<strong>Setup Slack 裕量达 +1.572 ns</strong>，Hold Slack 为 +1.078 ns，最高运行频率 <strong>Fmax 为 54.27 MHz</strong>，时序极其健壮收敛。
  </div>

  <div class="defense-q">Q2：倒计时剩余 10 秒时的告急幽灵是什么颜色？为什么这样设计？</div>
  <div class="defense-a">
    <strong>3秒极速应答：</strong><br>
    告急幽灵采用<strong>“绿色 + 2 Hz 频率闪烁”</strong>。<br>
    因为双色点阵中未选中的零片是红色，锁定的零片是黄色。如果幽灵做成红或黄，会与零片混叠在一起；<br>
    而活动零片是<strong>常亮绿色</strong>，幽灵是<strong>闪烁绿色</strong>，玩家依靠动静反差一眼就能看清目标底图；且硬件上直接借用主状态机已有的 2 Hz 标志，<strong>实测增加 0 个 LE</strong>，达到了极高的人机工效与轻量化平衡。
  </div>
</div>
