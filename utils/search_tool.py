"""
@Time    : 2026/3/10 19:00
@Author  : Zhang Hao yv
@File    : search_tool.py
@Desc    : 联网搜索工具封装。通过 Tavily 提供实时教育知识补盲，采用扁平化函数设计。
"""

from tavily import TavilyClient
from utils.config_loader import rag_config, logger

# --- 1. 模块级单例初始化 ---
_api_key = rag_config.get("TAVILY_API_KEY")
_client = TavilyClient(api_key=_api_key) if _api_key else None

if not _api_key:
    logger.error("❌ TAVILY_API_KEY 未在配置文件中设置，联网搜索将无法工作。")

# --- 2. 扁平化业务函数 ---

def search_education_tips(query: str, max_results: int = 3) -> list:
    """
    [核心函数] 执行针对教育场景优化的深度搜索。
    """
    if not _client:
        logger.warning(f"⚠️ 联网搜索功能未激活（缺失 API Key），跳过对问题 [{query}] 的检索")
        return []

    try:
        logger.info(f"🌐 正在发起 Tavily 联网搜索: {query}")
        search_result = _client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_raw_content=False
        )

        # 统一数据结构，确保与 retriever 的输出格式兼容
        results = [
            {"source": f"网络资源: {item['url']}", "content": item['content']}
            for item in search_result.get('results', [])
        ]

        logger.info(f"✅ 联网搜索完成，获取到 {len(results)} 条实时资料")
        return results

    except Exception as e:
        logger.error(f"❌ 联网搜索执行异常: {e}")
        return []

# --- 3. 模块独立测试 ---
if __name__ == "__main__":
    test_query = "赛文和塞罗的关系是什么"
    print("\n" + "="*50)
    print(f"🚀 启动扁平化搜索工具测试 | 问题: {test_query}")
    print("="*50 + "\n")

    # 直接调用函数进行测试
    results = search_education_tips(test_query, max_results=3)

    if results:
        for i, res in enumerate(results, 1):
            print(f"【结果 #{i}】")
            print(f"来源: {res['source']}")
            print(f"摘要: {res['content'][:150]}...")
            print("-" * 30)
        print(f"\n✨ 测试成功: 提取到 {len(results)} 条联网资料。")
    else:
        print("\n❌ 测试未返回结果，请检查 API Key 或网络环境。")