# Pan302Bridge

`Pan302Bridge` 是一个 MoviePilot V2 插件，用于联动 MoviePilot 与 pan302。

插件支持两条链路：

- MoviePilot 整理完成后，主动通知 pan302 根据本地路径处理文件。
- pan302 回调 MoviePilot 后，刷新 Emby 或 MoviePilot 已配置的媒体服务器。

如果填写了 Emby 地址和 API Key，插件会直连 Emby 刷新媒体库。没有填写时，插件会调用 MoviePilot 已启用的媒体服务器刷新能力。

## 功能

- 接收 pan-302 回调。
- 监听 MoviePilot 整理完成事件，调用 pan302 的 `upload-by-path`。
- 监听 MoviePilot 用户消息中的 115 分享链接，调用 pan302 分享转存。
- 保存最近一次回调记录。
- 根据事件名触发 MoviePilot 已启用媒体服务器刷新。
- 可选直连 Emby 刷新媒体库，避免同时刷新 MoviePilot 中配置的多个媒体服务器。
- 可选发送 MoviePilot 通知。
- 支持配置通知默认图片，避免通知卡片显示灰色占位。
- 支持在插件详情页手动刷新媒体服务器。
- 插件初始化和收到回调时会写入运行日志。

## 配置

- `启用 pan-302 联动`：是否启用插件。
- `pan302 地址`：例如 `http://192.168.6.36:3000`，用于 MoviePilot 主动调用 pan302。
- `pan302 Token`：pan302 的 Token。
- `115 分享转存目录`：收到 115 分享链接时提交给 pan302 的转存目录。
- `整理完成包含目录`：可选。MoviePilot 整理完成的目标路径只有命中这些目录才会通知 pan302；留空则不限制。
- `收到 pan-302 回调后发送 MoviePilot 通知`：启用后收到回调会发送通知。
- `通知默认图片 URL`：当 pan-302 回调没有携带图片字段时，用该图片作为 MoviePilot 通知卡片图片。建议填写 JPG 或 PNG 图片链接，不建议使用 SVG。
- `Emby 地址（可选）`：填写后插件会直连 Emby，例如 `http://192.168.6.36:8096`。
- `Emby API Key（可选）`：Emby 后台生成的 API Key。

如果 `Emby 地址` 和 `Emby API Key` 都填写，刷新目标是 Emby。

如果二者都留空，刷新目标是 MoviePilot 已配置并启用的媒体服务器。

插件默认会在下面事件回调时刷新 MoviePilot 已配置的媒体服务器：

```text
strm_generated,strm_sync_completed,share_transfer_completed,offline_move_completed
```

`transfer_failed` 默认不会触发刷新。

## 插件 API

MoviePilot 会将插件 API 注册到：

```text
/api/v1/plugin/Pan302Bridge/<path>
```

当前插件暴露：

```text
GET  /status
POST /refresh_mediaserver
POST /pan302_callback
```

MoviePilot 主动调用 pan302 时会使用：

```text
GET /api/sync/upload-by-path?path=<整理完成路径>
GET /strm/api/task/save-share?url=<115分享链接>&folder=<115分享转存目录>
```

直连 Emby 时，插件会调用：

```text
POST /emby/Library/Refresh
```

## pan-302 回调地址

pan-302 系统设置中的回调 URL 填：

```text
http://你的MoviePilot地址:3000/api/v1/plugin/Pan302Bridge/pan302_callback?apikey=你的MoviePilot_API_TOKEN
```

## 回调示例

```json
{
  "event": "strm_generated",
  "title": "pan-302 STRM 生成完成",
  "text": "资源已整理并生成 STRM",
  "image": "https://example.com/pan302.png",
  "cloudPath": "/media/video/xxx.mkv",
  "localPath": "",
  "ruleName": "115",
  "taskId": "",
  "time": "2026-05-11 12:00:00"
}
```
