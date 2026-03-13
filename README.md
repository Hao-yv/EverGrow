# EverGrow（长青策）

面向家长的家庭教育智能咨询系统，基于 RAG 提供青春期心理、亲子沟通、行为干预等方向的咨询建议。

## 技术栈

| 类别     | 技术                    |
|----------|-------------------------|
| 框架     | FastAPI                 |
| 数据库   | MySQL + ChromaDB        |
| LLM      | OpenAI 兼容 API（支持 Qwen / DashScope） |
| 检索     | ChromaDB 向量库 + Tavily 联网搜索 |
| 鉴权     | JWT + bcrypt            |

## 项目结构

```
EverGrow/
├── main.py                 # FastAPI 入口
├── config/
│   ├── database.yml        # MySQL 配置
│   ├── chroma.yml          # 向量库配置
│   └── prompts.yml         # 提示词、RAG 约束、安全边界
├── core/
│   ├── auth/
│   │   └── auther.py       # 注册、登录、Token 解析
│   └── manager/
│       └── database.py     # 会话、消息、用户 CRUD
├── utils/
│   ├── config_loader.py    # 配置加载
│   ├── logger_handler.py   # 日志
│   ├── path_tool.py        # 路径工具
│   └── search_tool.py      # Tavily 联网搜索
├── scripts/
│   └── init_db.py          # 数据库初始化
├── data/
│   ├── raw/                # 原始知识库文档
│   └── vector_db/          # ChromaDB 持久化
└── logs/                   # 日志目录
```

## 快速开始

### 1. 环境要求

- Python >= 3.12
- MySQL 服务

### 2. 安装依赖

```bash
pip install -e .
# 或
uv sync
```

### 3. 配置

- 复制 `.env.example` 为 `.env`，填写 API Key 等
- 修改 `config/database.yml` 中的数据库连接信息

### 4. 初始化数据库

```bash
python scripts/init_db.py
```

将创建 `users`、`sessions`、`messages` 表，并插入默认账户 `admin` / `admin`。

### 5. 启动服务

```bash
python main.py
# 或
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

服务地址：<http://127.0.0.1:8000>  
API 文档：<http://127.0.0.1:8000/docs>

## API 接口

### 鉴权

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/register | 注册 |
| POST | /api/auth/login | 登录 |
| GET | /api/auth/profile | 获取当前用户（需 Bearer token） |

## 环境变量示例

```env
# LLM
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL_NAME=gpt-4-turbo

#  embeddings
EMBEDDING_MODEL_NAME=text-embedding-ada-002

# Tavily
TAVILY_API_KEY=

# JWT
JWT_SECRET=your-secret-key
```

## 开发说明

- 日志输出到 `logs/agent_YYYYMMDD.log`
- 鉴权支持游客（无 token 时 `user_id` 为 `None`）
- 提示词与安全规则见 `config/prompts.yml`

## 后续规划

### 短期（核心功能）

1. **core.engine.generator**  
   - RAG 检索（ChromaDB 向量检索 + Tavily 联网搜索）
   - 基于 prompts.yml 构建 system/user prompt
   - 流式调用 LLM 生成回答
   - 与 database、refiner 串联

2. **core.engine.refiner**  
   - 将详细回答精炼为 2–3 条黄金建议
   - 调用 LLM 二次推理

3. **main.py 扩展**  
   - POST /api/chat/detailed：流式详细回答（SSE）
   - POST /api/chat/golden：同步返回黄金建议
   - GET /api/chat/sessions：会话列表
   - GET /api/chat/history/{session_id}：历史消息
   - DELETE /api/chat/sessions/{session_id}：删除会话

4. **ChromaDB 检索层**  
   - 封装向量检索逻辑
   - 与 search_tool 结果格式统一

### 中期（增强）

- 文档入库脚本：将 `data/raw` 文档切块并写入 ChromaDB
- 连接池：database 连接池优化
- 异常与超时：完善 generator 中的错误处理与超时控制

### 长期（可选）

- 用户反馈表（feedbacks）
- 审计日志（audit_logs）
- 知识库元数据管理（documents 表）

## License

（根据需要补充）
