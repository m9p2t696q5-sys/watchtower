"""把抓取结果 + LLM 摘要渲染成每日 Markdown 报告。"""

from watchtower.utils import slot_name


def _render_health_table(results):
    lines = ["| 信源 | 类别 | 状态 | 条数 / 说明 |", "| --- | --- | --- | --- |"]
    for r in results:
        src = r["source"]
        res = r["result"]
        if res.get("ok"):
            status = "✅"
            detail = f"{len(res['items'])} 条"
        else:
            status = "❌ 降级"
            detail = res.get("error", "未知错误")[:80]
        lines.append(f"| {src['name']} | {src['category']} | {status} | {detail} |")
    return "\n".join(lines)


def _render_appendix(results):
    lines = ["## 附录：各平台原始榜单", ""]
    for r in results:
        src = r["source"]
        res = r["result"]
        lines.append(f"### {src['name']}（{src['category']}）")
        if not res.get("ok"):
            lines.append(f"> 抓取失败：{res.get('error', '未知错误')}")
            lines.append("")
            continue
        items = res["items"]
        if not items:
            lines.append("> 无条目")
            lines.append("")
            continue
        lines.append("| 标题 | 热度 | 链接 |")
        lines.append("| --- | --- | --- |")
        for it in items:
            title = it["title"].replace("|", "｜")
            if it.get("zh"):
                title = f"{it['zh']}（{title}）"
            heat = (it.get("heat") or "").replace("|", "｜")
            url = it.get("url") or ""
            lines.append(f"| {title} | {heat} | [链接]({url}) |")
        lines.append("")
    return "\n".join(lines)


def render_report(date_str, results, summary_md, slot="morning"):
    ok_count = sum(1 for r in results if r["result"].get("ok"))
    lines = [
        f"# 瞭望塔{slot_name(slot)} · {date_str}",
        "",
        f"> 信源 {ok_count}/{len(results)} 正常 · 由 GitHub Actions 自动生成 · 供线下复盘使用",
        "",
        "## 信源状态",
        "",
        _render_health_table(results),
        "",
    ]
    if summary_md:
        lines += ["## AI 机会报告", "", summary_md, ""]
    else:
        lines += [
            "## AI 机会报告",
            "",
            "> ⚠️ 本次未生成 AI 摘要（未配置 DEEPSEEK_API_KEY 或调用失败），"
            "请直接阅读下方附录榜单，或手动补跑 `python watchtower/main.py`。",
            "",
        ]
    lines += [_render_appendix(results)]
    return "\n".join(lines)
