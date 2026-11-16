# 技术展示站维护入口（2026-11-16）

当前新站采用 **Zensical**，公开内容不再以答辩为中心。以下新约定优先于本文后半段保留的 Docsify 历史说明。

- 网站源与构建：[`zensical-site/README.md`](zensical-site/README.md)。
- 发布、旧链接兼容与回滚：[`zensical-site/MIGRATION.md`](zensical-site/MIGRATION.md)。
- 实际验收及剩余问题：[`zensical-site/VALIDATION.md`](zensical-site/VALIDATION.md)。
- 维护专题页：`zensical-site/docs/`；维护六组模块技术内容：`docs/subsystems/`，转换脚本去除问答并生成独立发布源。
- 指标以 `facts/facts.json`、`quartus/build_provenance.json` 和原测试记录为来源。先运行 `extract_facts.py --check`，再准备发布源并执行 `zensical build --strict`。
- `.generated/`、`site/` 都不入库。只复制明确引用的展示图片，不复制课程 PDF、实验报告与内部日志。
- 本次刷新事实模型以同步此前 RTL 注释整理后的行号；没有更改 RTL、Quartus 工程或仿真记录，没有重签历史证据。
- 原 `audit_evidence.py` 检查保留；本次诊断存在 13 FAIL，详见验证记录。不能把历史编译与断言结果写成当前源码的新验收。
- `docs-site-plan.md` 已过期，不作为架构依据。


## 工程图与证据维护

- 系统框图由 `scripts/gen_design_diagram.py`、`gen_overview_diagram.py` 和 `gen_flow_diagram.py` 生成。
- draw.io 交付件由 `scripts/gen_drawio_figures.py` 管理。修改图后运行相应 `--check`，确认与 RTL／事实模型一致。
- 仿真截图原件位于 `docs/图/`，站内裁图副本位于 `docs/assets/images/`；不要直接修改被事实模型按字节记录的证据。
- 不使用合成波形代替真实 Quartus GUI 结果；软件渲染 GIF 始终标注为规则模型。
- 修改 RTL 后需完整仿真、清洁编译、时序检查和必要的上板复测，再更新事实与构建记录。
- 个人报告中的身份字段只用于仓库外的提交产物，不写入公开源树。

旧 Docsify 的配置与制图维护细节保留在此文件的 Git 历史中。当前构建与发布请只使用上方的新站入口。
