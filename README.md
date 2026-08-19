# 瞭望塔（Watchtower）

> 每天早晚两次自动扫描全网热门平台，由 AI 从热榜中提炼「赚钱机会信号」，生成早报/晚报自动归档进 git 并推到 iPhone。
> 这是整个赚钱系统里唯一跑在云端的模块，其余（资金台账、日志、复盘）在线下完成。

## 它每天产出什么

每天运行两次（早报 + 晚报），每次自动 commit 两个文件到仓库：

| 文件 | 内容 |
| --- | --- |
| `reports/YYYY-MM-DD-morning.md` / `-evening.md` | 早报/晚报：信源健康表 + AI 机会报告（今日风向 / 机会信号 / 值得关注的人与产品 / 噪声提醒）+ 各平台原始榜单附录 |
| `data/YYYY-MM-DD-morning.json` / `-evening.json` | 当日抓取的原始结构化数据（供日后复盘分析） |

**推送节奏**（iPhone Bark 通知）：

| 时间（北京） | 内容 |
| --- | --- |
| 08:30（10:00 兜底） | 早报：隔夜热点 + 上午机会信号 |
| 20:00（22:30 兜底） | 晚报：当天热度变化 + 傍晚机会信号 |

> GitHub 定时任务高峰期可能延迟，兜底时间点保证「晚收到、不会收不到」；同日同时段防重，不会重复打扰。

历史报告全部留在 git 历史里，跑得越久越值钱：半年后你有一份带上下文的机会档案。

## 成本

- GitHub Actions：公开仓库**完全免费**
- DeepSeek API：早报+晚报各调用一次，**每天合计约 1~3 毛钱，一个月 3~9 元**（输入按每源 12 条裁剪过，已是压缩后的量级）。开发期反复手动测试才会出现单日几块钱的情况。

## 目录结构

```
.
├── .github/workflows/watchtower.yml   # GitHub Actions 定时调度 + 自动 commit
├── watchtower/                        # 核心代码
│   ├── config.py                      # 信源表（增删信源只改这里）
│   ├── fetchers.py                    # 各平台抓取器（失败自动降级）
│   ├── summarize.py                   # DeepSeek LLM 摘要（无 key 自动降级）
│   ├── render.py                      # Markdown 日报渲染
│   └── main.py                        # 入口
├── scripts/probe_sources.py           # 开发工具：探测信源健康
├── data/                              # 每日原始 JSON（git 归档）
├── reports/                           # 每日 Markdown 日报（git 归档）
├── requirements.txt                   # 仅依赖 requests
└── .env.example                       # API key 模板（复制为 .env）
```

## 推送：Bark（iOS，主力通道）

日报生成后，把「今日风向 + 机会信号表」全文推到 **iPhone 系统通知栏**（Bark，开源免费）。通知展开即可读全文，点击直达完整报告。

**一次性配置**（约 2 分钟）：
1. App Store 安装 **Bark**（开发者 Finb）
2. 打开 App 允许通知，首页地址 `https://api.day.app/KEY/` 中间的 `KEY` 即为设备密钥
3. 配置：
   - 本地：`.env` 填 `BARK_DEVICE_KEY`
   - 云端：GitHub `Settings → Secrets and variables → Actions` 添加 `BARK_DEVICE_KEY`

> 注意：Bark 服务器请求体约 4KB（≈1200 中文字）上限，推送模块已内置「按节智能裁剪」，
> 报告过长时优先保留今日风向与机会信号，其余点击通知看完整报告。

## 微信推送（可选，默认停用）

`watchtower/wechat_push.py` 提供微信官方通道（公众号测试号 + 模板消息）。当前 workflow 已停用该步骤（用户偏好 Bark）；需要恢复时取消
`.github/workflows/watchtower.yml` 中对应注释，并配置 4 个 Secrets：
`WECHAT_APPID / WECHAT_APPSECRET / WECHAT_OPENID / WECHAT_TEMPLATE_ID`。
申请流程：https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login 扫码登录，
记下 appID/appsecret → 扫码关注后记下 openid → 新增测试模板（内容填
`瞭望塔：{{title.DATA}} / 机会1：{{s1.DATA}} ... / {{note.DATA}}`）记下 template_id。
模板消息字段有显示长度限制，只能放短摘要，故作为 Bark 的补充通道。

## 本地运行

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2.（可选）配置 DeepSeek key：复制 .env.example 为 .env 并填入 key
#    不配置也能跑，只是日报没有 AI 分析部分

# 3. 跑一次
python watchtower/main.py            # 完整流程
python watchtower/main.py --no-llm   # 跳过 LLM
python scripts/probe_sources.py      # 只看各信源健康状态
```

## 部署到 GitHub Actions（一次性配置）

1. **建仓库**：GitHub 新建仓库（公开或私有均可，私有每月 2000 分钟免费额度，本任务每次 <5 分钟），例如 `watchtower`。
2. **推送代码**：
   ```powershell
   git init
   git add .
   git commit -m "init: watchtower"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/watchtower.git
   git push -u origin main
   ```
3. **配置 API key**（可选但强烈建议）：
   仓库页 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`：
   - Name: `DEEPSEEK_API_KEY`
   - Value: 你的 DeepSeek key（https://platform.deepseek.com 控制台创建，早晚两次调用合计每天约 1~3 毛钱）
4. **手动试跑一次**：仓库页 → `Actions` → 左侧 `Watchtower Daily` → `Run workflow`（可指定早报/晚报）。
   跑完后仓库里应出现 `data/` 和 `reports/` 的自动 commit。
5. **之后全自动**：每天北京时间 **08:30 早报 + 20:00 晚报**（各带一次兜底时间），结果自动 commit，你随时 `git pull` 收日报。

### 修改运行时间

编辑 `.github/workflows/watchtower.yml` 的 cron 表达式（UTC 时间，北京时间 = UTC + 8）：
```yaml
schedule:
  - cron: '30 0 * * *'    # 早报 08:30
  - cron: '0 2 * * *'     # 早报兜底 10:00
  - cron: '0 12 * * *'    # 晚报 20:00
  - cron: '30 14 * * *'   # 晚报兜底 22:30
```

## 信源清单（11 个）

| 信源 | 类别 | 抓取方式 | 稳定性 |
| --- | --- | --- | --- |
| 知乎热榜 | 中文舆论 | 公开接口 | 高 |
| 抖音热搜 | 短视频流量 | 公开接口 | 高 |
| B站热门视频 | 视频风向 | 公开接口 | 高 |
| B站热搜 | 视频风向 | 公开接口 | 高 |
| 爱范儿 | 商业科技 | 官方 RSS | 高 |
| 极客公园 | 科技商业 | 官方 RSS | 高 |
| 少数派 | 数字生活/副业 | 官方 RSS | 高 |
| IT之家 | 科技新闻 | 官方 RSS | 高 |
| V2EX 热帖 | 开发者社区 | 公开 API | 高（云端）；大陆本地网络不通属正常 |
| Hacker News | 全球科技 | 官方 API | 高 |
| GitHub Trending | 开发者生态 | HTML 解析 | 中（云端正常；页面改版可能失效） |

> 微博热搜与 36氪曾入选，但官方接口反爬（需登录态/JS 挑战），免登录抓取不可行，已移除。
> 找到可用替代后可在 `fetchers.py` 实现新函数、`config.py` 加一行即可恢复。

**降级设计**：任何一个信源挂掉，只在该日报告里标 ❌，不影响其他信源和整体流程。

## 报告怎么读（配合线下复盘）

- **看「机会信号」表**：每天挑 1 条置信度 ≥ 中的机会，执行「下一步可验证动作」，结果记进你的线下行动日志。
- **看「噪声提醒」**：这些热点直接跳过，省时间。
- **每周回顾 `reports/` 一周的日报**：哪些机会反复出现（= 真趋势），哪些当天就被证伪。
- 不要指望日报直接给你钱，它是**你的机会雷达**，行动和复盘仍然在线下由你完成。

## 常见问题

- **某天报告里某信源 ❌**：先 `git pull` 到本地跑 `python scripts/probe_sources.py` 看是否恢复。平台接口经常变动，长期失效的信源可在 `config.py` 删掉或换新。
- **想加新平台**：在 `fetchers.py` 写一个返回 `{"ok": ..., "items": [...]}` 的函数，再到 `config.py` 的 `SOURCES` 加一行即可。
- **AI 报告没生成**：检查 GitHub 仓库是否配了 `DEEPSEEK_API_KEY`，以及 key 是否欠费。
- **大陆本地跑 v2ex / GitHub Trending 失败**：正常，这两家大陆网络不通；Actions 云端在海外，不受影响。
