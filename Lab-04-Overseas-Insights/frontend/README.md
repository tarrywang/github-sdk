# Frontend (GitHub Pages · /overseas/)

这是一个极简静态页面：在浏览器端把 `report.md` 渲染成可阅读的 HTML。

## 本地预览（零安装）

仓库根目录执行：

- `python3 -m http.server 8000 --directory Lab-04-Overseas-Insights/frontend`
- 浏览器打开：`http://localhost:8000`

> 说明：直接双击打开 `index.html` 在部分浏览器会触发跨域限制，导致 `fetch(report.md)` 失败；用本地静态服务器即可。

## 使用方式

- 默认渲染：`report.md`（与 `index.html` 同目录）

## 部署到 GitHub Pages

本仓库使用单个 GitHub Pages 站点同时托管两个 Lab：

- 根路径 `/` → `Lab-01-Tech-Insights/frontend/`（EV 洞察，保持原有 URL 不变）
- 子路径 `/overseas/` → `Lab-04-Overseas-Insights/frontend/`（本出海洞察日报）

部署由 `.github/workflows/deploy-pages.yml` 完成：它把两个 `frontend/` 目录组装进一个 `_site/` 产物后上传。当
`Lab-04-Overseas-Insights/frontend/` 下的文件变更并推送到 `main` 时自动触发；Overseas Insight Workflow 每次运行后会把最新
`report.md` 写入该目录，从而触发 Pages 重新部署。

### 访问地址

- EV 洞察：`https://<你的用户名>.github.io/<仓库名>/`
- 出海洞察：`https://<你的用户名>.github.io/<仓库名>/overseas/`

## 故障排查

与 `tech-insight` 同源（gh-aw / `engine: copilot`），常见报错与修复见
`../../Lab-01-Tech-Insights/frontend/README.md`。改完工作流 frontmatter 后务必重新编译：
`gh aw compile .github/workflows/overseas-insight.md`。
