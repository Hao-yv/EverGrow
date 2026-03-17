# -*- coding: utf-8 -*-
"""
EverGrow Streamlit 前端（流式输出）
运行：python main.py streamlit
"""
import json
from typing import Any

import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"
MAX_HISTORY_TURNS = 5


def get_headers():
    """请求头，含 token"""
    token = st.session_state.get("access_token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def init_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "user" not in st.session_state:
        st.session_state.user = None
    if "conv_page" not in st.session_state:
        st.session_state.conv_page = 1
    if "conv_page_size" not in st.session_state:
        st.session_state.conv_page_size = 10
    if "conv_keyword" not in st.session_state:
        st.session_state.conv_keyword = ""


def _extract_error(resp: requests.Response) -> str:
    """统一提取 API 错误信息"""
    try:
        data = resp.json()
        message = data.get("message")
        if isinstance(message, str) and message.strip():
            detail = data.get("detail")
            if isinstance(detail, str) and detail.strip():
                return f"{message.strip()}：{detail.strip()}"
            return message.strip()
        detail = data.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict):
                msg = first.get("msg")
                if msg:
                    return str(msg)
        err = data.get("error")
        if isinstance(err, str) and err.strip():
            return err.strip()
    except Exception:
        pass
    return f"请求失败（HTTP {resp.status_code}）"


def _request_json(method: str, path: str, **kwargs) -> tuple[Any | None, str | None]:
    """统一 JSON 请求入口"""
    try:
        resp = requests.request(
            method=method,
            url=f"{API_URL}{path}",
            timeout=kwargs.pop("timeout", 10),
            **kwargs,
        )
    except requests.exceptions.ConnectionError:
        return None, "无法连接后端，请先执行 `python main.py` 启动 API。"
    except requests.exceptions.Timeout:
        return None, "请求超时，请稍后重试。"
    except Exception as e:
        return None, f"请求异常：{e}"

    if resp.status_code != 200:
        return None, _extract_error(resp)
    try:
        return resp.json(), None
    except Exception:
        return None, "响应解析失败，请检查后端返回。"


def login(username: str, password: str):
    data, err = _request_json(
        "POST",
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    if data:
        st.session_state.access_token = data["access_token"]
        st.session_state.user = data["user"]
        return True, None
    return False, err or "登录失败"


def register(username: str, password: str, nickname: str = ""):
    data, err = _request_json(
        "POST",
        "/api/auth/register",
        json={"username": username, "password": password, "nickname": nickname or None},
    )
    if data:
        st.session_state.access_token = data["access_token"]
        st.session_state.user = data["user"]
        return True, None
    return False, err or "注册失败"


def logout():
    st.session_state.access_token = None
    st.session_state.user = None
    st.session_state.conversation_id = None
    st.session_state.messages = []
    st.session_state.conv_page = 1


def list_conversations(page: int, page_size: int, keyword: str = ""):
    data, err = _request_json(
        "GET",
        "/api/conversations",
        headers=get_headers(),
        params={"page": page, "page_size": page_size, "keyword": keyword},
    )
    if err:
        return {"items": [], "total": 0, "has_more": False}, err
    return data, None


def create_conversation():
    data, err = _request_json("POST", "/api/conversations", headers=get_headers(), json={})
    if err:
        return None, err
    return data.get("id"), None


def rename_conversation(conv_id: int, title: str):
    _, err = _request_json(
        "PATCH",
        f"/api/conversations/{conv_id}",
        headers=get_headers(),
        json={"title": title},
    )
    return err


def get_conversation(conv_id: int):
    data, err = _request_json("GET", f"/api/conversations/{conv_id}", headers=get_headers())
    if err:
        return None, err
    return data, None


def delete_conversation(conv_id: int):
    _, err = _request_json("DELETE", f"/api/conversations/{conv_id}", headers=get_headers())
    return err


st.set_page_config(page_title="EverGrow 亲子问答", page_icon="🌱", layout="centered")
init_session()

# 未登录：显示登录/注册
if not st.session_state.access_token:
    st.title("🌱 EverGrow 家庭教育顾问")
    tab1, tab2 = st.tabs(["登录", "注册"])
    with tab1:
        with st.form("login_form"):
            u = st.text_input("用户名")
            p = st.text_input("密码", type="password")
            if st.form_submit_button("登录"):
                if u and p:
                    ok, err = login(u, p)
                    if ok:
                        st.success("登录成功")
                        st.rerun()
                    else:
                        st.error(err or "登录失败")
                else:
                    st.warning("请输入用户名和密码")
    with tab2:
        with st.form("register_form"):
            ru = st.text_input("用户名（2-50 字符）")
            rp = st.text_input("密码（至少 6 位）", type="password")
            rn = st.text_input("昵称（可选）")
            if st.form_submit_button("注册"):
                if ru and rp:
                    ok, err = register(ru, rp, rn)
                    if ok:
                        st.success("注册成功")
                        st.rerun()
                    else:
                        st.error(err or "注册失败")
                else:
                    st.warning("请输入用户名和密码")
    st.caption("登录后可保存对话历史")
    st.stop()

# 已登录：主界面
st.title("🌱 EverGrow 家庭教育顾问")
with st.sidebar:
    st.write(f"👤 {st.session_state.user.get('nickname', st.session_state.user.get('username', ''))}")
    if st.button("退出登录"):
        logout()
        st.rerun()

    st.divider()
    st.subheader("年龄段筛选")
    stage = st.selectbox(
        "选择年龄段（可检索对应阶段的资料）",
        options=["", "幼儿期", "学龄前", "小学", "初中", "高中", "通用"],
        format_func=lambda x: "不限" if x == "" else x,
    )

    st.divider()
    st.subheader("会话历史")
    keyword = st.text_input("搜索会话标题", value=st.session_state.conv_keyword, placeholder="输入关键词")
    if keyword != st.session_state.conv_keyword:
        st.session_state.conv_keyword = keyword
        st.session_state.conv_page = 1

    page_size = st.selectbox("每页条数", [5, 10, 20, 50], index=[5, 10, 20, 50].index(st.session_state.conv_page_size))
    if page_size != st.session_state.conv_page_size:
        st.session_state.conv_page_size = page_size
        st.session_state.conv_page = 1

    conv_data, conv_err = list_conversations(
        st.session_state.conv_page,
        st.session_state.conv_page_size,
        st.session_state.conv_keyword,
    )
    if conv_err:
        st.warning(conv_err)
    convs = conv_data.get("items", [])
    total = conv_data.get("total", 0)
    has_more = conv_data.get("has_more", False)

    col_prev, col_page, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("◀", disabled=st.session_state.conv_page <= 1):
            st.session_state.conv_page -= 1
            st.rerun()
    with col_page:
        st.caption(f"第 {st.session_state.conv_page} 页 · 共 {total} 条")
    with col_next:
        if st.button("▶", disabled=not has_more):
            st.session_state.conv_page += 1
            st.rerun()

    options = ["➕ 新建对话"] + [f"{c['title'][:18]}…" if len(c["title"]) > 18 else c["title"] for c in convs]
    ids = [None] + [c["id"] for c in convs]

    default_idx = 0
    if st.session_state.conversation_id in ids:
        default_idx = ids.index(st.session_state.conversation_id)

    idx = st.selectbox("选择会话", range(len(options)), index=default_idx, format_func=lambda i: options[i], key="conv_sel")
    selected = ids[idx]
    if selected != st.session_state.conversation_id:
        st.session_state.conversation_id = selected
        st.session_state.messages = []
        if selected:
            data, err = get_conversation(selected)
            if err:
                st.error(err)
            elif data and data.get("messages"):
                st.session_state.messages = [
                    {"role": m["role"], "content": m["content"], "sources": []}
                    for m in data["messages"]
                ]
        st.rerun()

    if st.session_state.conversation_id and convs:
        with st.form("rename_conv_form"):
            new_title = st.text_input("重命名当前会话", value=next((c["title"] for c in convs if c["id"] == st.session_state.conversation_id), ""))
            if st.form_submit_button("保存标题"):
                err = rename_conversation(st.session_state.conversation_id, new_title)
                if err:
                    st.error(err)
                else:
                    st.success("会话标题已更新")
                    st.rerun()

        if st.button("🗑 删除当前会话"):
            err = delete_conversation(st.session_state.conversation_id)
            if err:
                st.error(err)
            else:
                st.session_state.conversation_id = None
                st.session_state.messages = []
                st.rerun()

# 消息展示
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("📎 引用来源"):
                for s in msg["sources"]:
                    st.write(f"- **{s.get('title', '未知')}**")

# 输入
if question := st.chat_input("请输入您的问题，例如：孩子写作业拖拉怎么办？"):
    # 若当前无会话且已登录，先创建会话
    conv_id = st.session_state.conversation_id
    if not conv_id:
        conv_id, create_err = create_conversation()
        if create_err:
            st.error(create_err)
            st.stop()
        if conv_id:
            st.session_state.conversation_id = conv_id

    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            prev = st.session_state.messages[:-1]
            history_msgs = prev[-(MAX_HISTORY_TURNS * 2) :] if prev else []
            payload = {"question": question}
            if stage:
                payload["stage"] = stage
            if history_msgs:
                payload["history"] = [{"role": m["role"], "content": m["content"]} for m in history_msgs]
            if conv_id:
                payload["conversation_id"] = conv_id

            r = requests.post(
                f"{API_URL}/api/routes",
                json=payload,
                headers=get_headers(),
                stream=True,
                timeout=60,
            )
            if r.status_code != 200:
                raise RuntimeError(_extract_error(r))

            sources = []
            chunks = []
            stream_error = None
            placeholder = st.empty()

            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "sources" in data:
                        sources = data["sources"]
                    elif "chunk" in data:
                        chunks.append(data["chunk"])
                        placeholder.markdown("".join(chunks))
                    elif "error" in data:
                        stream_error = data["error"]
                        placeholder.error(stream_error)
                        break
                    elif data.get("code") and data.get("message"):
                        detail = data.get("detail")
                        stream_error = data["message"] if not detail else f"{data['message']}：{detail}"
                        placeholder.error(stream_error)
                        break
                except json.JSONDecodeError:
                    pass

            answer = "".join(chunks)
            if stream_error and not answer:
                answer = f"请求失败：{stream_error}"
        except requests.exceptions.ConnectionError:
            answer = "无法连接 API，请确认已启动后端：`python main.py`"
            sources = []
            st.error(answer)
        except Exception as e:
            answer = f"请求出错：{e}"
            sources = []
            st.error(answer)

        if sources:
            with st.expander("📎 引用来源"):
                for s in sources:
                    st.write(f"- **{s.get('title', '未知')}** ({s.get('source_file', '')})")

    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
    st.rerun()
