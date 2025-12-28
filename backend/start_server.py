#!/usr/bin/env python
"""启动服务器脚本"""
import uvicorn
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    try:
        print("正在启动服务器...")
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

