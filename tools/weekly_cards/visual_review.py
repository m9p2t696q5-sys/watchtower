"""视觉评审：用 DeepSeek 视觉模型评价卡片美观度，给出可执行的改进建议。

用法：
  python tools/weekly_cards/visual_review.py --dir tools/weekly_cards/output/2026-08-23 [--n 3]
"""

import argparse
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import requests  # noqa: E402

from watchtower.utils import load_env  # noqa: E402

API_URL = "https://api.deepseek.com/chat/completions"
VISION_MODEL = "deepseek-v4-flash-vision-exp"

PROMPT = """你是小红书知识卡片的设计评审。请评价这张卡片，重点看：
1. 视觉层次（标题/正文/装饰的主次是否清晰）
2. 配色与风格一致性
3. 排版密度与留白（手机屏上是否舒适）
4. 信息可读性（字号、对比度、行距）
5. 是否像"专业设计"，还是像"程序员随手排的"

输出严格按以下格式（不要其他内容）：
评分：X/10
优点：一句话
硬伤：一句话（最大的问题，若没有就说"无"）
建议1：一条最优先的具体改进（给出 CSS 层面的可执行描述，如"标题字号 118px 过大，建议 96px 并加字距"）
建议2：第二条具体改进
建议3：第三条具体改进
"""


def review_one(image_path, api_key):
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    payload = {
        "model": VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": PROMPT},
            ],
        }],
        "max_tokens": 500,
    }
    r = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--n", type=int, default=3, help="评审前 n 张（按文件名排序）")
    args = parser.parse_args()

    load_env()
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        print("[error] 未配置 DEEPSEEK_API_KEY", file=sys.stderr)
        sys.exit(1)

    pngs = sorted(Path(args.dir).glob("*.png"))[: args.n]
    for p in pngs:
        print(f"\n{'=' * 46}\n📄 {p.name}\n{'=' * 46}")
        try:
            review = review_one(p, key)
            print(review)
        except Exception as e:  # noqa: BLE001
            print(f"[error] 评审失败: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
