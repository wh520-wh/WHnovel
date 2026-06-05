# WHnovel

[![CI](https://github.com/wh520-wh/WHnovel/actions/workflows/ci.yml/badge.svg)](https://github.com/wh520-wh/WHnovel/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

AI 互动小说平台。选一个故事，跟 AI 聊着聊着就把剧情推进了。

## 功能

- 流式聊天：SSE 实时输出，支持打字指示器和自动滚动。
- 两段式输出：先推正文，再异步回写结构化尾部（状态、标签、高亮词）。
- 存档管理：创建、导出 JSON、导入、行内重命名。
- 剧情时间线：点击标签跳转到对应段落。
- AI 图片生成：封面和聊天插图共用一个可配置的图片模型。
- 管理面板：配模型、调提示词、管存档选项。
- 移动端适配：虚拟键盘偏移、44px 最小触控区、刘海屏安全区。

## 技术栈

前端 Vue 3 + Vite + TypeScript + Pinia + Element Plus，后端 FastAPI + SQLAlchemy + SQLite，通过 OpenAI 兼容 API 接入模型，SSE 流式传输。

## 快速开始

需要 Node.js 18+、Python 3.10+。

```bash
git clone https://github.com/wh520-wh/WHnovel.git
cd WHnovel
```

后端：

```bash
cd backend
pip install -r requirements.txt
python run.py
```

前端（另开终端）：

```bash
cd frontend
npm install
npm run dev
```

Windows 用户也可以直接跑 `start.ps1` 或 `start.bat`，`stop.bat` 停服务。

默认地址：前端 `http://localhost:5173`，后端 `http://localhost:8000`。

浏览器控制台输 `localStorage.admin_mode = '1'` 开管理员入口。

## 开发

后端用 Ruff 做 lint 和格式化，pytest 跑测试：

```bash
cd backend
pip install -r requirements-dev.txt
ruff check .          # lint
ruff format .         # 格式化
pytest                # 测试
```

前端用 ESLint + Prettier，vitest 跑测试：

```bash
cd frontend
npm ci
npm run lint          # ESLint
npm run format        # Prettier
npm run type-check    # TypeScript 类型检查
npm run test          # 测试
```

推 PR 时 CI 会自动跑这些检查。

## 目录结构

```
WHnovel/
├── backend/             FastAPI 服务
│   ├── app/             路由、模型、聊天流水线、加密
│   ├── tests/           pytest 测试
│   └── run.py           启动入口
├── frontend/            Vue 3 SPA
│   ├── src/
│   │   ├── stores/      Pinia 状态管理
│   │   ├── composables/ 可复用逻辑（流式聊天、滚动、图片等）
│   │   ├── views/       页面
│   │   └── api/         HTTP 和 SSE 封装
│   └── package.json
├── .github/workflows/   CI 配置
├── CONTRIBUTING.md      贡献指南
├── LICENSE
└── README.md
```

## 贡献

看 [CONTRIBUTING.md](CONTRIBUTING.md)。简单说：Issue 反馈问题，PR 提到 `main`，改后端逻辑记得带测试。

## 许可

MIT — 详见 [LICENSE](LICENSE)。
