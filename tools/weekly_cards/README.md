# 瞭望塔周报卡片生成器 v2

周报 Markdown → 小红书知识卡片 PNG。深蓝情报台风格（与 xhs-card 的赤陶暖色区分）。

## 快速开始

```powershell
# 渲染最近一份周报（3:4）
python tools/weekly_cards/cards.py

# 指定周报 / 9:15 比例 / 自定义水印
python tools/weekly_cards/cards.py --report reports/2026-08-23-weekly.md --ratio 9:15 --watermark "@你的水印"

# 只解析不渲染（调试用）
python tools/weekly_cards/cards.py --dry-run
```

输出：`tools/weekly_cards/output/{周日}/01_封面.png ... 05_看点与小结.png`

## 与 v1（xhs-card）的架构差异

| | v1（Claude Code 版） | v2（本工具） |
|---|---|---|
| 内容来源 | 手工写进 HTML 模板 | **自动解析周报 Markdown** |
| 改比例 | 改 5+ 处魔法数字，几分钟 | `--ratio 3:4/9:15`，1 秒 |
| 截图 | 整页截图 + 坐标裁剪（有坑） | **每卡独立渲染**，无裁剪逻辑 |
| 配色/尺寸 | 散落 CSS | 集中在 `RATIOS` / `THEME` / `FONT` 三个配置区 |

## 卡片结构（5-7 张自动分页）

1. 封面（标题 + 日期 + 关键词 chips + 目录）
2. 本周核心趋势（每页 3 条）
3. 连续出现的信号（每页 4 条，带"出现 N 天"徽章）
4. 值得记住（每页 4 条，标题 + 点评 + 来源域名）
5. 下周看点 + 社会观察小结

## 依赖

`playwright`（chromium 已装）+ 无需 Pillow。若云端使用：`pip install playwright && playwright install chromium`。

## 自定义

- 配色：改 `cards.py` 顶部 `THEME` dict（深蓝底 + 琥珀金 accent）
- 比例：`RATIOS` dict 添加新比例即可（如 `"1:1": {"w": 1080, "h": 1080}`）
- 水印：`--watermark` 参数，默认「瞭望塔周报 · AI 全网热点观察」
