# 网站验收记录

日期：2026-11-16（北京时间）。工作分支：`feat/zensical-project-showcase`，对应 PR #2。

## 本地构建与静态检查

- 安装并实际运行 `zensical==0.1.1`，Python 3.12。
- `zensical build --strict`：exit 0，No issues found。
- `check_site.py`：15 个 HTML（含 404），759 个本地引用及锚点通过；CSS 资源、图片／脚本／样式哈希和 `/dld/` 边界通过。
- `extract_facts.py --check`：通过。同步的是此前 RTL 注释整理后的行号／描述；`build`、`sim` 与原证据不变。
- `check_docs.py`：通过，原 Docsify 校验未删除。
- `check_privacy.py`：通过；全历史扫描仍报告脚本已登记的历史残留，未重写历史。新发布树不包含这些文件。
- `check_geometry.py`：通过；`check_plans.py`：exit 0，ALL PLAN CHECKS PASSED。随机可达性抽样中四幅图案分别有 1/2/6/2 个布局在搜索上限内未判定，不能视作全部可解证明。
- `git diff --check`：通过。

## 浏览器实测

使用实际 Chromium，先浏览桌面站，再以 320、390、768 CSS px 的同源 iframe 逐页渲染全部 14 个公开页面。iframe 是独立布局视口，不通过缩放截图伪造手机尺寸；传统滚动条占 15px，正文 clientWidth 分别为 305、375、753px。此检查不等同于真机触摸测试。

- 42 个窄屏／平板页面视图：无文档横向溢出，未发现破图。
- 桌面：14 页逐页检查无横向溢出或破图；中文正文、导航、卡片、GIF 与浅色主题可用。
- 320px：汉字换行、双列指标与侧栏打开可用。
- 390px：深色主题切换为 slate；中文“旋转”返回 9 个搜索结果，结果有高亮和深层链接。
- 平板：正文、图片和模块内容适应宽度。
- 架构页：VHDL 高亮有 104 个 token span；图片点击后打开 GLightbox，全屏可读且可关闭。
- 已知旧模块 hash 链接实际跳转至新 `modules/03_game_fsm/`，标题与目标正确。
- 控制台看到浏览器扩展自己的 metadata 错误，不来自站点脚本。

截图与机器可读矩阵放在 `zensical-site/qa/`，它们不进入 `docs_dir` 或正式发布树。

## 既有工程限制

`python scripts/audit_evidence.py` 实际结果：**13 FAIL / 4 WARN / 9 OK**。失败涉及历史仿真／固件指纹与当前 `rtl/puzzle_top.vhd` 不同。对照构建记录所指历史提交，去注释差异是 component 声明重排；其余 RTL 的逻辑指纹相同。但原校验不认可这个变化，因此没有把失败改写为通过，也没有修改 RTL、指纹或轮次记录来绕过它。

本环境没有 Quartus 和开发板，未重跑 RTL 仿真、综合、Fitter、STA 或烧录。站点中的资源和 184 条断言是历史证据；验证页已公开说明当前审计限制。

## 发布状态

PR #2 已合并，正式站点已上线并完成浏览器复核。

- PR 构建：[43870864476](https://github.com/tortrixx/dld/actions/runs/43870864476)，conclusion=success。
- 合并提交：`cdf1ebc72131d483d5436757b7eb77341f1aba74`。
- Pages 构建与部署：[43871017583](https://github.com/tortrixx/dld/actions/runs/43871017583)，build-and-verify、deploy 均 success。
- 正式地址：<https://tortrixx.github.io/dld/>。
- 线上实测：首页 h1、四张导航卡片和 GIF 正常；文档 scrollWidth 等于 clientWidth。
- 深层 `modules/03_game_fsm/` 的状态图及 GUI 波形均加载成功。
- 深色模式实际切换到 slate；中文“旋转”得到 9 个结果，点击首个结果成功到达工程取舍对应锚点。
- 正式站点已恢复浅色并保留供检查。此记录更新不改变站点发布源。


## 修改文件分组

- `.github/workflows/pages.yml`：严格构建、子路径与发布面检查、main 发布和 Docsify 手动回滚。
- `.github/workflows/zensical-preview.yml`：同一构建链，PR artifact 不发布。
- `zensical-site/mkdocs.yml`、`requirements.txt`：合法输出目录、固定版本、原生图标／代码／图片扩展。
- `zensical-site/scripts/prepare.py`、`check_site.py`：确定性内容转换、事实插值、图片白名单与渲染链接审计。
- `zensical-site/docs/`：首页与七个专题、六组模块入口、样式和旧链接兼容脚本；模块技术内容仍从原文档生成。
- `facts/facts.json`：只刷新 RTL 解析元数据，`design/build/sim/images/errors` 五组与迁移前逐项相同。
- `README.md`、`HANDOVER.md`、`zensical-site/README.md`、`MIGRATION.md`：维护入口及回滚说明。
- `zensical-site/qa/`：截图与浏览器矩阵，不发布到 Pages。

`git diff --exit-code -- rtl sim quartus scripts` 通过，原硬件、测试、工程与校验脚本无改动。
