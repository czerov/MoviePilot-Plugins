# Pan302Bridge

`Pan302Bridge` 是一个 MoviePilot V2 插件，用于在 MoviePilot 中联动 pan-302 的分享转存、离线移动、STRM 生成和转移整理流程。

## 功能

- 保存 pan-302 地址和 Bearer Token。
- 在插件详情页查看 pan-302 地址、最近连接、最近状态、最近动作和最近回调。
- 通过插件 API 测试 pan-302 连接。
- 触发 pan-302 全量或指定 STRM 同步。
- 触发 pan-302 指定转移规则。
- 接收 pan-302 回调，并可在 MoviePilot 内发送通知。

## 配置

- `启用 pan-302 联动`：是否启用插件。
- `pan-302 地址`：例如 `http://192.168.6.36:3000`。
- `pan-302 Token`：pan-302 的 Bearer Token。
- `回调校验 Token`：pan-302 回调 MoviePilot 时提交的简单校验 Token。
- `收到 pan-302 回调后发送 MoviePilot 通知`：启用后收到回调会调用 MoviePilot 通知。
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

