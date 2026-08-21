"""周报：汇总本周早晚报，生成「一周热点速览 + 尾版简讯」。

用法：
  python watchtower/weekly.py               # 汇总本周（周一~周日），输出到本周日
  python watchtower/weekly.py --date 2026-08-24   # 指定本周日

产出：
  reports/{周日}-weekly.md    一周速览（LLM 生成，保留原文链接）+ 未精选热点简讯
  并推送 Bark 通知（防重，同周只推一次）。

需要环境变量：DEEPSEEK_API_KEY（可选，无则简讯版）、BARK_DEVICE_KEY（可选）
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from watchtower import summarize  # noqa: E402
from watchtower.bark_push import already_pushed, mark_pushed  # noqa: E402
from watchtower.utils import REPO_ROOT, load_env, repo_report_url, today_cn  # noqa: E402

WEEKLY_PROMPT = """你是社会观察员。下面是本周（{start} ~ {end}）瞭望塔每日早报/晚报的分析摘要，按日期排列。

请基于这些内容生成一周热点速览，输出以下部分（中文，Markdown，直接输出正文）：

## 本周核心趋势
3~5 条：本周最重要的趋势或变化，每条 2~3 句话说明来龙去脉。

## 连续出现的信号
列出在本周多天反复出现的热点或信号（可能不是噪声），说明大概出现了几天、含义是什么。没有就明说。

## 本周值得记住
挑出本周值得记住的人/品牌/事件（最多 8 条），每条一句话点评 + **必须使用文末「链接字典」中对应条目的完整链接**，格式 [标题](链接)。字典里找不到对应条目的，不得编造链接。
- 涉及讣告、灾难、悲剧的条目：简短致意或客观陈述，措辞尊重，不消费逝者。

## 下周看点
2~3 条：基于本周信号，下周可能值得观察的方向（用「可能 / 值得关注」措辞）。

## 本周社会观察小结
2~3 句：本周热榜整体反映的社会情绪或结构性变化。

硬性要求：只输出正文；严格基于材料，不编造；措辞有温度，避免冰冷功利化表述。
"""


def this_week_dates(day):
    """返回 day 所在周（周一~周日）的日期列表。"""
    monday = day - timedelta(days=day.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def extract_ai_section(report_md, max_len=700):
    m = re.search(r"## AI 机会报告\s*\n(.*?)(?=\n## 附录)", report_md, re.S)
    if not m:
        return ""
    body = m.group(1).strip()
    body = "\n".join(l for l in body.splitlines() if not l.startswith(">"))
    return body[:max_len]


def build_llm_input(dates):
    """把本周各份报告的 AI 部分 + 条目链接字典拼成 LLM 输入。"""
    parts = []
    for d in dates:
        for slot, max_len, label in (("morning", 700, "早报"), ("evening", 400, "晚报")):
            p = REPO_ROOT / "reports" / f"{d}-{slot}.md"
            if not p.exists():
                continue
            sec = extract_ai_section(p.read_text(encoding="utf-8"), max_len)
            if sec:
                parts.append(f"\n===== {d} {label} =====\n{sec}")
    # 链接字典：每源每天早晚各取 top1，供「本周值得记住」引用准确链接
    dict_lines = []
    for d in dates:
        for slot in ("morning", "evening"):
            p = REPO_ROOT / "data" / f"{d}-{slot}.json"
            if not p.exists():
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            for r in data.get("results", []):
                items = (r["result"].get("items") or [])[:1]
                for it in items:
                    title = (it.get("title") or "").replace("|", "｜")
                    url = it.get("url") or ""
                    if title and url:
                        dict_lines.append(f"- {title} | {url}")
    if dict_lines:
        parts.append("\n===== 链接字典（标题 | 链接）=====\n" + "\n".join(dict_lines))
    return "\n".join(parts)


def build_briefs(dates):
    """尾版简讯：从本周原始数据提取未进精选的热点（每源每天 top2 → 去重 → 每源前 8）。"""
    per_source = {}
    seen = set()
    for d in dates:
        for slot in ("morning", "evening"):
            p = REPO_ROOT / "data" / f"{d}-{slot}.json"
            if not p.exists():
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            for r in data.get("results", []):
                src = r["source"]["name"]
                per_source.setdefault(src, [])
                for it in (r["result"].get("items") or [])[:2]:
                    title = it.get("title") or ""
                    if not title or title in seen:
                        continue
                    seen.add(title)
                    per_source[src].append({
                        "title": title,
                        "url": it.get("url") or "",
                        "zh": it.get("zh"),
                    })
    return {src: lst[:8] for src, lst in per_source.items()}


def render_weekly(sunday, dates, llm_md, briefs):
    lines = [
        f"# 瞭望塔周报 · {dates[0]} ~ {sunday}",
        "",
        "> 由 GitHub Actions 每周日 21:00 自动生成 · 汇总本周早晚报 · 供复盘与存档",
        "",
    ]
    if llm_md:
        llm_md = re.sub(r"(?m)^### ", "## ", llm_md)  # 统一标题层级
        lines += [llm_md, ""]
    else:
        lines += ["> ⚠️ 本周未生成 AI 周报（未配置 DEEPSEEK_API_KEY 或调用失败），以下为热点简讯。", ""]
    lines += ["## 尾版简讯：本周未精选热点", ""]
    for src, lst in briefs.items():
        if not lst:
            continue
        lines.append(f"### {src}")
        for it in lst:
            title = it["title"]
            display = f"{it['zh']}（{title}）" if it.get("zh") else title
            url = it["url"]
            lines.append(f"- [{display}]({url})" if url else f"- {display}")
        lines.append("")
    return "\n".join(lines)


def push_bark(sunday, weekly_md):
    key = os.environ.get("BARK_DEVICE_KEY", "")
    if not key:
        print("[weekly] 未配置 BARK_DEVICE_KEY，跳过推送")
        return
    dedupe = f"{sunday}-weekly"
    if already_pushed(dedupe):
        print(f"[weekly] {dedupe} 已推送过，跳过")
        return
    body = weekly_md
    m = re.search(r"## 本周核心趋势\s*\n(.*?)(?=\n## 下周看点)", weekly_md, re.S)
    if m:
        body = "## 本周核心趋势\n" + m.group(1).strip()
    body = body[:1200]
    try:
        r = requests.post(
            "https://api.day.app/push",
            json={
                "title": f"瞭望塔周报 · {sunday}",
                "body": body,
                "device_key": key,
                "url": repo_report_url(sunday, slot="weekly"),
                "group": "瞭望塔",
                "level": "active",
            },
            timeout=20,
        )
        j = r.json()
        if j.get("code") == 200:
            print("[weekly] Bark 推送成功")
            mark_pushed(dedupe)
        else:
            print(f"[weekly] Bark 推送失败: {j}")
    except Exception as e:  # noqa: BLE001
        print(f"[weekly] Bark 推送异常（不影响主流程）: {type(e).__name__}: {e}")


def main():
    parser = argparse.ArgumentParser(description="瞭望塔周报生成器")
    parser.add_argument("--date", default=today_cn(), help="本周日日期 YYYY-MM-DD")
    parser.add_argument("--no-llm", action="store_true", help="跳过 LLM 周报，仅简讯")
    parser.add_argument("--no-push", action="store_true", help="跳过 Bark 推送")
    args = parser.parse_args()

    load_env()
    sunday = parse_date(args.date)
    dates = this_week_dates(sunday)
    print(f"[weekly] 汇总 {dates[0]} ~ {sunday} 共 {len(dates)} 天")

    # LLM 周报
    llm_md = None
    if not args.no_llm:
        llm_md = _llm_weekly(dates)

    # 尾版简讯
    briefs = build_briefs(dates)

    # 渲染输出
    (REPO_ROOT / "reports").mkdir(exist_ok=True)
    out = REPO_ROOT / "reports" / f"{sunday}-weekly.md"
    out.write_text(render_weekly(sunday, dates, llm_md, briefs), encoding="utf-8")
    print(f"[weekly] 周报已生成: {out.relative_to(REPO_ROOT)}")

    if not args.no_push:
        push_bark(str(sunday), out.read_text(encoding="utf-8"))


def _llm_weekly(dates):
    """通用 LLM 周报调用（复用 summarize 的请求逻辑）。"""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("[weekly] 未配置 DEEPSEEK_API_KEY，跳过 LLM 周报")
        return None
    llm_input = build_llm_input(dates)
    if not llm_input:
        print("[weekly] 本周无报告数据，仅输出简讯")
        return None
    prompt = WEEKLY_PROMPT.format(start=dates[0], end=dates[-1])
    try:
        r = requests.post(
            summarize.API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": summarize.MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": llm_input},
                ],
                "temperature": 0.3,
                "max_tokens": 2600,
            },
            timeout=180,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001
        print(f"[weekly] LLM 周报失败，降级为简讯版: {type(e).__name__}: {e}")
        return None


if __name__ == "__main__":
    main()
