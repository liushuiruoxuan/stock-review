"""
启动器：优先 FastAPI（v2 全功能），依赖缺失时自动降级旧 server.py（零依赖兜底）。
容器 CMD 指向本文件。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT = os.environ.get("PORT", "8000")


def main():
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
    except ImportError:
        print("[run] 未安装 fastapi/uvicorn，降级为零依赖模式（python server.py）")
        import server
        server.main()
        return

    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(PORT),
                log_level="info")


if __name__ == "__main__":
    main()
