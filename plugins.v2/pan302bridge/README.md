# Pan302Bridge

`Pan302Bridge` 是一个 MoviePilot V2 插件，用于接收 pan-302 的任务回调，并在 pan-302 生成 STRM 后触发 Emby 刷新媒体库。

## 功能

- 保存 pan-302 地址和 Bearer Token。
- 在插件详情页查看 pan-302 地址、最近连接、最近状态、最近动作和最近回调。
- 通过插件 API 测试 pan-302 连接。
- 触发 pan-302 全量或指定 STRM 同步。
- 触发 pan-302 指定转移规则。
- 接收 pan-302 回调，并可在 MoviePilot 内发送通知。
- pan-302 回调 STRM 完成事件后，自动触发 Emby 全量或指定媒体库刷新。
- 支持手动测试 Emby 连接和手动刷新 Emby。

## 配置

- `启用 pan-302 联动`：是否启用插件。
- `pan-302 地址`：例如 `http://192.168.6.36:3000`。
- `pan-302 Token`：pan-302 的 Bearer Token。
- `回调校验 Token`：pan-302 回调 MoviePilot 时提交的简单校验 Token。
- `收到 pan-302 回调后发送 MoviePilot 通知`：启用后收到回调会调用 MoviePilot 通知。
- `pan-302 回调后刷新 Emby 媒体库`：启用后，匹配事件的回调会触发 Emby 刷库。
- `Emby 地址`：例如 `http://192.168.6.36:8096`，不要在末尾加 `/Library/Refresh`。
- `Emby API Key`：Emby 后台创建的 API Key。
- `Emby 媒体库 ID`：可选，多个用英文逗号分隔；留空时刷新全部媒体库。
- `Emby 刷库延迟秒数`：可选，STRM 刚生成后延迟几秒再通知 Emby。
- `触发 Emby 刷库的回调事件`：默认 `strm_generated,strm_sync_completed,share_transfer_completed,offline_move_completed`。
- `快捷 STRM 名称`：可选，用于详情页按钮触发指定 STRM 同步。
- `快捷转移规则名称`：可选，用于详情页按钮触发指定转移规则。

## 插件 API

MoviePilot 会将插件 API 注册到：

```text
/api/v1/plugin/Pan302Bridge/<path>
```

当前插件暴露：

```text
GET  /status
POST /test_connection
POST /pan302_status
POST /transfer_status
POST /trigger_strm_sync
POST /trigger_transfer_rule
POST /pan302_callback
POST /test_emby
POST /refresh_emby
```

## pan-302 回调示例

```json
{
  "token": "callback_token",
  "event": "share_transfer_completed",
  "title": "115 分享转存完成",
  "text": "资源已整理并生成 STRM",
  "cloudPath": "/media/video/xxx.mkv",
  "localPath": "",
  "ruleName": "115",
  "taskId": "",
  "time": "2026-05-11 12:00:00"
}
```

建议事件名：

```text
share_transfer_completed
offline_move_completed
strm_generated
strm_sync_completed
transfer_failed
```

默认只有下面事件会触发 Emby 刷库：

```text
strm_generated
strm_sync_completed
share_transfer_completed
offline_move_completed
```

`transfer_failed` 默认只记录和通知，不触发 Emby 刷库。

## Emby 刷库方式

如果 `Emby 媒体库 ID` 留空，插件会调用 Emby：

```text
POST /emby/Library/Refresh
```

如果填写了媒体库 ID，例如：

```text
577,3,1959
```

插件会分别调用：

```text
POST /emby/Items/577/Refresh
POST /emby/Items/3/Refresh
POST /emby/Items/1959/Refresh
```
