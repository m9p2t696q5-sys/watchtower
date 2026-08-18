"""开发工具：探测所有信源接口当前健康状态。

用法（仓库根目录）：
  python scripts/probe_sources.py        # 只显示状态
  python scripts/probe_sources.py -v     # 附加显示每个信源前 3 条样本
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from watchtower import config, fetchers  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    ok = 0
    total = len(config.SOURCES)
    for src in config.SOURCES:
        fn = getattr(fetchers, src["fetcher"])
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": str(e)}
        if res.get("ok"):
            ok += 1
            print(f"[OK]   {src['id']:<20} {len(res['items']):>3} 条")
            if args.verbose:
                for it in res["items"][:3]:
                    print(f"        - {it['title'][:60]}  |  {it.get('heat', '')[:30]}")
        else:
            print(f"[FAIL] {src['id']:<20} {res.get('error', '')[:120]}")
    print(f"\n{ok}/{total} 个信源可用")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
