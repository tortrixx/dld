# Zensical 项目展示站

本站是对现有 Docsify 文档站的**增量迁移候选**，以技术展示与工程阅读为主，不包含答辩速查功能。原始资料、测试与代码均保持不变。

## 本地构建

```bash
python -m pip install 'zensical>=0.1,<0.3'
python zensical-site/scripts/prepare.py
cd zensical-site
zensical serve
# 或 zensical build
```

`prepare.py` 将现有六组模块文档的非答辩部分和展示素材复制到 Zensical 源目录，防止机械复制产生第二套事实内容。每次站点构建都要先运行它。生成的 `docs/modules/`、`docs/assets/images/` 不应手动编辑。迁移成功后可以进一步改为带哈希与链接审计的正式内容管线。

## 验收与发布

1. PR 中不修改 RTL、仿真、Quartus 工程、事实模型及现有 Docsify 页面。
2. 先运行现有 `extract_facts.py --check` 和 `check_docs.py`，再构建新站。
3. 在本机检验首页、六个模块、截图、GIF、搜索、中文、移动端与深色模式。
4. 旧站在 PR 合并前继续运行；合并切换 GitHub Pages 的构建工作流后再验证线上路径。
5. 构建失败时不应发布新站；不要绕开校验门禁。

注意：`docs-site-plan.md` 是过期方案，不能作为新站架构依据；现有有效约束见根目录 `HANDOVER.md`。
