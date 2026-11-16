# Zensical 技术展示站

面向 GitHub 访客、电子工程学生与开发者。公开输出只包含项目说明、六组模块与引用到的工程图片，排除课程资料、报告和内部日志。

## 构建

```bash
python -m pip install -r zensical-site/requirements.txt
python scripts/extract_facts.py --check
python scripts/check_docs.py
python zensical-site/scripts/prepare.py
cd zensical-site
zensical build --strict
cd ..
python zensical-site/scripts/check_site.py
```

预览：完成 `prepare.py` 后在 `zensical-site/` 运行 `zensical serve`。

## 内容来源

- `docs/`：手工维护的公开专题页与少量 CSS。
- `../docs/subsystems/`：六组模块的技术内容唯一来源。转换时只去除答辩问答，保留设计解释和波形；必要的问答技术结论整理到工程取舍页。
- `../facts/facts.json`：指标及历史仿真表的机器来源；先通过事实模型检查再构建。
- `.generated/`：清空后重建的发布源，不手改、不入库。
- `site/`：构建结果，不入库。

`prepare.py` 只复制被引用的图片，生成逐文件 SHA-256 清单。`check_site.py` 校验生成 HTML、锚点、CSS 资源、复制字节和 `/dld/` 路径边界。已知旧 Docsify `#/subsystems/…` 链接由小型兼容脚本迁移到对应模块页；旧节内锚点回到模块页。

Zensical 与 MkDocs 并非完全等价：当前固定使用实际验证过的 `zensical==0.1.1`；`site_dir` 必须在项目根内，图标函数使用 `zensical.extensions.emoji`。升级时重做严格构建和浏览器验收。

## 发布和回滚

见 [MIGRATION.md](MIGRATION.md)。验证记录见 [VALIDATION.md](VALIDATION.md)。`docs-site-plan.md` 是过期方案，不能用它恢复旧架构。

历史 Quartus 结果只作历史记录展示；本次维护未运行硬件综合或重新签发测试证据。`audit_evidence.py` 的既有失败见验证记录。
