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


def repo_report_url(date_str, env_override="WATCHTOWER_REPO_URL"):
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
    return f"{base}/blob/main/reports/{date_str}.md"
