# 复现与构建

项目面向 **Quartus II 9.1 / VHDL-93 / MAX II EPM1270T144C5**，实际 Quartus 编译与上板需要相应硬件及工具环境。本网站的构建不需要 Quartus。

## 仓库准备

```bash
git clone https://github.com/tortrixx/dld.git
cd dld
python scripts/check_env.py
python scripts/gen_project.py puzzle_top
```

## 仿真与综合

```bash
python scripts/sim.py run game_fsm
# Windows PowerShell 示例：按实际安装路径设置 QUARTUS_ROOT
# & "$env:QUARTUS_ROOT\quartus\bin\quartus_sh.exe" -t scripts/build.tcl
```

实际构建前先阅读仓库 [README](https://github.com/tortrixx/dld#readme) 及 [工程操作指南](https://github.com/tortrixx/dld/blob/main/HANDOFF.md)，确认当前命令、Quartus 路径和依赖。

!!! warning "修改 RTL 后"
    不要把历史资源、时序和断言结果当作新版本结果。应重新进行仿真、清洁构建、时序分析和必要的上板验证，并更新可追溯证据。

## 文档网站本地运行

```bash
python -m pip install 'zensical>=0.1,<0.3'
python zensical-site/scripts/prepare.py
cd zensical-site
zensical serve
# 生产构建：zensical build
```

文档站使用从现有源码文档复制生成的独立发布目录，不会写回 `rtl/`、`sim/`、`facts/` 或原始证据文档。
