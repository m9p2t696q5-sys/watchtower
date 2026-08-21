"""DeepSeek LLM 摘要：把全网热榜翻译成「社会观察 + 赚钱机会信号」报告。

无 API key 或调用失败时返回 None，上层自动降级为纯榜单报告。
另含英文标题批量翻译函数（用于 HN / GitHub Trending 等英文信源）。
"""

import os
import re

import requests

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是一位「社会观察员 × 商业情报分析师」，服务于一位希望持续观察社会热点、理解现象背后机制、并从中发现机会的个人。

你会收到今天从多个平台抓取的热榜条目汇总（部分条目附有背景简介）。请严格基于这些材料分析，不要编造条目之外的事实、数字或事件。

请输出以下五个部分（中文，Markdown 格式，直接输出报告正文，不要任何开场白或结尾客套）：

## 今日风向
用 3~5 句话概括今天全网的整体气氛：热点集中在哪些领域、情绪如何（只谈条目能支撑的内容）。

## 社会现象观察
从热榜中找出 1~3 个值得深想的社会现象或结构性变化，每个用 2~3 句话说明「它可能意味着什么」。
- 优先关注：不同热点之间的关联（例如消费话题与政策话题同日出现指向什么）、人群情绪与心理、可能长期存在的结构变化（而非一次性事件）。
- 措辞克制，用「可能 / 似乎 / 值得关注」等表达，不要下断言。

## 机会信号
从热榜中识别与「赚钱/商业机会」直接或间接相关的信号，输出表格：

| 机会 | 类型 | 信号来源 | 热度证据 | 置信度 | 下一步可验证动作 |

- 类型用：新需求 / 工具化机会 / 内容流量红利 / 平台政策变化 / 趋势赛道 / 信息差。
- 最多 8 条，宁缺毋滥；确实没有就明说「今日无明显机会信号」并解释为什么。
- 「下一步可验证动作」必须具体到今天就能做，例如「搜索该关键词，看供需与竞品数量」「注册体验该产品并记录上手成本」。
- 置信度标注：高 / 中 / 低。

## 值得关注的人 / 品牌 / 事件
挑出热榜中值得记住的人、品牌或事件（最多 5 条），**按事件性质选择写法**：
- 正面事件：做对了什么、有什么可借鉴或可模仿。
- 负面事件（翻车、争议、退网等）：发生了什么、教训是什么、可能预示的行业变化。
- 中性/结构性事件（政策、行业变动等）：客观陈述影响与值得关注的原因。
- 讣告、灾难、社会悲剧类事件：简短致意或客观陈述即可。**严禁**用商业价值、流量价值等功利角度评述，不消费逝者与悲剧，不输出「无商业价值」之类的表述。

## 今日不必深挖
列出 2~3 条不建议投入时间研究的热点（纯娱乐、一次性赛事结果、周期性节日话题等），每条一句话理由。
- 讣告与悲剧事件不要放进本栏目。

硬性要求：
1. 只输出报告正文。
2. 每条结论都要能对应到输入条目；没有证据支撑的观点不要写。
3. 机会信号部分宁缺毋滥，避免为了凑数把娱乐热点包装成机会。
4. 措辞有温度：对人和悲剧保持尊重，避免冰冷的功利化表述。
"""


def _build_user_prompt(entries_by_source, date_str):
    lines = [f"今天是 {date_str}。以下是从多个平台抓取的热榜条目（按平台分组）："]
    for name, items in entries_by_source.items():
        lines.append(f"\n## {name}")
        for it in items:
            heat = it.get("heat") or ""
            line = f"- {it['title']}（{heat}）{it['url']}"
            if it.get("desc"):
                line += f" | 背景：{it['desc']}"
            lines.append(line)
    lines.append("\n请按系统提示的格式输出今天的报告。")
    return "\n".join(lines)


def summarize(entries_by_source, date_str, api_key=None):
    """调用 DeepSeek 生成中文报告；失败返回 None。"""
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None
    user_prompt = _build_user_prompt(entries_by_source, date_str)
    try:
        r = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2600,
            },
            timeout=180,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] LLM 摘要失败，降级为纯榜单报告: {type(e).__name__}: {e}")
        return None


def translate_titles(titles, api_key=None):
    """批量翻译英文标题，返回 {原文: 中文} 映射；失败返回空字典。"""
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key or not titles:
        return {}
    lines = "\n".join(f"{i}: {t}" for i, t in enumerate(titles))
    try:
        r = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是译者。把下面每行「编号: 英文标题」翻译成简洁通顺的中文，"
                        "输出格式严格为「编号: 中文」，每行一条，只输出翻译结果，不要解释。",
                    },
                    {"role": "user", "content": lines},
                ],
                "temperature": 0,
                "max_tokens": 30 * len(titles) + 100,
            },
            timeout=60,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        result = {}
        for line in content.splitlines():
            m = re.match(r"\s*(\d+)\s*[:：]\s*(.+)", line)
            if m:
                idx = int(m.group(1))
                if 0 <= idx < len(titles):
                    result[titles[idx]] = m.group(2).strip()
        return result
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 标题翻译失败（保留原文）: {type(e).__name__}")
        return {}
