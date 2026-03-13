"""
对比 openai 库 vs dashscope 官方 SDK 调用 qwen 的耗时。
"""
import os
import time
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
MODEL = os.getenv("DASHSCOPE_MODEL_NAME", "qwen-turbo")
PROMPT = "你好，请用一句话介绍你自己"


def test_openai():
    """使用 openai 库（兼容接口）"""
    from openai import OpenAI
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    start = time.perf_counter()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT}],
        max_tokens=100,
    )
    elapsed = time.perf_counter() - start
    text = resp.choices[0].message.content
    return elapsed, text


def test_dashscope():
    """使用 dashscope 官方 SDK，qwen-turbo 为纯文本模型用 Generation.call"""
    import dashscope
    from http import HTTPStatus
    saved = os.environ.pop("DASHSCOPE_BASE_URL", None)
    try:
        dashscope.api_key = API_KEY
        start = time.perf_counter()
        resp = dashscope.Generation.call(
            model="qwen-turbo",
            messages=[{"role": "user", "content": PROMPT}],
            result_format="message",
            max_tokens=100,
        )
        elapsed = time.perf_counter() - start
    finally:
        if saved is not None:
            os.environ["DASHSCOPE_BASE_URL"] = saved
    if resp.status_code != HTTPStatus.OK:
        raise Exception(f"{resp.code}: {resp.message}")
    text = resp.output.choices[0].message.content
    return elapsed, text


def main():
    if not API_KEY:
        print("❌ 未配置 DASHSCOPE_API_KEY")
        return

    print("=" * 50)
    print("qwen 连接耗时对比")
    print("=" * 50)
    print(f"model: {MODEL}\n")

    print("\n2. dashscope 官方 SDK")
    try:
        t, text = test_dashscope()
        print(f"   耗时: {t:.2f}s")
        print(f"   回复: {text[:80]}...")
    except Exception as e:
        print(f"   ❌ {e}")

    print("1. openai 库（兼容接口）")
    try:
        t, text = test_openai()
        print(f"   耗时: {t:.2f}s")
        print(f"   回复: {text[:80]}...")
    except Exception as e:
        print(f"   ❌ {e}")



    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
