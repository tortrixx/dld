# 发布与回滚

迁移前 main：`f158c7814a8d36d5834bd6852a624b05b9fdd93e`。原 Docsify 源码、依赖和校验脚本保留。

1. 在工作分支完成事实模型、原文档、隐私、Zensical strict、生成资源和浏览器验收。
2. PR CI 只构建并上传预览 artifact，不发布 Pages。
3. 验收后合并 PR，main 的 Pages 工作流使用 Zensical，上传 `zensical-site/site/`。
4. 等待部署成功，检查正式 `/dld/` 首页、深层模块、搜索和图片。只有这一步完成才可宣称正式上线。

## 快速回滚

在 GitHub Actions 选择 **Deploy technical showcase to Pages** → **Run workflow** → main → `renderer=docsify`。工作流将原 Docsify 发布白名单打包并部署，不需要回退 RTL、事实模型或 Git 历史。

手动回滚只影响当前部署；下次 main 推送仍默认发布 Zensical。需要持续回滚时，将 `pages.yml` 的默认构建分支改回 Docsify，或 revert 迁移 PR（保留新增事实模型刷新）。工作流并发组为 `pages`，避免发布交叉；回滚前等待队列中旧的 Pages 运行结束。

故障回滚不等于重新验证硬件。构建失败不会进入 deploy 作业。Pages 继续保留上一个成功部署。

## 兼容范围

- `/dld/` 保持不变，资源均使用子路径内相对引用。
- 已知 `#/subsystems/<name>.md` 或不带 `.md` 的旧链接跳转到对应模块。
- 旧的 `?id=…` 节内锚点不映射，回到模块页面，由目录继续定位。
- 不迁移答辩问答入口，不把课程报告、原始资料或日志加入发布目录。
