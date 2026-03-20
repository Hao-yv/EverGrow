# RAG 检索与生成 - 代码提示

---

## 1. retriever.py 核心逻辑

### 加载 Chroma

```python
import chromadb
from chromadb.config import Settings

# 路径用 ROOT，与 ingest 一致
ROOT = Path(__file__).resolve().parent.parent.parent
persist_dir = ROOT / "data" / "chroma_db"

client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
collection = client.get_collection(name="agent")
```

### 获取 query 的 embedding（与 ingest 相同方式）

```python
from openai import OpenAI

def get_embedding(text: str, api_key: str, base_url: str, model: str) -> list[float]:
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding
```

### 检索

```python
# collection.query 返回结构示例：
# {
#   "ids": [[id1, id2, ...]],
#   "documents": [[doc1, doc2, ...]],
#   "metadatas": [[{"source_file": "...", "title": "..."}, ...]],
#   "distances": [[...]]
# }

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=chroma_cfg.get("k", 3),
    include=["documents", "metadatas", "ids"]
)

# 注意：query 返回的是二维列表，取 results["documents"][0]
docs = results["documents"][0] if results["documents"] else []
metas = results["metadatas"][0] if results["metadatas"] else []
ids = results["ids"][0] if results["ids"] else []
```

### search 完整实现

```python
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # 根据实际位置调整

def _get_embedding(text: str, api_key: str, base_url: str, model: str) -> list[float]:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding

def search(
    question: str,
    k: int | None = None,
    persist_dir: str | Path | None = None,
    collection_name: str = "agent",
) -> list[dict]:
    """
    检索与问题相关的文档。
    返回 [{"content": str, "title": str, "source_file": str, "chroma_doc_id": str}, ...]
    """
    import yaml
    from dotenv import load_dotenv
    import chromadb
    from chromadb.config import Settings

    load_dotenv(ROOT / ".env")
    chroma_cfg = yaml.safe_load(open(ROOT / "config" / "chroma.yml", encoding="utf-8"))

    persist_dir = persist_dir or ROOT / chroma_cfg.get("persist_directory", "data/chroma_db")
    collection_name = chroma_cfg.get("collection_name", "agent")
    k = k or chroma_cfg.get("k", 3)

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-ada-002")
    if not api_key or not base_url:
        raise ValueError("请配置 OPENAI_API_KEY 和 OPENAI_BASE_URL")

    # 向量化问题
    query_embedding = _get_embedding(question, api_key, base_url, embedding_model)

    # 检索
    client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
    collection = client.get_collection(name=collection_name)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "ids"],
    )

    docs = results["documents"][0] if results["documents"] else []
    metas = results["metadatas"][0] if results["metadatas"] else []
    ids = results["ids"][0] if results["ids"] else []

    return [
        {
            "content": doc,
            "title": (m or {}).get("title", "未知"),
            "source_file": (m or {}).get("source_file", ""),
            "chroma_doc_id": doc_id,
        }
        for doc, m, doc_id in zip(docs, metas, ids)
    ]
```

---

## 2. generator.py 核心逻辑

### 加载 prompts

```python
import yaml

with open(ROOT / "config" / "prompts.yml", encoding="utf-8") as f:
    prompts = yaml.safe_load(f)

system_prompt = prompts["system_prompt"]
qa_template = prompts["qa_template"]
no_result_prompt = prompts["no_result_prompt"]
```

### 拼接 context

```python
def _build_context(docs: list[dict]) -> str:
    parts = []
    for i, d in enumerate(docs, 1):
        title = d.get("title", "未知")
        content = d.get("content", "")
        parts.append(f"【{i}】《{title}》\n{content}")
    return "\n\n".join(parts)
```

### 调用 LLM

```python
from openai import OpenAI

client = OpenAI(api_key=api_key, base_url=base_url)
resp = client.chat.completions.create(
    model=os.getenv("OPENAI_MODEL_NAME", "gpt-5.2-chat"),
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": qa_template.format(context=context, question=question)}
    ],
)
answer = resp.choices[0].message.content
```

### 无检索结果时

```python
if not docs:
    # 可直接返回 no_result_prompt，或让 LLM 基于该提示生成
    return {"answer": no_result_prompt, "sources": []}
```

---

## 3. 串联调用（ask.py / qa.py）

```python
def ask(question: str) -> dict:
    retriever = Retriever()
    generator = Generator()

    docs = retriever.search(question)
    result = generator.generate(question=question, docs=docs)

    return {
        "answer": result["answer"],
        "sources": [{"title": d.get("title"), "source_file": d.get("source_file")} for d in docs]
    }
```

---

## 4. 配置加载参考（与 ingest 一致）

```python
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent  # 若在 app/rag/ 下
load_dotenv(ROOT / ".env")

# chroma
chroma_cfg = yaml.safe_load(open(ROOT / "config" / "chroma.yml"))

# env
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-ada-002")
llm_model = os.getenv("OPENAI_MODEL_NAME", "gpt-5.2-chat")
```

---

## 5. 注意事项

| 点 | 说明 |
|------|------|
| **embedding 模型** | 必须与 ingest 时一致（text-embedding-ada-002），否则向量不匹配 |
| **chroma 路径** | 与 chroma.yml 中 persist_directory 一致（data/chroma_db） |
| **collection 名** | chroma.yml 中 collection_name: agent |
| **context 长度** | 若 docs 总长超 4k token，可截断或只取前 N 篇 |
| **异常处理** | LLM/embedding 调用加 try-except，避免单次失败导致崩溃 |

---

## 6. 简单自测

```python
# 在 retriever 或 ask 中
if __name__ == "__main__":
    result = ask("孩子写作业拖拉怎么办？")
    print(result["answer"])
    print("引用:", result["sources"])
```
