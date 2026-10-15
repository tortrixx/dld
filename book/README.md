# `book/` —— 项目网站 + 技术文档（Material for MkDocs）

这是 `tortrixx/dld` 的**对外网站**，也是项目的技术文档本体：线下与线上的地址都是

**<https://tortrixx.github.io/dld/>**

> ⚠️ **站点取舍（2026-10-15 第 27 工作阶段）**：本工作阶段最初建的是**两层**站点 ——
> `site/`（Vite + React 的工程**展示**站，挂在 `/dld/`）与本站（挂在 `/dld/docs/`）。
> 随后**用户决定去掉展示站、只保留本站并让它占用根路径 `/dld/`**，于是：
> * `site/` 整个目录已删除（连同它的交互点阵、时序播放器、演示动画与前端测试）；
> * `book/mkdocs.yml` 的 `site_url` 改为 `https://tortrixx.github.io/dld/`；
> * `.github/workflows/pages.yml` 只剩"构建 `book/` → 上传 `book/site`"一条线。
>
> 好处是**只有一份事实、一个构建、一个门禁**，不再有"两个站点互相打架"的可能。

---

## 一条命令起本地站

```bash
# 在仓库根目录执行
python -m venv book/.venv

# Windows
book/.venv/Scripts/python -m pip install -r book/requirements.txt
# Linux / macOS
book/.venv/bin/python -m pip install -r book/requirements.txt

python book/scripts/book.py serve        # → http://127.0.0.1:8000/
```

> ⚠️ **不要**直接 `mkdocs serve`。文档站里有三类内容是**构建前必须先生成**的：
>
> 1. `facts/facts.json`（从 `rtl/` `sim/` `quartus/` 抽取）
> 2. `docs/_generated/`（从 facts.json 生成的表格页）
> 3. `docs/assets/`（从 `docs/图/` 同步的素材）
>
> `book/scripts/book.py` 会按这个顺序做完再交给 MkDocs，
> 直接跑 `mkdocs` 会得到"页面缺片段"的报错或**陈旧的表格**。

### 网络受限时

`pip` / `npm` 需要外网。如果本机走代理：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7890'; $env:HTTPS_PROXY='http://127.0.0.1:7890'
book\.venv\Scripts\python -m pip install -r book\requirements.txt
```

CI（GitHub Actions）不需要代理。

---

## 其它命令

```bash
python book/scripts/book.py gen                  # 只生成（不构建）
python book/scripts/book.py build                # 生成 + mkdocs build --strict + 产物自证
python book/scripts/book.py check                # 生成 + 一致性门禁（不构建）
python book/scripts/check_book.py <页面...>       # 只查指定页面（写文档时自检用）

# 改了 CSS / 版式之后**必须**跑这个：无头浏览器按浅色/深色各拍一遍
python book/scripts/book.py build && python book/scripts/shoot.py
python book/scripts/shoot.py --all               # 每个一级章节各挑一页

# 产物默认落在 book/site/（相对 book/mkdocs.yml 所在目录）
# 要放到别处验证：给 --site-dir 传**相对 book/ 的路径**
python book/scripts/book.py build --site-dir ../somewhere-else
```

> `mkdocs --strict` 只检查**链接与锚点**，对版式一无所知。
> 视觉回归靠 `shoot.py`（产物在 `book/review/`，不入库）——
> 本轮两个真缺陷（深色主题"黑报头 + 白正文"、片段里的表缩成半宽）都是它抓到的。

---

## 目录说明

```
book/
├── mkdocs.yml            Material 配置：strict + hooks + snippets + 中文搜索
├── requirements.txt      锁版本的 Python 依赖
├── AUTHORING.md          ★ 写页面之前**必须**读的规范
├── hooks/facts.py        把 {{fact:...}} / {{src:path:line}} 注入 Markdown
├── scripts/
│   ├── book.py           唯一入口：gen / build / serve / check
│   ├── gen_pages.py      生成 docs/_generated/ 下的表格页
│   ├── sync_assets.py    把 docs/图/ 同步进 docs/assets/
│   └── check_book.py     一致性门禁（页面级 + 站点级）
└── docs/
    ├── index.md                   总览
    ├── 01-project/ … 09-defense/   52 个内容页（导航顺序即阅读顺序）
    ├── stylesheets/extra.css      自持字体栈 + 表格/图注/代码排版
    ├── assets/brand/              品牌图标（手写，入库）
    ├── assets/hardware/           **有意为空**：仓库里没有真实硬件照片
    └── _generated/                ★ 机械生成的片段（**不入库**，构建前重生成）
```

### 为什么 `_generated/` 不入库

入库 = 允许过期。本项目已经被"文档与代码不一致"咬过一次（`docs/06` 的 ERR-022：
文档里把端口位宽抄错）。所以这里的规则是**每次构建前重新生成**，
从根上不存在"忘了更新"这种状态。

### 为什么页面里不写数字

页面里的 LE / LAB / Fmax / 断言条数一律写成 `{{fact:build.fit.le}}`
这样的占位符，由 `hooks/facts.py` 在构建时替换。**写错路径会直接构建失败**，
这比"上线后被人发现数字不对"便宜得多。

表格同理：端口表、连接表、层级表、引脚表、断言明细、图片清单、ERR 索引
全部用 `--8<-- "_generated/xxx.md"` 引入生成页。

---

## 门禁都查什么

`python book/scripts/book.py check`：

* `facts/facts.json` 是否与 `rtl/` `sim/` `quartus/` 一致（重新生成后逐字节比对）
* 每个页面：`{{fact:}}` 能否解析、`{{src:}}` 指向的文件是否**已入库**、
  `--8<--` 引用的生成页是否存在、图片是否存在、内部链接是否可达、有无残留占位
* 站点级：`mkdocs.yml` 的 nav 与 `docs/` 是否互为子集（不漏页、不缺页）
* 每个真实实体在文档里是否被提到；关键读数是否出现"同一指标两个值"
* 加上 `mkdocs build --strict` 本身对导航、链接、锚点的检查

**不允许为了让检查通过而删掉链接或降低标准** —— 那等于把门禁变成装饰。

---

## 部署

线上是**一个**站点：

```
https://tortrixx.github.io/dld/
```

见 `.github/workflows/pages.yml`：装 Python 依赖 → `extract_facts.py --check` →
`book.py check` → `book.py build`（含 `--strict`）→ 自证产物完整且**没有外部 CDN
脚本引用** → 上传 `book/site`。

> ⚠️ `site_url` 必须是 `https://tortrixx.github.io/dld/`：Material 由它推出
> `base_url = /dld/`，所有静态资源引用都带这个前缀。写错会表现为"本地好、线上
> CSS/JS 全 404"。
