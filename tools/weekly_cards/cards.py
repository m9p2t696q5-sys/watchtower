"""瞭望塔周报卡片生成器 v2 —— 周报 Markdown → 小红书知识卡片 PNG。

架构（与 v1 的本质区别）：
  内容解析（markdown → 结构化数据）→ 布局函数（数据 → 独立 HTML）→ 逐卡独立渲染
  · 比例/配色/字号全部集中在 RATIOS / THEME / FONT 三个配置区，改比例 = 传一个参数
  · 每张卡片独立渲染（set_content + 精确 viewport），从架构上消灭"截图截不全"问题
  · 纯文字卡片，无外部图片依赖，set_content 渲染无 file:// 拦截问题

用法：
  python tools/weekly_cards/cards.py                                   # 渲染最近一份周报，3:4
  python tools/weekly_cards/cards.py --report reports/2026-08-23-weekly.md
  python tools/weekly_cards/cards.py --ratio 9:15 --watermark "@瞭望塔"
  python tools/weekly_cards/cards.py --dry-run                          # 只解析不渲染
"""

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# --------------------------------------------------------------------------
# 配置区：所有魔法数字都在这
# --------------------------------------------------------------------------

RATIOS = {
    "3:4":  {"w": 1080, "h": 1440, "label": "3:4"},
    "9:15": {"w": 1080, "h": 1800, "label": "9:15"},
}

THEME = {
    # 深夜情报台：深蓝底 + 琥珀金强调
    "bg": "#0b1220",
    "card": "#111a2c",
    "card2": "#16233c",
    "accent": "#f5b942",
    "accent_soft": "rgba(245,185,66,0.14)",
    "text": "#e9eef8",
    "sub": "#a9bad6",
    "line": "#24334f",
    "badge_bg": "rgba(245,185,66,0.15)",
    "badge_text": "#ffd98a",
}

FONT = '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif'

WATERMARK_DEFAULT = "瞭望塔周报 · AI 全网热点观察"

CARD_TYPES = ("cover", "trends", "signals", "remembers", "outlook")

# --------------------------------------------------------------------------
# 周报 Markdown 解析
# --------------------------------------------------------------------------


def _cut_section(md, name):
    """提取 '## name' 到下一个 '## ' 之间的内容。"""
    m = re.search(rf"^##\s*{re.escape(name)}\s*\n(.*?)(?=^##\s|\Z)", md, re.S | re.M)
    return m.group(1).strip() if m else ""


def _split_bold_items(text):
    """解析「**标题** + 段落」形式的条目，返回 [(title, body)]。"""
    items = []
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^\*\*([^*]+)\*\*\s*[:：]?\s*(.*)$", line)
        if m:
            title = re.sub(r"^\d+[.、]\s*", "", m.group(1)).strip()
            cur = {"title": title, "body": m.group(2).strip()}
            items.append(cur)
        elif cur is not None:
            cur["body"] = (cur["body"] + " " + line).strip()
    # 无 ** 结构时整段作为一条
    if not items and text.strip():
        items.append({"title": "", "body": text.strip()})
    return items


def _split_list_items(text):
    """解析 '- xxx' 列表，返回 [str]。"""
    return [re.sub(r"^\s*[-•]\s*", "", l).strip() for l in text.splitlines()
            if re.match(r"^\s*[-•]\s+", l)]


def parse_weekly(md):
    """周报 markdown → 结构化数据。"""
    trends = _split_bold_items(_cut_section(md, "本周核心趋势"))
    signals = _split_bold_items(_cut_section(md, "连续出现的信号"))
    outlooks = _split_list_items(_cut_section(md, "下周看点"))
    summary = _cut_section(md, "本周社会观察小结").strip()

    remembers = []
    for line in _cut_section(md, "本周值得记住").splitlines():
        m = re.match(r"^\s*[-•]\s*\[([^\]]+)\]\(([^)]+)\)\s*(?:——|—|-)?\s*(.*)$", line)
        if m:
            remembers.append({"title": m.group(1).strip(),
                              "url": m.group(2).strip(),
                              "note": m.group(3).strip()})
    return {"trends": trends, "signals": signals, "remembers": remembers,
            "outlooks": outlooks, "summary": summary}


# --------------------------------------------------------------------------
# 布局函数：数据 → HTML 卡片
# --------------------------------------------------------------------------


def _css(ratio, watermark):
    w, h = ratio["w"], ratio["h"]
    pad = int(w * 0.085)
    return f"""
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
      width:{w}px; height:{h}px; overflow:hidden;
      background:{THEME['bg']}; color:{THEME['text']};
      font-family:{FONT};
      display:flex; flex-direction:column;
    }}
    .wrap {{ width:100%; height:100%; padding:{int(w*0.095)}px; display:flex; flex-direction:column; }}
    .header {{ display:flex; justify-content:space-between; align-items:baseline;
      border-bottom:2px solid {THEME['line']}; padding-bottom:18px; margin-bottom:34px; }}
    .header .kicker {{ color:{THEME['accent']}; font-size:26px; letter-spacing:4px; font-weight:600; }}
    .header .page {{ color:{THEME['sub']}; font-size:22px; }}
    .footer {{ margin-top:auto; display:flex; justify-content:space-between;
      color:{THEME['sub']}; font-size:19px; padding-top:18px;
      border-top:1px solid {THEME['line']}; }}
    .watermark {{ opacity:.55; }}
    h1.cover-title {{ line-height:1.08; font-weight:800; margin:26px 0 10px; }}
    .cover-title .big {{ font-size:116px; letter-spacing:2px; }}
    .cover-title .small {{ font-size:86px; color:{THEME['accent']}; letter-spacing:10px; }}
    .date-range {{ color:{THEME['accent']}; font-size:30px; letter-spacing:2px; font-weight:600; }}
    .cover-sub {{ color:{THEME['sub']}; font-size:27px; margin-top:14px; line-height:1.7; }}
    .chips {{ display:flex; flex-wrap:wrap; gap:18px; margin-top:36px; }}
    .chip {{ background:rgba(255,255,255,0.11); color:{THEME['badge_text']};
      border:1px solid rgba(245,200,60,0.6); border-radius:999px;
      padding:14px 32px; font-size:24px; font-weight:600; line-height:1.5;
      word-break:break-all; max-width:100%; }}
    .toc {{ margin-top:48px; background:{THEME['card']}; border:1px solid {THEME['line']};
      border-radius:22px; padding:38px 46px; }}
    .toc .toc-label {{ color:{THEME['sub']}; font-size:24px; font-weight:600;
      letter-spacing:4px; margin-bottom:6px; }}
    .toc .row {{ display:flex; justify-content:space-between; align-items:center;
      font-size:27px; color:{THEME['sub']}; padding:15px 0; line-height:1.8;
      border-bottom:1px dashed {THEME['line']}; }}
    .toc .row:last-child {{ border-bottom:none; }}
    .toc .row b {{ color:{THEME['text']}; font-weight:700; font-size:44px; }}
    .item {{ margin-bottom:46px; }}
    .item .idx {{ display:inline-block; color:{THEME['accent']}; font-size:44px;
      font-weight:800; margin-right:16px; }}
    .item .t {{ font-size:34px; font-weight:700; line-height:1.55; }}
    .item .b {{ color:{THEME['sub']}; font-size:28px; line-height:1.9; margin-top:14px; }}
    .sig {{ background:{THEME['card']}; border:1px solid {THEME['line']};
      border-radius:20px; padding:32px 40px; margin-bottom:32px; }}
    .sig .badge {{ display:inline-block; background:{THEME['badge_bg']};
      color:{THEME['badge_text']}; border-radius:999px; padding:7px 24px;
      font-size:22px; font-weight:700; margin-bottom:16px; }}
    .sig .t {{ font-size:30px; font-weight:700; line-height:1.55; }}
    .sig .b {{ color:{THEME['sub']}; font-size:27px; line-height:1.9; margin-top:14px; }}
    .rem {{ margin-bottom:36px; }}
    .rem .t {{ font-size:31px; font-weight:700; line-height:1.55; }}
    .rem .n {{ color:{THEME['sub']}; font-size:26px; line-height:1.85; margin-top:12px; }}
    .rem .src {{ color:{THEME['accent']}; font-size:21px; margin-top:10px; }}
    .out {{ background:{THEME['card']}; border-left:6px solid {THEME['accent']};
      border-radius:0 18px 18px 0; padding:30px 38px; margin-bottom:28px; }}
    .out .t {{ font-size:29px; font-weight:700; margin-bottom:12px; }}
    .out .b {{ color:{THEME['sub']}; font-size:27px; line-height:1.9; }}
    .summ {{ background:{THEME['card2']}; border-radius:20px; padding:34px 40px; }}
    .summ .label {{ color:{THEME['accent']}; font-size:23px; font-weight:700;
      letter-spacing:3px; margin-bottom:14px; }}
    .summ p {{ color:{THEME['text']}; font-size:26px; line-height:1.95; }}
    """


def _page_html(inner, kicker, page_no, total, ratio, watermark):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>{_css(ratio, watermark)}</style></head>
<body><div class="wrap">
<div class="header"><span class="kicker">{kicker}</span><span class="page">{page_no} / {total}</span></div>
{inner}
<div class="footer"><span>瞭望塔 · AI 每日观察</span><span class="watermark">{watermark}</span></div>
</div></body></html>"""


def _truncate(s, n):
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def build_cards(data, monday, sunday, ratio_key, watermark):
    """数据 → 卡片列表 [(文件名, html)]。"""
    ratio = RATIOS[ratio_key]
    trends, signals, remembers, outlooks, summary = (
        data["trends"], data["signals"], data["remembers"],
        data["outlooks"], data["summary"])

    # 分页
    trend_pages = [trends[i:i + 3] for i in range(0, max(len(trends), 1), 3)] or [[]]
    sig_pages = [signals[i:i + 4] for i in range(0, max(len(signals), 1), 4)] or [[]]
    rem_pages = [remembers[i:i + 4] for i in range(0, max(len(remembers), 1), 4)] or [[]]

    cards = []

    # 1. 封面
    keywords = [re.sub(r"[「」《》]", "", t["title"]).strip() for t in trends[:2] if t.get("title")]
    try:
        week_no = date.fromisoformat(monday).isocalendar()[1]
    except Exception:  # noqa: BLE001
        week_no = "?"
    toc_rows = []
    if trends:
        toc_rows.append(("本周核心趋势", f"{len(trends)} 条"))
    if signals:
        toc_rows.append(("连续出现的信号", f"{len(signals)} 个"))
    if remembers:
        toc_rows.append(("值得记住的事件", f"{len(remembers)} 件"))
    if outlooks:
        toc_rows.append(("下周看点", f"{len(outlooks)} 条"))
    toc = "".join(f'<div class="row"><span>{k}</span><b>{v}</b></div>' for k, v in toc_rows)
    inner = f"""
<h1 class="cover-title"><span class="big">瞭望塔</span><br><span class="small">周 报</span></h1>
<div class="date-range">{monday} — {sunday}</div>
<div class="cover-sub">全网热榜 · AI 趋势分析 · 一周速览<br>深蓝情报台 · 第 {week_no} 周</div>
<div class="chips">{''.join(f'<span class="chip">{k}</span>' for k in keywords)}</div>
<div class="toc"><div class="toc-label">本期看点</div>{toc}</div>"""
    cards.append(("01_封面", inner))

    # 2. 核心趋势
    for pi, page in enumerate(trend_pages):
        rows = ""
        for i, t in enumerate(page):
            title = t["title"] or "本周趋势"
            rows += (f'<div class="item"><span class="idx">{pi * 3 + i + 1:02d}</span>'
                     f'<span class="t">{title}</span>'
                     f'<div class="b">{_truncate(t["body"], 220)}</div></div>')
        cards.append((f"02_核心趋势_{pi + 1}", rows))

    # 3. 连续信号
    for pi, page in enumerate(sig_pages):
        rows = ""
        for t in page:
            title = t["title"] or "信号"
            m = re.search(r"连续\s*(\d+)\s*天", title) or re.search(r"出现\s*(\d+)\s*天", title)
            days = f"出现 {m.group(1)} 天" if m else "反复出现"
            rows += (f'<div class="sig"><span class="badge">{days}</span>'
                     f'<div class="t">{title}</div>'
                     f'<div class="b">{_truncate(t["body"], 200)}</div></div>')
        cards.append((f"03_连续信号_{pi + 1}", rows))

    # 4. 值得记住
    for pi, page in enumerate(rem_pages):
        rows = ""
        for r in page:
            src = re.sub(r"https?://(www\.)?", "", r["url"]).split("/")[0]
            rows += (f'<div class="rem"><div class="t">{_truncate(r["title"], 60)}</div>'
                     f'<div class="n">{_truncate(r["note"], 130)}</div>'
                     f'<div class="src">{src}</div></div>')
        cards.append((f"04_值得记住_{pi + 1}", rows))

    # 5. 下周看点 + 社会观察小结
    outs = ""
    for o in outlooks:
        m = re.match(r"^\*{1,2}([^*]+?)\*{1,2}\s*[:：]?\s*(.*)$", o)
        if m:
            outs += (f'<div class="out"><div class="t">{m.group(1).strip()}</div>'
                     f'<div class="b">{_truncate(m.group(2).strip(), 150)}</div></div>')
        else:
            outs += f'<div class="out"><div class="t">看点</div><div class="b">{_truncate(o, 150)}</div></div>'
    summ = ""
    if summary:
        summ = (f'<div class="summ"><div class="label">社会观察小结</div>'
                f'<p>{_truncate(summary, 260)}</p></div>')
    cards.append((f"05_看点与小结_1", outs + summ))

    total = len(cards)
    out = []
    for i, (name, inner) in enumerate(cards):
        kicker_map = {"01": "瞭望塔周报", "02": "本周核心趋势", "03": "连续出现的信号",
                      "04": "值得记住", "05": "下周看点"}
        prefix = name.split("_")[0]
        kicker = kicker_map.get(prefix, "瞭望塔周报")
        out.append((f"{name}.png",
                    _page_html(inner, kicker, i + 1, total, ratio, watermark)))
    return out


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------


def render(cards, ratio, out_dir):
    w, h = ratio["w"], ratio["h"]
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, html in cards:
            page = browser.new_page(
                viewport={"width": w, "height": h}, device_scale_factor=2)
            page.set_content(html, wait_until="load")
            path = out_dir / name
            page.screenshot(path=str(path),
                            clip={"x": 0, "y": 0, "width": w, "height": h})
            page.close()
            kb = path.stat().st_size // 1024
            print(f"[OK] {name} ({kb} KB)")
        browser.close()


# --------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="瞭望塔周报卡片生成器 v2")
    parser.add_argument("--report", default=None, help="周报路径（默认取 reports 里最新 weekly）")
    parser.add_argument("--ratio", choices=list(RATIOS), default="3:4")
    parser.add_argument("--watermark", default=WATERMARK_DEFAULT)
    parser.add_argument("--out", default=None, help="输出目录（默认 output/{周日}/）")
    parser.add_argument("--dry-run", action="store_true", help="只解析打印，不渲染")
    args = parser.parse_args()

    if args.report:
        report_path = Path(args.report)
    else:
        weeklys = sorted((REPO_ROOT / "reports").glob("*-weekly.md"))
        if not weeklys:
            print("[error] 未找到周报，先用 weekly.py 生成。", file=sys.stderr)
            sys.exit(1)
        report_path = weeklys[-1]
    md = report_path.read_text(encoding="utf-8")
    sunday = report_path.stem.replace("-weekly", "")

    data = parse_weekly(md)
    print(f"[info] 解析 {report_path}:")
    print(f"  趋势 {len(data['trends'])} 条 / 信号 {len(data['signals'])} 个 / "
          f"值得记住 {len(data['remembers'])} 件 / 看点 {len(data['outlooks'])} 条 / "
          f"小结 {'有' if data['summary'] else '无'}")
    if args.dry_run:
        sys.exit(0)

    # 从报告头部取日期区间（"瞭望塔周报 · 2026-08-17 ~ 2026-08-23"）
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", md)
    if m:
        monday, sunday = m.group(1), m.group(2)
    else:
        try:
            monday = str(date.fromisoformat(sunday) - timedelta(days=6))
        except Exception:  # noqa: BLE001
            monday = sunday

    cards = build_cards(data, monday, sunday, args.ratio, args.watermark)
    out_dir = Path(args.out) if args.out else HERE / "output" / sunday
    print(f"[info] 渲染 {len(cards)} 张 {RATIOS[args.ratio]['label']} 卡片 -> {out_dir}")
    render(cards, RATIOS[args.ratio], out_dir)
    print(f"[info] 完成")


if __name__ == "__main__":
    main()
