"""瞭望塔入口：抓取 → 存档 → LLM 摘要 → 渲染日报（早报/晚报）。

用法：
  python watchtower/main.py                     # 完整流程，时段按环境/默认早报
  python watchtower/main.py --slot evening      # 强制生成晚报
  python watchtower/main.py --no-llm            # 跳过 LLM，仅榜单
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from watchtower import config, fetchers, render, summarize  # noqa: E402
from watchtower.utils import REPO_ROOT, load_env, resolve_slot, today_cn  # noqa: E402


def enrich_background(entries_by_source, top_n=2):
    """每源 top N 条热点抓取网页 meta description 作为背景（并发、静默降级）。"""
    tasks = []
    for items in entries_by_source.values():
        for it in items[:top_n]:
            if not it.get("desc") and it.get("url"):
                tasks.append(it)
    if not tasks:
        return
    print(f"[info] 抓取 {len(tasks)} 条热点背景简介 ...")

    def work(it):
        it["desc"] = fetchers.fetch_page_desc(it["url"])

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(work, tasks))


def translate_english(entries_by_source):
    """对标记为英文的信源标题批量翻译，结果写回条目的 zh 字段。"""
    titles = []
    for src in config.SOURCES:
        if src.get("lang") == "en":
            for it in entries_by_source.get(src["name"], []):
                if it["title"] and not it.get("zh"):
                    titles.append(it["title"])
    if not titles:
        return
    print(f"[info] 翻译 {len(titles)} 条英文标题 ...")
    zh_map = summarize.translate_titles(titles)
    for items in entries_by_source.values():
        for it in items:
            if not it.get("zh") and it["title"] in zh_map:
                it["zh"] = zh_map[it["title"]]


def run(date_str, use_llm=True, slot="morning"):
    os.chdir(REPO_ROOT)

    results = []
    entries_by_source = {}
    llm_limit = config.LLM_LIMIT_PER_SOURCE
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
                # 附录用全量 limit 条；LLM 输入只取前 llm_limit 条（控成本）
                entries_by_source[src["name"]] = items[: min(llm_limit, len(items))]
        results.append({"source": src, "result": res})
        status = "OK" if res.get("ok") else "FAIL"
        print(f"[{status}] {src['name']}: {len(res.get('items', []))} 条"
              + ("" if res.get("ok") else f" -- {res.get('error', '')[:100]}"))

    ok_count = sum(1 for r in results if r["result"].get("ok"))

    # 背景浅读 + 英文标题翻译（可选增强，失败静默降级，不影响主流程）
    if entries_by_source:
        enrich_background(entries_by_source)
        translate_english(entries_by_source)

    # 原始数据存档（git 可追溯）
    (REPO_ROOT / "data").mkdir(exist_ok=True)
    raw_path = REPO_ROOT / "data" / f"{date_str}-{slot}.json"
    raw_path.write_text(
        json.dumps({"date": date_str, "slot": slot, "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # LLM 摘要（有内容且允许时）
    summary_md = None
    if use_llm and entries_by_source:
        print("[info] 调用 DeepSeek 生成报告 ...")
        summary_md = summarize.summarize(entries_by_source, date_str)

    # 渲染日报
    (REPO_ROOT / "reports").mkdir(exist_ok=True)
    report_path = REPO_ROOT / "reports" / f"{date_str}-{slot}.md"
    report_path.write_text(
        render.render_report(date_str, results, summary_md, slot=slot), encoding="utf-8"
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
    parser.add_argument("--slot", choices=["morning", "evening"], default=None,
                        help="时段（默认按触发环境推断，无则早报）")
    args = parser.parse_args()

    load_env()
    slot = resolve_slot(os.environ.get("SCHEDULE_EXPR"),
                        args.slot or os.environ.get("DISPATCH_SLOT"))
    sys.exit(run(today_cn(), use_llm=not args.no_llm, slot=slot))


if __name__ == "__main__":
    main()
