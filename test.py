"""
@Time    : 2026/3/9 15:33
@Author  : Zhang Hao yv
@File    : test.py
@IDE     : PyCharm
"""
import requests
import json


def chat_with_memory(messages, session_id="stress-test-001"):
    url = "http://localhost:8000/api/chat/stream"

    for msg in messages:
        print(f"\n{"-" * 20}\n家长提问: {msg}")
        payload = {"message": msg, "session_id": session_id}
        full_reply = ""

        with requests.post(url, json=payload, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        data_str = decoded[6:]
                        if data_str == "[DONE]": break
                        data = json.loads(data_str)
                        if 'text' in data:
                            content = data['text']
                            full_reply += content
                            print(content, end="", flush=True)
        print(f"\n[系统已存盘，回复长度: {len(full_reply)}]")


if __name__ == "__main__":
    # 测试用例：考察指代消解和逻辑连贯性
    test_cases = [
        "我儿子今年 7 岁，最近寒假总是不肯写作业，一催他就哭。",
        "他哭的时候我该怎么安慰他？",  # 考察“他”指代 7 岁儿子
        "刚才你建议的第一点，如果他不配合，我该怎么办？"  # 考察对上一轮建议的记忆
    ]
    chat_with_memory(test_cases)