"""微信官方推送（公众号测试号 + 模板消息）。

原理（参考 B 站专栏「白嫖微信官方推送」/ tech-shrimp/FreeWechatPush）：
  1. 微信公众平台测试号提供 appID/appSecret，扫码关注得到 openid，自建模板得 template_id；
  2. 用 appID/appSecret 换 access_token，调用模板消息接口把内容推到个人微信。

用法：
  python watchtower/wechat_push.py          # 推送当日报告精华到微信
  python watchtower/wechat_push.py --date 2026-08-19 --file reports/2026-08-19.md  # 指定

需要环境变量（本地放 .env，云端放 GitHub Secrets）：
  WECHAT_APPID / WECHAT_APPSECRET / WECHAT_OPENID / WECHAT_TEMPLATE_ID
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 支持直接 python watchtower/xxx.py

import requests

from watchtower.utils import REPO_ROOT, load_env, repo_report_url, today_cn

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/template/send"

FIELD_MAX = 40  # 模板消息单字段保守长度（字符）


def _clip(s, limit=FIELD_MAX):
    s = (s or "").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def extract_fields(report_md):
    """从日报 Markdown 抽取微信推送字段：title / s1 / s2 / s3 / note 由调用方拼。"""
    title = ""
    m = re.search(r"## 今日风向\s*\n+(.*?)(?:\n##|\n\n##|\Z)", report_md, re.S)
    if m:
        # 取第一句
        first = re.split(r"[。！？!?]", m.group(1).strip(), maxsplit=1)[0]
        title = first.strip()
    signals = []
    for row in re.findall(r"^\|\s*([^|]+?)\s*\|\s*[^|]+\|\s*[^|]+\|\s*[^|]+\|\s*([^|]+?)\s*\|", report_md, re.M):
        name, confidence = row[0].strip(), row[1].strip()
        if name in ("机会", "------") or not name:
            continue
        signals.append(f"{name}（{confidence}）")
    return title, signals


def get_access_token(appid, secret):
    r = requests.get(TOKEN_URL, params={
        "grant_type": "client_credential", "appid": appid, "secret": secret,
    }, timeout=20)
    j = r.json()
    if j.get("errcode"):
        raise RuntimeError(f"获取 access_token 失败: {j}")
    return j["access_token"]


def send(appid, secret, openid, template_id, data, url):
    token = get_access_token(appid, secret)
    body = {
        "touser": openid,
        "template_id": template_id,
        "url": url,
        "data": {k: {"value": v} for k, v in data.items()},
    }
    r = requests.post(SEND_URL, params={"access_token": token}, json=body, timeout=20)
    j = r.json()
    if j.get("errcode") == 42001:  # token 失效，刷新重试一次
        token = get_access_token(appid, secret)
        r = requests.post(SEND_URL, params={"access_token": token}, json=body, timeout=20)
        j = r.json()
    return j


def push_daily(report_md, date_str, ok_count, total_count):
    appid = os.environ.get("WECHAT_APPID", "")
    secret = os.environ.get("WECHAT_APPSECRET", "")
    openid = os.environ.get("WECHAT_OPENID", "")
    template_id = os.environ.get("WECHAT_TEMPLATE_ID", "")
    if not all([appid, secret, openid, template_id]):
        print("[wechat] 未完整配置微信推送环境变量，跳过推送")
        return

    title, signals = extract_fields(report_md)
    data = {
        "title": _clip(title, 30),
        "s1": _clip(signals[0] if len(signals) > 0 else "今日无明显机会信号"),
        "s2": _clip(signals[1] if len(signals) > 1 else "—"),
        "s3": _clip(signals[2] if len(signals) > 2 else "—"),
        "note": f"信源 {ok_count}/{total_count} 正常 · 点此看完整报告",
    }
    url = repo_report_url(date_str)
    try:
        resp = send(appid, secret, openid, template_id, data, url)
        if resp.get("errcode") == 0:
            print(f"[wechat] 推送成功: {data['title'][:30]}")
        else:
            print(f"[wechat] 推送失败: {resp}")
    except Exception as e:  # noqa: BLE001
        print(f"[wechat] 推送异常（不影响主流程）: {type(e).__name__}: {e}")


def main():
    parser = argparse.ArgumentParser(description="推送瞭望塔日报精华到微信")
    parser.add_argument("--date", default=today_cn())
    parser.add_argument("--file", default=None, help="指定报告文件（默认按日期找 reports/<date>.md）")
    args = parser.parse_args()

    load_env()
    report_path = Path(args.file) if args.file else REPO_ROOT / "reports" / f"{args.date}.md"
    if not report_path.exists():
        print(f"[wechat] 报告不存在: {report_path}", file=sys.stderr)
        sys.exit(1)
    report_md = report_path.read_text(encoding="utf-8")

    # 从报告头部解析信源健康数（"信源 9/11 正常"）
    m = re.search(r"信源 (\d+)/(\d+) 正常", report_md)
    ok_count, total_count = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    push_daily(report_md, args.date, ok_count, total_count)


if __name__ == "__main__":
    main()
