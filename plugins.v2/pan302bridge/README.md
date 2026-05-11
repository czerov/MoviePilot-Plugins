# Pan302Bridge

`Pan302Bridge` 是一个 MoviePilot V2 插件，用于接收 pan-302 的任务回调，并在 STRM 生成完成后调用 MoviePilot 已配置的媒体服务器刷新能力。

插件不再重复配置 Emby 地址和 API Key。Emby、Jellyfin、Plex 等媒体服务器仍然在 MoviePilot 原有设置中维护。

## 功能

- 接收 pan-302 回调。
- 校验可选的回调 Token。
- 保存最近一次回调记录。
- 根据事件名触发 MoviePilot 已启用媒体服务器刷新。
- 可选发送 MoviePilot 通知。
- 支持在插件详情页手动刷新媒体服务器。

## 配置

- `启用 pan-302 联动`：是否启用插件。
- `回调后刷新 MoviePilot 媒体服务器`：启用后，匹配事件的回调会调用 MoviePilot 已配置的媒体服务器刷新。
- `回调校验 Token`：可选。如果填写，pan-302 回调 JSON 中的 `token` 必须一致。
- `刷新延迟秒数`：可选。STRM 刚生成后等待几秒再刷新媒体服务器。
- `触发刷新的回调事件`：多个事件用英文逗号分隔。
- `收到 pan-302 回调后发送 MoviePilot 通知`：启用后收到回调会发送通知。

默认触发刷新的事件：

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

## pan-302 回调地址

pan-302 系统设置中的回调 URL 填：

```text
http://你的MoviePilot地址:3000/api/v1/plugin/Pan302Bridge/pan302_callback?apikey=你的MoviePilot_API_TOKEN
```

如果插件里没有填写 `回调校验 Token`，pan-302 请求体不需要额外带 `token`。

如果插件里填写了 `回调校验 Token`，pan-302 请求体需要带同样的 `token`。

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

带回调校验 Token 的示例：

```json
{
  "token": "callback_token",
  "event": "strm_generated",
  "title": "pan-302 STRM 生成完成",
  "text": "资源已整理并生成 STRM"
}
```
