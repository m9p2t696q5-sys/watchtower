"""瞭望塔入口：抓取 → 存档 → LLM 摘要 → 渲染日报。

用法：
  python watchtower/main.py            # 完整流程（有 key 则含 AI 报告）
  python watchtower/main.py --no-llm   # 跳过 LLM，仅榜单
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:  # 支持 python watchtower/main.py 直接运行
    sys.path.insert(0, str(REPO_ROOT))

from watchtower import config, fetchers, render, summarize  # noqa: E402


def load_env(path=".env"):
    """极简 .env 加载（不覆盖已存在的环境变量）。"""
    env_file = REPO_ROOT / path
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k:
            os.environ.setdefault(k, v)


def today_cn():
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")


def run(date_str, use_llm=True):
    os.chdir(REPO_ROOT)

    results = []
    entries_by_source = {}
    for src in config.SOURCES:
        fn = getattr(fetchers, src["fetcher"])
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": f"fetcher 崩溃: {type(e).__name__}: {e}"}
        if res.get("ok"):
            items = res["items"][: src["limit"]]
            res["items"] = items
            if items:
                entries_by_source[src["name"]] = items
        results.append({"source": src, "result": res})
        status = "OK" if res.get("ok") else "FAIL"
        print(f"[{status}] {src['name']}: {len(res.get('items', []))} 条"
              + ("" if res.get("ok") else f" -- {res.get('error', '')[:100]}"))

    ok_count = sum(1 for r in results if r["result"].get("ok"))

    # 原始数据存档（git 可追溯）
    (REPO_ROOT / "data").mkdir(exist_ok=True)
    raw_path = REPO_ROOT / "data" / f"{date_str}.json"
    raw_path.write_text(
        json.dumps({"date": date_str, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # LLM 摘要（有内容且允许时）
    summary_md = None
    if use_llm and entries_by_source:
        print("[info] 调用 DeepSeek 生成机会报告 ...")
        summary_md = summarize.summarize(entries_by_source, date_str)

    # 渲染日报
    (REPO_ROOT / "reports").mkdir(exist_ok=True)
    report_path = REPO_ROOT / "reports" / f"{date_str}.md"
    report_path.write_text(
        render.render_report(date_str, results, summary_md), encoding="utf-8"
    )
    print(f"[info] 报告已生成: {report_path.relative_to(REPO_ROOT)}")
    print(f"[info] 原始数据:   {raw_path.relative_to(REPO_ROOT)}")

    if ok_count == 0:
        print("[error] 所有信源均抓取失败，请检查网络或信源接口变动。", file=sys.stderr)
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description="瞭望塔日报生成器")
    parser.add_argument("--no-llm", action="store_true", help="跳过 LLM 摘要")
    args = parser.parse_args()

    load_env()
    sys.exit(run(today_cn(), use_llm=not args.no_llm))


if __name__ == "__main__":
    main()
