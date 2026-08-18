"""Bark 推送（iOS 专属）：把当日 AI 报告全文推到 iPhone 系统通知栏。

用法：
  python watchtower/bark_push.py                # 推送当日报告
  python watchtower/bark_push.py --date 2026-08-19 --file reports/2026-08-19.md

需要环境变量（本地 .env / GitHub Secrets）：
  BARK_DEVICE_KEY    Bark App 首页的 KEY（api.day.app/KEY/ 中间那串）
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 支持直接 python watchtower/xxx.py

import requests

from watchtower.utils import REPO_ROOT, load_env, repo_report_url, today_cn

BARK_URL = "https://api.day.app/push"
BODY_MAX = 1200  # Bark 服务器请求体约 4KB 上限（约 1200 中文字），超限返回 413


def extract_ai_section(report_md):
    """抽取日报中的 AI 机会报告部分，并按节智能裁剪到 Bark 上限。

    优先保留「今日风向」「机会信号」等靠前的节；截断点落在小节边界，
    避免把表格切一半。
    """
    m = re.search(r"## AI 机会报告\s*\n(.*?)(?=\n## 附录)", report_md, re.S)
    if not m:
        return report_md[:BODY_MAX]
    body = m.group(1).strip()
    # 去掉「降级提示」这类以 > 开头的说明行
    body = "\n".join(l for l in body.splitlines() if not l.startswith(">"))
    if len(body) <= BODY_MAX:
        return body
    sections = re.split(r"(?=## )", body)
    out = []
    for sec in sections:
        if len("\n\n".join(out + [sec])) <= BODY_MAX - 40:
            out.append(sec)
        else:
            break
    text = "\n\n".join(out).strip()
    if out:
        text += "\n\n— 内容较多，点此通知查看完整报告 —"
    else:
        text = body[:BODY_MAX]
    return text


def push(date_str, report_md):
    key = os.environ.get("BARK_DEVICE_KEY", "")
    if not key:
        print("[bark] 未配置 BARK_DEVICE_KEY，跳过推送")
        return
    body = extract_ai_section(report_md)
    payload = {
        "title": f"瞭望塔日报 · {date_str}",
        "body": body,
        "device_key": key,
        "url": repo_report_url(date_str),
        "group": "瞭望塔",
        "icon": "https://github.githubassets.com/favicons/favicon.svg",
        "level": "active",
    }
    try:
        r = requests.post(BARK_URL, json=payload, timeout=20)
        j = r.json()
        if j.get("code") == 200:
            print(f"[bark] 推送成功（{len(body)} 字）")
        else:
            print(f"[bark] 推送失败: {j}")
    except Exception as e:  # noqa: BLE001
        status = getattr(r, "status_code", "?") if "r" in dir() else "?"
        text = getattr(r, "text", "")[:200] if "r" in dir() else ""
        print(f"[bark] 推送异常（不影响主流程）: {type(e).__name__}: {e} | HTTP {status} | {text}")


def main():
    parser = argparse.ArgumentParser(description="推送瞭望塔日报到 Bark (iOS)")
    parser.add_argument("--date", default=today_cn())
    parser.add_argument("--file", default=None)
    args = parser.parse_args()

    load_env()
    report_path = Path(args.file) if args.file else REPO_ROOT / "reports" / f"{args.date}.md"
    if not report_path.exists():
        print(f"[bark] 报告不存在: {report_path}", file=sys.stderr)
        sys.exit(1)
    push(args.date, report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
