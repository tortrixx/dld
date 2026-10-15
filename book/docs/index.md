---
hide:
  - navigation
  - toc
---

<!-- ==========================================================================
     首页是**裸 HTML**（不是 Markdown 正文）：编辑式着陆页需要精确控制版式，
     Markdown 的行内元素模型表达不了 hero / 事实条 / 章节栅格这类版块。
     样式全部在 `stylesheets/extra.css` §11，以 `.home` 为作用域。
     `hide: [navigation, toc]` 去掉左边栏与目录 —— 首页不是"一页文档"。

     ⚠️ 内联 HTML 里的相对链接**不会被 MkDocs 改写**，必须自己写对：
     目标是 `xx/yy.md` → 输出目录是 `xx/yy/`；`xx/index.md` → `xx/`。
     `book/scripts/check_book.py` 会把这些 `href` 也逐个查存在性，别写错。
     ========================================================================== -->

<div class="home">

<section class="home-hero home__inner">
  <div class="home-copy">
    <p class="eyebrow"><span class="dot"></span>数字电路与逻辑设计实验（下）· 题目 4</p>
    <h1>简易拼图游戏<span class="serif">1270 个逻辑单元里<span class="accent-period">.</span></span></h1>
    <p class="home-sub">纯 VHDL-93 RTL。<br>没有 CPU、没有 IP 核、没有软核。</p>
    <p class="home-lead">
      在一块 <strong>8×8 双色点阵</strong>上玩拼图：先看 5 秒目标图案，零片随机散落；
      用 <strong>4×4 矩阵键盘</strong>选择、上下左右移动、必要时原地旋转 90°，
      把零片拼回目标形状后逐块按【确认】锁定。三关递增，第三关图案从四幅库中随机。
    </p>
    <div class="home-actions">
      <a class="btn btn--primary" href="01-project/overview/">从头读起 <span class="arw" aria-hidden="true">→</span></a>
      <a class="tlink" href="04-interfaces/event-traces/">追踪一次按键的信号链 <span aria-hidden="true">↓</span></a>
    </div>
    <p class="home-credit">
      源码在 <a href="{{repo}}">GitHub · tortrixx/dld</a>。
      本站里每个数字都由 <code>facts/facts.json</code> 机械注入 ——
      手写数字会被门禁拦下，所以它们不会过期。
    </p>
  </div>

  <div class="home-figure">
    <svg class="matrix" viewBox="0 0 260 260" role="img"
         aria-label="8×8 双色点阵的对局中盘面示意：黄色为已锁定零片，绿色为当前选中的零片，红色为未选中的零片，其余为熄灭">
      <rect class="matrix-bg" x="8" y="8" width="244" height="244"></rect>
      <g class="matrix-grid">
        <path d="M8 38.5h244M8 69h244M8 99.5h244M8 130h244M8 160.5h244M8 191h244M8 221.5h244"></path>
        <path d="M38.5 8v244M69 8v244M99.5 8v244M130 8v244M160.5 8v244M191 8v244M221.5 8v244"></path>
      </g>
      <g class="matrix-cells">
        <rect class="c-lock" x="14" y="74" width="29" height="29"></rect>
        <rect class="c-lock" x="44" y="74" width="29" height="29"></rect>
        <rect class="c-lock" x="14" y="104" width="29" height="29"></rect>
        <rect class="c-lock" x="44" y="104" width="29" height="29"></rect>
        <rect class="c-sel" x="44" y="164" width="29" height="29"></rect>
        <rect class="c-sel" x="74" y="164" width="29" height="29"></rect>
        <rect class="c-sel" x="74" y="194" width="29" height="29"></rect>
        <rect class="c-piece" x="14" y="14" width="29" height="29"></rect>
        <rect class="c-piece" x="44" y="14" width="29" height="29"></rect>
        <rect class="c-piece" x="164" y="14" width="29" height="29"></rect>
        <rect class="c-piece" x="134" y="74" width="29" height="29"></rect>
        <rect class="c-piece" x="194" y="194" width="29" height="29"></rect>
        <rect class="c-piece" x="224" y="194" width="29" height="29"></rect>
        <rect class="c-piece" x="224" y="164" width="29" height="29"></rect>
      </g>
    </svg>
    <p class="matrix-legend">
      <span><i class="sw sw-red"></i>未锁定零片</span>
      <span><i class="sw sw-green"></i>当前选中</span>
      <span><i class="sw sw-yellow"></i>已锁定</span>
      <span><i class="sw sw-off"></i>熄灭</span>
    </p>
    <p class="matrix-note">
      每个点只有 <strong>4 种状态</strong>（灭 / 红 / 绿 / 黄）——
      这正是"告急幽灵"那一轮必须改用<strong>闪烁</strong>而不是换颜色的原因。
    </p>
  </div>
</section>

<div class="facts home__inner">
  <span><b>{{fact:build.sta.fmax_mhz}}</b> MHz Fmax（约束 50 MHz，0 违例）</span>
  <span><b>{{fact:build.pins_locked}}</b> 个引脚全部显式锁定</span>
  <span><b>{{fact:sim.totals.assertions}}</b> 条仿真断言，全部通过</span>
  <span><span class="sym" aria-hidden="true">↗</span>{{fact:hierarchy.counts.entities}} 个实体 · {{fact:sim.totals.modules}} 个模块/场景</span>
</div>

<section class="home-section home__inner">
  <div class="section-head">
    <div>
      <p class="eyebrow">从"看懂它"到"讲清它"</p>
      <h2>站点地图<span class="accent-period">.</span></h2>
    </div>
    <p>第一次接触这个项目，<br>顺着编号读一遍就够了。</p>
  </div>

  <div class="chapters">
    <a class="chapter chapter--first" href="01-project/overview/">
      <span class="chapter__num">01</span>
      <div>
        <h3>项目</h3>
        <p>它是什么、题目要求落在哪、做到了什么、<strong>还差什么</strong>。</p>
        <span class="chapter__start">从这里开始</span>
      </div>
      <span class="chapter__arrow" aria-hidden="true">→</span>
    </a>
    <a class="chapter" href="02-architecture/system-overview/">
      <span class="chapter__num">02</span>
      <div>
        <h3>系统架构</h3>
        <p>1 张总框图 + 7 张子系统图；真实层级、数据通路、时钟节拍、面积账。</p>
      </div>
      <span class="chapter__arrow" aria-hidden="true">→</span>
    </a>
    <a class="chapter" href="03-modules/">
      <span class="chapter__num">03</span>
      <div>
        <h3>模块设计</h3>
        <p>15 个实体逐个讲：端口契约、内部原理、<strong>一次真实输入输出</strong>、验证证据。</p>
      </div>
      <span class="chapter__arrow" aria-hidden="true">→</span>
    </a>
    <a class="chapter" href="04-interfaces/">
      <span class="chapter__num">04</span>
      <div>
        <h3>接口与信息传递</h3>
        <p>跨模块连接总表、数据字典与位序约定、时序契约、端到端流程 A~E。</p>
      </div>
      <span class="chapter__arrow" aria-hidden="true">→</span>
    </a>
    <a class="chapter" href="05-gameplay/startup/">
      <span class="chapter__num">05</span>
      <div>
        <h3>游戏流程</h3>
        <p>上电自检 → 一局生命周期 → 移动与旋转 → 胜负判定 → 音效。</p>
      </div>
      <span class="chapter__arrow" aria-hidden="true">→</span>
    </a>
    <a class="chapter" href="06-verification/strategy/">
      <span class="chapter__num">06</span>
      <div>
        <h3>验证与证据</h3>
        <p>为什么这么验、184 条断言各在验什么、12 张真实 Quartus 截图怎么看。</p>
      </div>
      <span class="chapter__arrow" aria-hidden="true">→</span>
    </a>
    <a class="chapter" href="07-implementation/compilation/">
      <span class="chapter__num">07</span>
      <div>
        <h3>实现到 FPGA</h3>
        <p>清洁编译、SEED 重扫、资源与时序报告、52 条引脚锁定、可复现性。</p>
      </div>
      <span class="chapter__arrow" aria-hidden="true">→</span>
    </a>
    <a class="chapter" href="08-debugging/">
      <span class="chapter__num">08</span>
      <div>
        <h3>调试与取舍</h3>
        <p>ERR-001~056 索引与 10 条复盘；每条取舍写清得到什么、失去什么。</p>
      </div>
      <span class="chapter__arrow" aria-hidden="true">→</span>
    </a>
    <a class="chapter" href="09-defense/presentation-outline/">
      <span class="chapter__num">09</span>
      <div>
        <h3>答辩</h3>
        <p>5~8 分钟 PPT 结构、现场演示脚本、31 问 FAQ、技术深挖。</p>
      </div>
      <span class="chapter__arrow" aria-hidden="true">→</span>
    </a>
  </div>
</section>

<section class="home-strip home__inner">
  <div>
    <p class="eyebrow">先看结论，再追证据</p>
    <h2>一次按键，五级信号链。</h2>
    <p>
      物理行列 → 200 Hz 扫描与 40 ms 消抖 → 按键事件 → 状态机译码 → 拼图引擎的越界/重叠判定
      → 64 位帧经 <code>mrow</code> 切行 → 点阵与数码管刷新。每一级都有真实信号名与仿真证据。
    </p>
  </div>
  <a class="btn btn--outline" href="04-interfaces/event-traces/">端到端追踪 →</a>
</section>

<section class="home-strip home__strip--last home__inner">
  <div>
    <p class="eyebrow">证据优先，缺什么就写什么</p>
    <h2>184 条断言，12 张实测截图，0 张硬件照片。</h2>
    <p>
      每条断言都写清"能证明什么、<strong>不能</strong>证明什么"；脚本渲染的辅助波形与
      真实 Quartus GUI 截图分开标注；真实开发板照片<strong>一张都没有</strong>，
      所以补拍清单也一并写好。
    </p>
  </div>
  <a class="btn btn--outline" href="06-verification/board-validation/">看缺失的证据 →</a>
</section>

</div>
