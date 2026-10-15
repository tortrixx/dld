# `book/` —— 技术文档站（Material for MkDocs）

这是 `tortrixx/dld` 的**技术文档站**源码。它与 [`../site/`](../site/README.md)
（Vite + React 的**工程展示站**）是**两层互补**的站点，两者共用同一套工程事实
（`../facts/facts.json`），互相链接。

| | 展示站 `site/` | 文档站 `book/` |
|---|---|---|
| 在线地址 | `https://tortrixx.github.io/dld/` | `https://tortrixx.github.io/dld/docs/` |
| 面向 | 答辩现场的**整体观感** | **系统性阅读**与逐条查证 |
| 内容 | 首屏、交互点阵、时序播放器、演示动画 | 架构、接口契约、数据字典、时序、证据、答辩稿 |

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
python book/scripts/book.py build                # 生成 + mkdocs build --strict
python book/scripts/book.py check                # 生成 + 一致性门禁（不构建）
python book/scripts/check_book.py <页面...>       # 只查指定页面（写文档时自检用）

# 构建到"和展示站合并"的布局（本地复现线上）：
python book/scripts/book.py build --site-dir ../site/dist/docs
```

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

线上是**一个** GitHub Pages 站点，两个入口：

```
https://tortrixx.github.io/dld/         ← site/ 展示站
https://tortrixx.github.io/dld/docs/    ← book/ 文档站
```

合并方式见 `.github/workflows/pages.yml`：**先** `vite build`（它会清空 `site/dist`），
**再** `BOOK_SITE_DIR=site/dist/docs mkdocs build`，最后上传 `site/dist`。
顺序反过来文档会被 Vite 清掉 —— 这一点在工作流里也写了注释。
