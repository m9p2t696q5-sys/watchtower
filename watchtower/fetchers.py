"""各平台热榜抓取器。

约定：每个 fetcher 返回
  {"ok": True,  "items": [{"title", "url", "heat", "extra"}, ...]}
  {"ok": False, "error": "..."}

任何单一信源失败都不影响整体流程，由上层做降级处理。
"""

import html as html_mod
import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests

TIMEOUT = (10, 20)  # (连接超时, 读取超时)，单位秒
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA}


def _get(url, params=None, headers=None):
    return requests.get(
        url, params=params, headers={**HEADERS, **(headers or {})}, timeout=TIMEOUT
    )


def _ok(items):
    return {"ok": True, "items": items}


def _fail(exc):
    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _quote(s):
    return urllib.parse.quote(s or "")


def fetch_page_desc(url, max_len=200):
    """抓取网页的 meta description 作为热点背景简介（供 LLM 理解事件）。

    超时 / 非 200 / 无 description 一律返回空字符串，绝不抛出异常——
    背景是锦上添花，绝不允许它拖垮主流程。
    """
    if not url or not url.startswith("http"):
        return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=(5, 8))
        if r.status_code != 200:
            return ""
        text = r.text
        patterns = (
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
        )
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                desc = html_mod.unescape(m.group(1)).strip()
                return desc[:max_len]
    except Exception:  # noqa: BLE001
        pass
    return ""


# --------------------------------------------------------------------------
# 中文舆论 / 流量
# --------------------------------------------------------------------------

def fetch_zhihu():
    """知乎热榜：https://api.zhihu.com/topstory/hot-list"""
    try:
        r = _get("https://api.zhihu.com/topstory/hot-list", params={"limit": 50})
        r.raise_for_status()
        data = r.json().get("data", [])
        items = []
        for d in data:
            t = d.get("target") or {}
            title = (t.get("title") or "").strip()
            if not title:
                continue
            qid = t.get("id")
            url = f"https://www.zhihu.com/question/{qid}" if qid else "https://www.zhihu.com/hot"
            items.append({
                "title": title,
                "url": url,
                "heat": d.get("detail_text") or "",
                "extra": (t.get("excerpt") or "")[:120],
            })
        return _ok(items)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def fetch_douyin():
    """抖音热搜榜：iesdouyin 公开接口"""
    try:
        r = _get("https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/")
        r.raise_for_status()
        j = r.json()
        if j.get("status_code") != 0:
            return {"ok": False, "error": f"douyin status_code={j.get('status_code')}"}
        items = []
        for w in j.get("word_list") or []:
            word = (w.get("word") or "").strip()
            if not word:
                continue
            items.append({
                "title": word,
                "url": f"https://www.douyin.com/search/{_quote(word)}",
                "heat": f"热度 {w.get('hot_value', '')}".strip(),
                "extra": (w.get("sentence") or "")[:120],
            })
        return _ok(items)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def fetch_bilibili_popular():
    """B站全站热门视频"""
    try:
        r = _get("https://api.bilibili.com/x/web-interface/popular", params={"ps": 20, "pn": 1})
        r.raise_for_status()
        j = r.json()
        if j.get("code") != 0:
            return {"ok": False, "error": f"bilibili code={j.get('code')} {j.get('message')}"}
        items = []
        for v in (j.get("data") or {}).get("list", []):
            stat = v.get("stat") or {}
            items.append({
                "title": v.get("title", ""),
                "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
                "heat": f"播放 {stat.get('view', 0)} / 赞 {stat.get('like', 0)}",
                "extra": (v.get("desc") or "")[:120],
            })
        return _ok(items)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def fetch_bilibili_hot_search():
    """B站热搜词"""
    try:
        r = _get("https://api.bilibili.com/x/web-interface/search/square", params={"limit": 20})
        r.raise_for_status()
        j = r.json()
        if j.get("code") != 0:
            return {"ok": False, "error": f"bilibili code={j.get('code')} {j.get('message')}"}
        items = []
        trending = ((j.get("data") or {}).get("trending") or {}).get("list") or []
        for w in trending:
            kw = (w.get("keyword") or "").strip()
            if not kw:
                continue
            items.append({
                "title": kw,
                "url": f"https://search.bilibili.com/all?keyword={_quote(kw)}",
                "heat": f"热搜分 {w.get('heat_score', '')}".strip(),
                "extra": w.get("show_name") or "",
            })
        return _ok(items)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def fetch_weibo():
    """微博热搜（已弃用：官方接口需登录态，第三方聚合已失效）。
    保留函数以备后续找到可用抓法时重新启用，config.SOURCES 中已移除。"""
    return {"ok": False, "error": "微博信源已停用（官方反爬，无免登录接口）"}


# --------------------------------------------------------------------------
# RSS 类（商业财经 / 科技 / 数字生活）
# --------------------------------------------------------------------------

def _sanitize_xml(text):
    """清洗不规范的 XML：删非法控制字符、把裸 & 转义为 &amp;。

    很多媒体 feed 生成器会产出「半合法」XML（如爱范儿正文插图 URL 里的
    裸 &，2026-08-19 实测），严格解析直接失败，清洗后即可正常解析。
    """
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", text)
    return text


def _fetch_rss(url):
    """通用 RSS/Atom 解析（处理 namespace；对不规范 XML 自动清洗重试）"""
    r = _get(url)
    r.raise_for_status()
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        cleaned = _sanitize_xml(r.content.decode("utf-8", errors="replace"))
        root = ET.fromstring(cleaned.encode("utf-8"))
    items = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = date = ""
        for child in list(node):
            ct = child.tag.rsplit("}", 1)[-1]
            if ct == "title":
                title = html_mod.unescape((child.text or "")).strip()
            elif ct == "link":
                link = (child.get("href") or (child.text or "")).strip()
            elif ct in ("pubDate", "published", "updated"):
                date = (child.text or "").strip()
        if title and link:
            items.append({"title": title, "url": link, "heat": date[:16], "extra": ""})
    return items


def fetch_ifanr():
    """爱范儿 RSS（商业科技媒体，顶替已反爬的 36氪）"""
    try:
        return _ok(_fetch_rss("https://www.ifanr.com/feed"))
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def fetch_geekpark():
    """极客公园 RSS（科技商业媒体）"""
    try:
        return _ok(_fetch_rss("https://www.geekpark.net/rss"))
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def fetch_sspai():
    try:
        return _ok(_fetch_rss("https://sspai.com/feed"))
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def fetch_ithome():
    try:
        return _ok(_fetch_rss("https://www.ithome.com/rss/"))
    except Exception as e:  # noqa: BLE001
        return _fail(e)


# --------------------------------------------------------------------------
# 开发者生态
# --------------------------------------------------------------------------

def fetch_v2ex():
    """V2EX 热帖（公开 API；大陆网络可能不通，Actions 云端正常）"""
    try:
        r = _get("https://www.v2ex.com/api/topics/hot.json")
        r.raise_for_status()
        items = []
        for t in r.json():
            node = t.get("node") or {}
            items.append({
                "title": t.get("title", ""),
                "url": t.get("url", ""),
                "heat": f"回复 {t.get('replies', 0)}",
                "extra": f"节点: {node.get('title', '')}",
            })
        return _ok(items)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def fetch_hn():
    """Hacker News 头条（官方公开 API）"""
    try:
        ids = _get("https://hacker-news.firebaseio.com/v0/topstories.json").json()[:15]
        items = []
        for i in ids:
            try:
                d = _get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json").json()
            except Exception:  # noqa: BLE001
                continue
            if not d:
                continue
            items.append({
                "title": d.get("title", ""),
                "url": d.get("url") or f"https://news.ycombinator.com/item?id={d.get('id')}",
                "heat": f"{d.get('score', 0)} 分 / {d.get('descendants', 0)} 评论",
                "extra": "",
            })
        return _ok(items)
    except Exception as e:  # noqa: BLE001
        return _fail(e)


def fetch_github_trending():
    """GitHub Trending（HTML 解析；大陆网络可能不通，Actions 云端正常）"""
    try:
        r = _get("https://github.com/trending", headers={"Accept": "text/html"})
        r.raise_for_status()
        text = r.text
        blocks = re.findall(r'<article class="Box-row">(.*?)</article>', text, re.S)
        items = []
        for b in blocks:
            m = re.search(r'<h2[^>]*>\s*<a[^>]*href="(/[^"#]+)"', b)
            if not m:
                continue
            repo = m.group(1).strip("/")
            dm = re.search(r'<p class="col-9[^"]*"[^>]*>(.*?)</p>', b, re.S)
            desc = ""
            if dm:
                desc = html_mod.unescape(re.sub(r"<[^>]+>", "", dm.group(1))).strip()
            sm = re.search(r'stargazers"[^>]*>(?:.*?</svg>)?\s*([\d.,]+k?)\s*</a>', b, re.S)
            stars = sm.group(1) if sm else ""
            items.append({
                "title": repo,
                "url": f"https://github.com/{repo}",
                "heat": f"{stars} stars".strip(),
                "extra": desc[:120],
            })
        return _ok(items)
    except Exception as e:  # noqa: BLE001
        return _fail(e)
