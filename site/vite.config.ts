import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * GitHub Pages 部署口径（见 site/README.md §部署）：
 *
 *   · 仓库是 `tortrixx/dld`，用**项目级** Pages ⇒ 线上地址是
 *     `https://<user>.github.io/dld/`，所以站点的 base 是 `/dld/`。
 *
 *   · ⚠️ **dev / preview / build 三个命令共用同一个 base**，这是踩过坑之后改的：
 *     早先写成"只有 build 用 /dld/、dev 用 /"，结果 `vite preview` 也走
 *     `command === 'serve'` 分支拿到 base = '/'，于是它一边吐出一个引用
 *     `/dld/assets/...` 的 index.html、一边在 `/` 下找文件 ⇒
 *     **构建产物的 JS/CSS 全部 404，页面白屏**。
 *     现在三个命令都用 `/dld/`，好处不止是修 bug：本地 dev 走的就是
 *     线上那条子路径，这类"子路径 404"从此在开发阶段就会暴露，而不是等上线。
 *     本地地址：http://localhost:5173/dld/ （dev）· http://localhost:4173/dld/ （preview）
 *
 *   · 换成**用户级** Pages（`https://<user>.github.io/`）或改仓库名时不用动代码：
 *     `VITE_BASE=/ npm run build` 覆盖即可（GitHub Actions 就是靠这个环境变量传的，
 *     见 .github/workflows/pages.yml）。
 */
const base = process.env.VITE_BASE ?? '/dld/';

export default defineConfig({
  base,
  plugins: [react()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
