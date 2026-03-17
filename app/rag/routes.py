from app.rag import search, generate


def ask(question: str) -> dict:
    """
    根据用户问题检索文档并生成回答。

    Args:
        question: 用户问题

    Returns:
        {"answer": str, "sources": [{"title": str, "source_file": str}, ...]}
    """
    docs = search(question)
    result = generate(question=question, docs=docs)
    return result


if __name__ == "__main__":
    # 测试：python -m app.rag.qa
    result = ask("孩子写作业拖拉怎么办？")
    print("回答:", result["answer"][:200], "...")
    print("引用:", result["sources"])
