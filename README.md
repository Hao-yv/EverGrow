# EverGrow 亲子矛盾 RAG 智能问答平台

面向 0–18 岁亲子矛盾的 RAG 问答系统，本地检索不足时自动上网补充。

## 快速开始

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置
cp .env.example .env          # 填写 OPENAI_API_KEY、OPENAI_BASE_URL 等
cp config/database.yml.example config/database.yml   # 可选，仅 ingest 写库时需

# 3. 语料放入 data/raw/，执行导入
python scripts/ingest.py

# 4. 启动后端（默认）
python main.py

# 5. 新终端启动前端
python main.py streamlit
```

- 后端：http://127.0.0.1:8000  
- 前端：http://localhost:8501  
- API 文档：http://127.0.0.1:8000/docs  

## 环境要求

- Python >= 3.12
- .env 中配置 OPENAI 兼容 API（LLM + Embedding）
- 可选：TAVILY_API_KEY（本地无结果时上网检索）、MySQL（仅 ingest 写库时）

## 项目结构

```
EverGrow/
├── app/                 # 应用
│   ├── __init__.py     # FastAPI 入口
│   ├── api/            # API 路由
│   ├── rag/            # RAG：retriever、generator、web_search
│   └── core/           # 配置
├── config/             # chroma.yml、prompts.yml
├── data/raw/           # 语料（docx/doc/txt）
├── scripts/            # ingest、init_db
└── main.py             # 统一入口：python main.py [api|streamlit]
```

## 主要命令

| 命令 | 说明 |
|------|------|
| `python scripts/init_db.py` | 建表 + 初始 admin 用户（需 MySQL） |
| `python scripts/ingest.py` | 语料导入 Chroma |
| `python main.py` 或 `python main.py api` | 启动 FastAPI 后端 |
| `python main.py streamlit` | 启动前端 |
