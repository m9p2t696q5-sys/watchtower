"""DeepSeek LLM 摘要：把全网热榜翻译成「赚钱机会信号」报告。

无 API key 或调用失败时返回 None，上层自动降级为纯榜单报告。
"""

import os

import requests

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是一名商业情报分析师，服务于一位正在寻找自动化/低投入赚钱机会的个人创业者。

你会收到今天从多个平台抓取的热榜条目汇总。请严格只基于这些条目分析，不要编造条目之外的具体事实、数字或事件。

请输出以下四部分（中文，Markdown 格式，直接输出报告正文，不要任何开场白或结尾客套）：

## 今日风向
用 3~5 句话概括今天全网的整体气氛：热点集中在哪些领域、情绪如何、与昨天相比可能的变化（只谈今天给出的条目能支撑的内容）。

## 机会信号
从热榜中识别与「赚钱/商业机会」直接或间接相关的信号，输出表格：

| 机会 | 类型 | 信号来源 | 热度证据 | 置信度 | 下一步可验证动作 |

- 类型用：新需求 / 工具化机会 / 内容流量红利 / 平台政策变化 / 趋势赛道 / 信息差。
- 最多 8 条，宁缺毋滥；确实没有就明说「今日无明显机会信号」并解释为什么。
- 「下一步可验证动作」必须具体到今天就能做，例如「搜索该关键词，看供需与竞品数量」「注册体验该产品并记录上手成本」。
- 置信度标注：高 / 中 / 低。

## 值得关注的人 / 品牌 / 产品
挑出热榜中表现突出的创作者、品牌或产品（最多 5 条），每条说明：它是谁、做对了什么、对你（想找低投入赚钱机会的个人）有什么可借鉴或可模仿的点。

## 噪声提醒
指出哪些热点是纯娱乐 / 情绪消费 / 一次性事件，不值得投入时间研究（2~3 条），并给一句判断理由。

硬性要求：
1. 只输出报告正文。
2. 每条结论都要能对应到输入条目；没有证据支撑的观点不要写。
3. 机会信号部分宁缺毋滥，避免为了凑数把娱乐热点包装成机会。
"""


def _build_user_prompt(entries_by_source, date_str):
    lines = [f"今天是 {date_str}。以下是从多个平台抓取的热榜条目（按平台分组）："]
    for name, items in entries_by_source.items():
        lines.append(f"\n## {name}")
        for it in items:
            heat = it.get("heat") or ""
            lines.append(f"- {it['title']}（{heat}）{it['url']}")
    lines.append("\n请按系统提示的格式输出今天的报告。")
    return "\n".join(lines)


def summarize(entries_by_source, date_str, api_key=None):
    """调用 DeepSeek 生成中文机会报告；失败返回 None。"""
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
