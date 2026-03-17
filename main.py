# -*- coding: utf-8 -*-
"""EverGrow 统一启动入口"""
import argparse
import sys


def run_api():
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)


def run_streamlit():
    import streamlit.web.cli as stcli
    sys.argv = ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501"]
    stcli.main()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EverGrow 亲子矛盾 RAG 智能问答平台")
    parser.add_argument(
        "mode",
        nargs="?",
        default="api",
        choices=["api", "streamlit"],
        help="api=启动后端(默认) | streamlit=启动前端",
    )
    args = parser.parse_args()
    if args.mode == "api":
        run_api()
    else:
        run_streamlit()