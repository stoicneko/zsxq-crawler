# zsxq-crawler

[English](README_EN.md)

知识星球付费社群爬虫及工具集。通过 zsxq REST API 抓取主题、评论、图片和文件附件，支持本地网页浏览、实时监控和知识库导出。

## 特性

- **增量爬取** — 自动跳过已下载的主题，支持中断后继续
- **完整内容** — 主题、评论、图片、文件附件
- **限流处理** — 可配置请求间隔、批次暂停，API 1059 错误自动重试
- **网页浏览器** — Notion 风格本地 UI，支持搜索、筛选、收藏、标签和图片灯箱
- **实时监控** — 轮询新主题并自动刷新网页浏览器
- **知识库导出** — 将主题转换为 Obsidian 兼容的 Markdown 文件，含自动生成索引
- **systemd 部署** — 以用户服务方式运行监控和网页浏览器

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

### 运行爬虫

```bash
python main.py                          # 爬取全部
python main.py --max-pages 5            # 限制 5 页（100 条主题）
python main.py --no-images --no-files   # 仅爬文字和评论
python main.py --no-comments            # 跳过评论
python main.py -v                       # 详细日志
```

按 `Ctrl+C` 可随时中断，已爬取的数据自动保存。

## 网页浏览器

基于 Flask 的本地应用，以简洁的 Notion 风格界面浏览已爬取的主题。

```bash
python web/app.py                       # 启动于 http://localhost:5000
```

**功能：**
- 无限滚动主题列表，支持全文搜索
- 按类型（话题 / 问答 / 作业）、日期范围、加精状态筛选
- 收藏和自定义标签（持久化到 `user_data.json`）
- 图片灯箱，支持缩放（鼠标滚轮 / +/-）、拖拽平移和键盘快捷键
- `/api/reload` 端点用于从磁盘刷新主题（供监控服务调用）

## 实时监控

轮询服务，监控新主题并自动下载。

```bash
python monitor.py                       # 每 5 分钟轮询一次（默认）
python monitor.py --interval 60         # 每 60 秒轮询一次
python monitor.py --no-notify           # 不通知网页应用
python monitor.py --no-images --no-files   # 轻量模式
python monitor.py -v                    # 详细日志
```

发现新主题时，监控服务通过爬虫流水线处理并向网页浏览器发送刷新信号，实现即时更新。

### systemd 部署

以用户服务方式同时运行监控和网页浏览器：

```bash
# 安装服务文件
cp deploy/*.service deploy/*.target ~/.config/systemd/user/

# 启动服务
systemctl --user start zsxq.target
systemctl --user enable zsxq.target     # 开机自启

# 查看日志
journalctl --user -u zsxq-monitor -f
journalctl --user -u zsxq-web -f
```

## 知识库导出

将已爬取的主题转换为 Obsidian 兼容的 Markdown 文件，自动生成索引。

```bash
python convert_to_kb.py                           # 自动检测 group，输出到 knowledge-base/
python convert_to_kb.py --output-dir my-kb         # 自定义输出目录
python convert_to_kb.py --source-dir output        # 自定义源目录
python convert_to_kb.py --group-id 12345           # 指定 group ID
```

**生成内容：**
- 每个主题一个 Markdown 文件（含元数据、图片、评论）
- 按月份、作者、类型分类的索引
- 符号链接的图片目录，方便 Obsidian 附件引用

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
| `ZSXQ_MONITOR_INTERVAL` | `300` | 监控轮询间隔（秒） |
| `ZSXQ_RELOAD_TOKEN` | *（空）* | `/api/reload` 端点的 Bearer 认证令牌 |

## 输出结构

```
output/{group_id}/
├── all_topics.json      # 全部主题合并，按时间排序
├── summary.json         # 爬取统计
├── user_data.json       # 网页浏览器的收藏和标签数据
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
