# MoviePilot 插件对接 pan-302 开发提示词

这份文档用于新建一个 MoviePilot V2 插件项目，目标是开发一个 `Pan302Bridge` 插件，让 MoviePilot 可以主动调用 pan-302，也让 pan-302 在分享转存、离线移动、STRM 生成等流程完成后回调 MoviePilot。

## 目标

开发一个 MoviePilot V2 插件，作为 MoviePilot 和 pan-302 之间的桥接层。

插件第一版不要做复杂全页 UI，优先使用 MoviePilot 的 Vuetify JSON 配置页和详情页，先把核心联动跑通：

- 在 MoviePilot 插件配置里保存 pan-302 地址、账号或 Token。
- 在 MoviePilot 插件详情页展示 pan-302 连接状态。
- 在 MoviePilot 插件详情页提供按钮触发 pan-302 的常用动作。
- 在 MoviePilot 插件内暴露回调接口，接收 pan-302 的任务完成通知。
- 后续可通过 `get_actions()` 接入 MoviePilot 工作流。

## 参考仓库

- MoviePilot 插件市场仓库：`https://github.com/jxxghp/MoviePilot-Plugins`
- pan-302 项目仓库：`https://github.com/czerov/pan-302.git`

MoviePilot 插件仓库只负责插件源码、市场索引、图标和文档；插件真正运行在 MoviePilot 后端宿主中。

## 建议目录结构

```text
MoviePilot-Plugins/
├── package.v2.json
└── plugins.v2/
    └── pan302bridge/
        ├── __init__.py
        ├── README.md
        └── requirements.txt
```

插件类名建议使用：

```python
class Pan302Bridge(_PluginBase):
    ...
```

插件目录必须是类名小写：

```text
plugins.v2/pan302bridge/
```

## 插件第一版范围

第一版只做桥接，不要直接复刻 pan-302 的整个前端。

### 配置项

插件配置页提供这些字段：

- `enabled`：是否启用插件。
- `pan302_url`：pan-302 地址，例如 `http://192.168.6.36:3000`。
- `pan302_token`：pan-302 Bearer Token，优先支持直接粘贴现有 Token。
- `pan302_username`：可选，如果后续希望插件自动登录 pan-302。
- `pan302_password`：可选，如果后续希望插件自动登录 pan-302。
- `callback_token`：pan-302 回调到 MoviePilot 插件时使用的简单校验 Token。
- `notify_on_callback`：收到 pan-302 回调后是否在 MoviePilot 内发通知。

### 插件详情页

详情页显示：

- pan-302 地址。
- 连接状态。
- pan-302 版本信息。
- 最近一次回调记录。
- 最近一次执行动作结果。

详情页按钮建议：

- 测试连接。
- 获取 pan-302 状态。
- 执行全部 STRM 同步。
- 执行指定 STRM 同步。
- 执行指定转移规则。
- 查询传输任务状态。

### 插件 API

MoviePilot 插件 API 会注册在：

```text
/api/v1/plugin/Pan302Bridge/<path>
```

建议第一版暴露这些接口：

```text
GET  /api/v1/plugin/Pan302Bridge/status
POST /api/v1/plugin/Pan302Bridge/test_connection
POST /api/v1/plugin/Pan302Bridge/trigger_strm_sync
POST /api/v1/plugin/Pan302Bridge/trigger_transfer_rule
POST /api/v1/plugin/Pan302Bridge/pan302_callback
```

`pan302_callback` 给 pan-302 调用，用来通知 MoviePilot：

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

事件名建议先支持：

```text
share_transfer_completed
offline_move_completed
strm_generated
strm_sync_completed
transfer_failed
```

收到回调后：

- 校验 `token`。
- 保存最近回调记录到插件数据。
- 如果开启通知，通过 `self.post_message()` 发 MoviePilot 通知。
- 后续可扩展为触发 MoviePilot 媒体库刷新或工作流。

## pan-302 可调用接口

pan-302 API 基础路径为：

```text
{pan302_url}/api
```

除 `/api/version`、`/api/302`、登录状态等少数接口外，大多数接口需要：

```text
Authorization: Bearer <pan302_token>
```

第一版建议优先使用这些接口：

```text
GET  /api/version
GET  /api/stats
GET  /api/health
GET  /api/transfer/status
GET  /api/transfer/logs
GET  /api/transfer/rules
POST /api/transfer/rules/trigger/:name
POST /api/transfer/share-receive
POST /api/transfer/offline-add
GET  /api/transfer/offline-tasks
POST /api/transfer/offline-move-completed
GET  /api/strm/items
POST /api/strm/sync
POST /api/strm/sync/:name
GET  /api/strm/status
```

其中分享转存接口：

```text
POST /api/transfer/share-receive
```

请求体按 pan-302 当前代码实现确认，预计至少需要：

```json
{
  "driverType": "115",
  "shareUrl": "https://115.com/s/xxxx",
  "receiveCode": "",
  "dstID": "/转存监控"
}
```

执行转移规则：

```text
POST /api/transfer/rules/trigger/:name
```

执行 STRM：

```text
POST /api/strm/sync
POST /api/strm/sync/:name
```

## 插件骨架示例

```python
from typing import Any, Dict, List, Tuple
import requests

from app.plugins import _PluginBase


class Pan302Bridge(_PluginBase):
    plugin_name = "Pan302 联动"
    plugin_desc = "在 MoviePilot 中联动 pan-302 的分享转存、离线移动、STRM 和转移整理。"
    plugin_icon = "Moviepilot_A.png"
    plugin_version = "1.0.0"
    plugin_author = "czerov"
    author_url = "https://github.com/czerov"
    plugin_config_prefix = "pan302bridge_"
    plugin_order = 50
    auth_level = 1

    _enabled = False
    _pan302_url = ""
    _pan302_token = ""
    _callback_token = ""
    _notify_on_callback = True

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._pan302_url = (config.get("pan302_url") or "").rstrip("/")
        self._pan302_token = config.get("pan302_token") or ""
        self._callback_token = config.get("callback_token") or ""
        self._notify_on_callback = bool(config.get("notify_on_callback", True))

    def get_state(self) -> bool:
        return self._enabled

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询 pan-302 联动状态",
            },
            {
                "path": "/test_connection",
                "endpoint": self.api_test_connection,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "测试 pan-302 连接",
            },
            {
                "path": "/trigger_strm_sync",
                "endpoint": self.api_trigger_strm_sync,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "触发 pan-302 STRM 同步",
            },
            {
                "path": "/trigger_transfer_rule",
                "endpoint": self.api_trigger_transfer_rule,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "触发 pan-302 转移规则",
            },
            {
                "path": "/pan302_callback",
                "endpoint": self.api_pan302_callback,
                "methods": ["POST"],
                "auth": "apikey",
                "summary": "接收 pan-302 回调",
            },
        ]

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self._pan302_token:
            headers["Authorization"] = f"Bearer {self._pan302_token}"
        return headers

    def _pan302_get(self, path: str):
        url = f"{self._pan302_url}{path}"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _pan302_post(self, path: str, payload: dict | None = None):
        url = f"{self._pan302_url}{path}"
        resp = requests.post(url, json=payload or {}, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def api_status(self):
        return {
            "enabled": self._enabled,
            "pan302_url": self._pan302_url,
            "has_token": bool(self._pan302_token),
        }

    def api_test_connection(self):
        if not self._pan302_url:
            return {"success": False, "message": "pan-302 地址未配置"}
        try:
            version = self._pan302_get("/api/version")
            self.save_data("last_connection", version)
            return {"success": True, "data": version}
        except Exception as err:
            return {"success": False, "message": str(err)}

    def api_trigger_strm_sync(self, data: dict = None):
        data = data or {}
        name = data.get("name")
        path = f"/api/strm/sync/{name}" if name else "/api/strm/sync"
        result = self._pan302_post(path)
        self.save_data("last_action", {"action": "strm_sync", "result": result})
        return {"success": True, "data": result}

    def api_trigger_transfer_rule(self, data: dict = None):
        data = data or {}
        name = data.get("name")
        if not name:
            return {"success": False, "message": "缺少规则名称"}
        result = self._pan302_post(f"/api/transfer/rules/trigger/{name}")
        self.save_data("last_action", {"action": "transfer_rule", "name": name, "result": result})
        return {"success": True, "data": result}

    def api_pan302_callback(self, data: dict = None):
        data = data or {}
        if self._callback_token and data.get("token") != self._callback_token:
            return {"success": False, "message": "callback token 不正确"}

        self.save_data("last_callback", data)

        if self._notify_on_callback:
            self.post_message(
                title=data.get("title") or "pan-302 任务完成",
                text=data.get("text") or str(data),
            )

        return {"success": True}

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用 pan-302 联动",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 8},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "pan302_url",
                                            "label": "pan-302 地址",
                                            "placeholder": "http://192.168.6.36:3000",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "pan302_token",
                                            "label": "pan-302 Token",
                                            "type": "password",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "callback_token",
                                            "label": "回调校验 Token",
                                            "type": "password",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify_on_callback",
                                            "label": "收到 pan-302 回调后发送 MoviePilot 通知",
                                        },
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ], {
            "enabled": False,
            "pan302_url": "",
            "pan302_token": "",
            "callback_token": "",
            "notify_on_callback": True,
        }

    def get_page(self) -> List[dict]:
        last_callback = self.get_data("last_callback") or {}
        last_action = self.get_data("last_action") or {}
        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": f"pan-302 地址：{self._pan302_url or '未配置'}",
                },
            },
            {
                "component": "VAlert",
                "props": {
                    "type": "success",
                    "variant": "tonal",
                    "text": f"最近回调：{last_callback}",
                },
            },
            {
                "component": "VAlert",
                "props": {
                    "type": "secondary",
                    "variant": "tonal",
                    "text": f"最近动作：{last_action}",
                },
            },
        ]

    def stop_service(self):
        pass
```

## package.v2.json 示例

```json
{
  "Pan302Bridge": {
    "name": "Pan302 联动",
    "description": "在 MoviePilot 中联动 pan-302 的分享转存、离线移动、STRM 和转移整理。",
    "labels": "网盘,STRM,MoviePilot,pan-302",
    "version": "1.0.0",
    "icon": "Moviepilot_A.png",
    "author": "czerov",
    "level": 1,
    "history": {
      "v1.0.0": "新增 pan-302 联动插件，支持连接测试、STRM 同步、转移规则触发和任务回调。"
    }
  }
}
```

## 后续增强方向

第一版跑通后，再考虑这些增强：

- 在 pan-302 增加专门的 MoviePilot 回调配置，不复用通用通知。
- pan-302 分享转存完成后回调插件，并由插件触发 MoviePilot 媒体库刷新。
- pan-302 STRM 生成完成后回调插件，并由插件通知用户。
- 插件实现 `get_actions()`，让 MoviePilot 工作流可直接调用 pan-302。
- 插件实现 `get_service()`，定时检查 pan-302 任务状态。
- 如果需要完整控制台，再使用 MoviePilot Vue 联邦组件做侧栏页面。

## 给新项目 Codex 的提示词

请基于 MoviePilot V2 插件规范，开发一个名为 `Pan302Bridge` 的插件，用于对接 pan-302 项目。

要求：

1. 插件目录为 `plugins.v2/pan302bridge/`，主类为 `Pan302Bridge`，继承 `app.plugins._PluginBase`。
2. 使用 Vuetify JSON 实现配置页和详情页，暂时不要使用 Vue 联邦组件。
3. 配置项包括：启用开关、pan-302 地址、pan-302 Token、回调校验 Token、收到回调后是否发送 MoviePilot 通知。
4. 插件需要通过 `requests` 调用 pan-302 API，统一加 `Authorization: Bearer <token>`。
5. 实现 `get_api()`，至少暴露：
   - `GET /status`
   - `POST /test_connection`
   - `POST /trigger_strm_sync`
   - `POST /trigger_transfer_rule`
   - `POST /pan302_callback`
6. `test_connection` 调用 pan-302 的 `/api/version`。
7. `trigger_strm_sync` 调用 pan-302 的 `/api/strm/sync` 或 `/api/strm/sync/:name`。
8. `trigger_transfer_rule` 调用 pan-302 的 `/api/transfer/rules/trigger/:name`。
9. `pan302_callback` 校验 callback token，保存最近回调记录，并在开启通知时调用 `self.post_message()`。
10. 使用 `_PluginBase` 提供的 `save_data()`、`get_data()`、`update_config()`，避免自己写额外存储。
11. 同步更新 `package.v2.json`，版本号必须和 `plugin_version` 一致。
12. 完成后运行 Python 编译检查：
    - `python -m py_compile plugins.v2/pan302bridge/__init__.py`
    - `python -m compileall plugins.v2/pan302bridge`

验收标准：

- 插件可以在 MoviePilot 插件市场/本地插件中加载。
- 配置页可以保存 pan-302 地址和 Token。
- 点击测试连接可以拿到 pan-302 版本信息。
- 可以从 MoviePilot 插件触发 pan-302 STRM 同步。
- 可以从 MoviePilot 插件触发 pan-302 指定转移规则。
- pan-302 可以 POST 到插件的 `/pan302_callback`，MoviePilot 能收到并发通知。
