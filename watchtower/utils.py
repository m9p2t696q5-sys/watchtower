"""公共工具：env 加载 / 日期 / 报告链接推导。"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent


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


# 时段（slot）相关：早报 morning / 晚报 evening
SLOT_NAMES = {"morning": "早报", "evening": "晚报"}
EVENING_CRONS = ("0 12 * * *", "30 14 * * *")  # 晚报 20:30 与晚报兜底 22:30（UTC）


def resolve_slot(schedule_expr=None, dispatch_slot=None):
    """根据触发方式判断本次是早报还是晚报。

    优先级：手动触发指定的 slot > schedule 表达式匹配 > 默认 morning。
    """
    if dispatch_slot and dispatch_slot.strip().lower() in SLOT_NAMES:
        return dispatch_slot.strip().lower()
    if schedule_expr and schedule_expr.strip() in EVENING_CRONS:
        return "evening"
    return "morning"


def slot_name(slot):
    return SLOT_NAMES.get(slot, "日报")


def repo_report_url(date_str, slot=None, env_override="WATCHTOWER_REPO_URL"):
    """拼出当天报告的 GitHub 链接（供推送点击跳转）。"""
    base = os.environ.get(env_override, "")
    if not base:
        try:
            out = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                capture_output=True, text=True, cwd=REPO_ROOT, timeout=10,
            ).stdout.strip()
            m = re.match(r"(?:https://github\.com/|git@github\.com:)([^/]+)/([^/]+?)(?:\.git)?$", out)
            if m:
                base = f"https://github.com/{m.group(1)}/{m.group(2)}"
        except Exception:  # noqa: BLE001
            base = ""
    if not base:
        return ""
    filename = f"{date_str}-{slot}.md" if slot else f"{date_str}.md"
    return f"{base}/blob/main/reports/{filename}"
