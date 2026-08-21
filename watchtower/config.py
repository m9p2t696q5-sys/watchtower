"""瞭望塔信源配置（表驱动）。

新增/删减信源只需改 SOURCES 列表，并在 fetchers.py 中实现对应 fetcher 函数。
limit = 进入报告附录的最大条目数。
"""

# 进入 LLM 摘要的每信源条目上限（低于 limit，用于控制 API 成本；
# 报告附录仍展示全量 limit 条，不影响信息完整性）
LLM_LIMIT_PER_SOURCE = 12

SOURCES = [
    {
        "id": "zhihu",
        "name": "知乎热榜",
        "category": "中文舆论风向",
        "fetcher": "fetch_zhihu",
        "limit": 20,
        "note": "公开接口，稳定",
    },
    {
        "id": "douyin",
        "name": "抖音热搜",
        "category": "短视频流量",
        "fetcher": "fetch_douyin",
        "limit": 20,
        "note": "公开接口，稳定",
    },
    {
        "id": "bilibili_popular",
        "name": "B站热门视频",
        "category": "视频内容风向",
        "fetcher": "fetch_bilibili_popular",
        "limit": 15,
        "note": "公开接口，稳定",
    },
    {
        "id": "bilibili_hot_search",
        "name": "B站热搜",
        "category": "视频内容风向",
        "fetcher": "fetch_bilibili_hot_search",
        "limit": 15,
        "note": "公开接口，稳定",
    },
    {
        "id": "ifanr",
        "name": "爱范儿",
        "category": "商业科技媒体",
        "fetcher": "fetch_ifanr",
        "limit": 20,
        "note": "官方 RSS",
    },
    {
        "id": "geekpark",
        "name": "极客公园",
        "category": "科技商业媒体",
        "fetcher": "fetch_geekpark",
        "limit": 20,
        "note": "官方 RSS",
    },
    {
        "id": "sspai",
        "name": "少数派",
        "category": "数字生活/效率/副业",
        "fetcher": "fetch_sspai",
        "limit": 15,
        "note": "官方 RSS",
    },
    {
        "id": "ithome",
        "name": "IT之家",
        "category": "科技新闻",
        "fetcher": "fetch_ithome",
        "limit": 20,
        "note": "官方 RSS",
    },
    {
        "id": "v2ex",
        "name": "V2EX 热帖",
        "category": "开发者社区",
        "fetcher": "fetch_v2ex",
        "limit": 20,
        "note": "公开 API；大陆网络可能不通，Actions 云端（海外）正常",
    },
    {
        "id": "hn",
        "name": "Hacker News",
        "category": "全球科技风向",
        "fetcher": "fetch_hn",
        "limit": 15,
        "note": "官方公开 API",
        "lang": "en",
    },
    {
        "id": "github_trending",
        "name": "GitHub Trending",
        "category": "开发者生态",
        "fetcher": "fetch_github_trending",
        "limit": 15,
        "note": "HTML 解析；大陆网络可能不通，Actions 云端正常",
        "lang": "en",
    },
]
