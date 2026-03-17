# zsxq-crawler

[English](README.md)

知识星球付费社群爬虫。通过 zsxq REST API 抓取主题、评论、图片和文件附件。

## 特性

- **增量爬取** — 自动跳过已下载的主题，支持中断后继续
- **完整内容** — 主题、评论、图片、文件附件
- **限流处理** — 可配置请求间隔、批次暂停，API 1059 错误自动重试
- **全量分页** — 基于游标分页，可爬取全部历史或指定页数

## 快速开始

```bash
git clone https://github.com/stoicneko/zsxq-crawler.git
cd zsxq-crawler
python3 -m venv venv
source venv/bin/activate        # bash/zsh
# source venv/bin/activate.fish  # fish shell
pip install -r requirements.txt
```

### 获取 Cookie

1. 浏览器打开 https://wx.zsxq.com 并扫码登录
2. F12 打开开发者工具 → Network（网络）标签
3. 找到任意 `api.zsxq.com` 的请求
4. 从 Cookie 请求头中复制 `zsxq_access_token=...` 的值

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入 ZSXQ_COOKIE 和 ZSXQ_GROUP_ID
```

### 运行

```bash
python main.py                          # 爬取全部
python main.py --max-pages 5            # 限制 5 页（100 条主题）
python main.py --no-images --no-files   # 仅爬文字和评论
python main.py --no-comments            # 跳过评论
python main.py -v                       # 详细日志
```

按 `Ctrl+C` 可随时中断，已爬取的数据自动保存。

## 配置项

所有配置在 `.env` 文件中（参考 `.env.example`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ZSXQ_COOKIE` | *（必填）* | 浏览器 Cookie，包含 `zsxq_access_token` |
| `ZSXQ_GROUP_ID` | *（必填）* | 社群 URL 中的 Group ID |
| `ZSXQ_REQUEST_DELAY` | `3` | 请求间隔（秒） |
| `ZSXQ_BATCH_SIZE` | `15` | 每批请求数量 |
| `ZSXQ_BATCH_PAUSE` | `180` | 批次间暂停时间（秒） |
| `ZSXQ_DOWNLOAD_IMAGES` | `true` | 是否下载图片 |
| `ZSXQ_DOWNLOAD_FILES` | `true` | 是否下载文件附件 |
| `ZSXQ_CRAWL_COMMENTS` | `true` | 是否爬取评论 |
| `ZSXQ_OUTPUT_DIR` | `output` | 输出目录 |
| `ZSXQ_MAX_PAGES` | `0` | 最大爬取页数（0 = 不限） |

## 输出结构

```
output/{group_id}/
├── all_topics.json      # 全部主题合并，按时间排序
├── summary.json         # 爬取统计
├── topics/              # 每个主题单独一个 JSON
│   ├── {topic_id}.json
│   └── ...
├── images/              # 下载的图片
│   ├── {topic_id}_{image_id}.jpg
│   └── ...
└── files/               # 下载的附件
    ├── {file_id}_{filename}
    └── ...
```

## 许可证

MIT
