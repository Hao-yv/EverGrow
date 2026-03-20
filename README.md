# EverGrow 亲子矛盾 RAG 智能问答平台

面向 0-18 岁亲子教育问题的 RAG 问答系统，优先本地知识库检索，检索不足时可联网补充。

## 当前技术栈

- 后端：FastAPI + Chroma + MySQL
- 前端：Vue3 + Vite + Element Plus（项目目录：`../EverBloom`）
- 模型：OpenAI 兼容接口（聊天 + Embedding）

## 快速开始（推荐：EverBloom 前端）

### 1) 安装 uv（若尚未安装）

```bash
# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2) 同步后端依赖（uv）

```bash
uv sync
```

### 3) 配置文件

```bash
# Linux / macOS
cp .env.example .env
cp config/database.yml.example config/database.yml
```

```powershell
# Windows PowerShell
copy .env.example .env
copy config\database.yml.example config\database.yml
```

必填项：

- `.env`：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`JWT_SECRET_KEY`
- `config/database.yml`：`host`、`port`、`database`、`user`、`password`

> 注意：当前后端包含登录和会话能力，因此运行期也依赖 MySQL，不仅仅是 ingest 阶段。

### 4) 导入知识库（首次或更新语料时）

```bash
uv run python scripts/ingest.py
```

### 5) 启动后端

```bash
uv run python main.py
# 或
uv run python main.py api
```

后端地址：

- API 服务：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

### 6) 启动 EverBloom 前端（推荐）

在 `../EverBloom` 目录执行：

```bash
npm install
npm run dev
```

前端默认地址通常为：`http://127.0.0.1:5173`

如果需要修改后端地址，可在 EverBloom 中配置：

- `VITE_API_BASE_URL`（默认 `http://127.0.0.1:8000`）

## 兼容说明（旧入口）

`uv run python main.py streamlit` 为旧版前端入口，目前默认推荐使用 `EverBloom`。  
如需继续使用旧入口，请先确认 `app/streamlit_app.py` 是否存在并可运行。

## 项目结构

```text
EverGrow/
├── app/
│   ├── __init__.py              # FastAPI 入口、异常处理、/health
│   ├── api/
│   │   ├── auth.py              # 注册/登录/鉴权
│   │   ├── conversations.py     # 会话 CRUD 与历史消息
│   │   └── routes.py            # RAG 流式问答
│   ├── core/
│   │   ├── auth.py              # JWT + 密码哈希
│   │   ├── config.py            # 配置加载与启动校验
│   │   └── db.py                # 数据库连接管理
│   └── rag/
│       ├── retriever.py         # 混合检索 + 阈值 + 重排 + stage 回退
│       ├── generator.py         # 回答生成（支持流式）
│       └── web_search.py        # 联网补充检索
├── config/                      # chroma.yml / prompts.yml / database.yml
├── data/raw/                    # 待导入语料
├── docs/                        # 论文素材与设计文档
├── scripts/
│   ├── init_db.py               # 数据库初始化
│   └── ingest.py                # 语料导入向量库
├── main.py                      # 启动入口
└── README.md
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `uv sync` | 同步 Python 依赖（基于 `pyproject.toml` + `uv.lock`） |
| `uv run python scripts/init_db.py` | 初始化数据库表与初始数据 |
| `uv run python scripts/ingest.py` | 导入语料到 Chroma（并写入元数据） |
| `uv run python main.py` / `uv run python main.py api` | 启动后端 API |

## uv 项目管理建议

- 新增依赖：`uv add <package>`
- 新增开发依赖：`uv add --dev <package>`
- 删除依赖：`uv remove <package>`
- 更新锁文件：`uv lock`
- 临时运行命令：`uv run <command>`

> 团队协作建议：提交 `pyproject.toml` 与 `uv.lock`，确保环境一致性。
