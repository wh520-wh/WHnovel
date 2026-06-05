# WHnovel

[![CI](https://github.com/wh520-wh/WHnovel/actions/workflows/ci.yml/badge.svg)](https://github.com/wh520-wh/WHnovel/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个 AI 情景互动小说平台，提供流式聊天、结构化剧情状态与可配置的模型接入。

## 功能

- 基于 Server-Sent Events 的流式聊天，事件包括 `delta`、`text_end`、`tail`、`done`。
- 两段式流式输出：先发送正文文本，再以独立请求回写结构化尾部（状态、标签、高亮词等）。
- 存档管理：支持创建、导出、导入和行内重命名。
- 剧情时间线导航：可点击的剧情标签，跳转到对应段落。
- AI 图片生成：封面与聊天内插图共用一个可配置的图片模型。
- 管理面板：配置聊天与图片模型、提示词和单存档选项。
- 结构化输出治理：统一契约层（`ai_contracts.py`）定义 schema、校验模型 JSON、补默认值并返回统一错误码。
- 移动端输入栏：虚拟键盘偏移由专用 composable 统一处理。

## 技术栈

- 前端：Vue 3、Vite、TypeScript、Pinia、Element Plus。
- 后端：FastAPI、SQLAlchemy、SQLite、Pydantic。
- AI：通过 OpenAI 兼容的 HTTP API 接入聊天与图片模型。
- 流式：Server-Sent Events（SSE），配以单存档生成锁。

## 快速开始

前置条件：

- Node.js 18+ 与 npm。
- Python 3.10+。
- Windows 上需要 Git Bash（`start.ps1` 启动器会用到）或 PowerShell。

克隆并运行：

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

前端（在另一个终端中）：

```bash
cd frontend
npm install
npm run dev
```

或者在 Windows 上从仓库根目录直接使用启动脚本：

```bash
./start.ps1
# 或
start.bat
```

停止开发服务：

```bash
stop.bat
```

默认本地地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`

在浏览器控制台执行 `localStorage.admin_mode = '1'` 即可开启管理员入口。

## 目录结构

```
WHnovel/
├── backend/                FastAPI 服务、SQLAlchemy 模型、聊天流水线
│   ├── app/
│   ├── tests/
│   └── run.py
├── frontend/               Vue 3 SPA（Vite + TS）
│   ├── src/
│   │   ├── stores/
│   │   ├── composables/
│   │   ├── views/
│   │   └── api/
│   └── package.json
├── docs/                   设计笔记与 AI 输出治理文档
├── scripts/                仓库维护脚本
├── start.ps1, start.bat    本地开发启动器（后端 + 前端）
├── stop.bat                停止开发服务
├── LICENSE
├── README.md
├── README.zh.md
└── .github/                Issue / PR 模板与行为准则
```

## 贡献

通过 Issue 反馈 Bug 与想法，向 `main` 分支提交 PR。请遵循 `.github/PULL_REQUEST_TEMPLATE.md`，保持改动聚焦；当改动涉及后端逻辑或聊天流水线时请附上测试。

## 许可

MIT — 详见 [LICENSE](LICENSE)。
