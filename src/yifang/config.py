"""模型配置 — 从 .env 文件读取，不在代码中存放任何敏感值"""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_REQUIRED = ["OPENAI_BASE_URL", "OPENAI_API_KEY", "MODEL"]
_missing = [k for k in _REQUIRED if not os.getenv(k)]
if _missing:
    print(f"缺少环境变量: {', '.join(_missing)}", file=sys.stderr)
    print("请复制 .env.example 为 .env 并填写配置", file=sys.stderr)
    sys.exit(1)

client = OpenAI(
    base_url=os.environ["OPENAI_BASE_URL"],
    api_key=os.environ["OPENAI_API_KEY"],
)
MODEL = os.environ["MODEL"]
