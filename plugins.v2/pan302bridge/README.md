# Pan302Bridge

`Pan302Bridge` 是一个 MoviePilot V2 插件，用于接收 pan-302 的任务回调，并在 STRM 生成完成后刷新 Emby 或 MoviePilot 已配置的媒体服务器。

如果填写了 Emby 地址和 API Key，插件会直连 Emby 刷新媒体库。没有填写时，插件会调用 MoviePilot 已启用的媒体服务器刷新能力。

## 功能

- 接收 pan-302 回调。
- 保存最近一次回调记录。
- 根据事件名触发 MoviePilot 已启用媒体服务器刷新。
- 可选直连 Emby 刷新媒体库，避免同时刷新 MoviePilot 中配置的多个媒体服务器。
- 可选发送 MoviePilot 通知。
- 支持在插件详情页手动刷新媒体服务器。

## 配置

- `启用 pan-302 联动`：是否启用插件。
- `收到 pan-302 回调后发送 MoviePilot 通知`：启用后收到回调会发送通知。
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
  "cloudPath": "/media/video/xxx.mkv",
  "localPath": "",
  "ruleName": "115",
  "taskId": "",
  "time": "2026-05-11 12:00:00"
}
```
