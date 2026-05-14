from datetime import datetime
from time import sleep
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.plugins import _PluginBase

try:
    from app.core.module import ModuleManager
except Exception:  # pragma: no cover - MoviePilot runtime provides app.core.module.
    ModuleManager = None

try:
    from app.log import logger
except Exception:  # pragma: no cover - MoviePilot runtime provides app.log.
    logger = None


class Pan302Bridge(_PluginBase):
    plugin_name = "Pan302 联动"
    plugin_desc = "接收 pan-302 回调，并刷新 Emby 或 MoviePilot 媒体服务器。"
    plugin_icon = "Moviepilot_A.png"
    plugin_version = "1.4.0"
    plugin_author = "czerov"
    author_url = "https://github.com/czerov"
    plugin_config_prefix = "pan302bridge_"
    plugin_order = 50
    auth_level = 1

    _enabled = False
    _refresh_mediaserver = True
    _refresh_events = "strm_generated,strm_sync_completed,share_transfer_completed,offline_move_completed"
    _refresh_delay = 0
    _notify_on_callback = True
    _emby_url = ""
    _emby_api_key = ""

    def init_plugin(self, config: Optional[dict] = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._notify_on_callback = bool(config.get("notify_on_callback", True))
        self._emby_url = self._normalize_base_url(config.get("emby_url"))
        self._emby_api_key = (config.get("emby_api_key") or "").strip()

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_base_url(url: Optional[str]) -> str:
        return (url or "").strip().rstrip("/")

    @staticmethod
    def _split_config_values(value: str) -> List[str]:
        if not value:
            return []
        normalized = str(value).replace("\n", ",").replace(";", ",")
        return [item.strip() for item in normalized.split(",") if item.strip()]

    @staticmethod
    def _compact(value: Any) -> str:
        if value in (None, "", {}, []):
            return "暂无"
        text = str(value)
        if len(text) > 240:
            return text[:237] + "..."
        return text

    @staticmethod
    def _error_message(err: Exception) -> str:
        if isinstance(err, HTTPError):
            try:
                detail = err.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            return "HTTP %s: %s" % (err.code, detail or err.reason)
        return str(err)

    def _log_warning(self, message: str):
        if logger:
            logger.warning(message)

    def _save_action(self, action: str, success: bool, data: Optional[dict] = None):
        payload = {
            "action": action,
            "success": success,
            "time": self._now(),
        }
        if data:
            payload.update(data)
        self.save_data("last_action", payload)

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
                "path": "/refresh_mediaserver",
                "endpoint": self.api_refresh_mediaserver,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "刷新 MoviePilot 媒体服务器",
            },
            {
                "path": "/pan302_callback",
                "endpoint": self.api_pan302_callback,
                "methods": ["POST"],
                "auth": "apikey",
                "summary": "接收 pan-302 回调",
            },
        ]

    def api_status(self) -> Dict[str, Any]:
        return {
            "success": True,
            "enabled": self._enabled,
            "refresh_mediaserver": self._refresh_mediaserver,
            "refresh_events": self._split_config_values(self._refresh_events),
            "notify_on_callback": self._notify_on_callback,
            "emby_url": self._emby_url,
            "has_emby_api_key": bool(self._emby_api_key),
            "last_callback": self.get_data("last_callback"),
            "last_mediaserver_refresh": self.get_data("last_mediaserver_refresh"),
            "last_action": self.get_data("last_action"),
        }

    def api_refresh_mediaserver(self, data: Optional[dict] = None) -> Dict[str, Any]:
        result = self._refresh_preferred_mediaserver(reason="manual", callback=data or {})
        self._save_action("refresh_mediaserver", bool(result.get("success")), result)
        return result

    def api_pan302_callback(self, data: Optional[dict] = None) -> Dict[str, Any]:
        data = data or {}
        callback = dict(data)
        callback["success"] = True
        callback.setdefault("time", self._now())

        refresh_result = self._refresh_from_callback(callback)
        callback["mediaserver_refresh"] = refresh_result
        self.save_data("last_callback", callback)

        if self._notify_on_callback:
            self._notify_callback(callback)

        return {
            "success": True,
            "mediaserver_refresh": refresh_result,
        }

    def _refresh_from_callback(self, callback: Dict[str, Any]) -> Dict[str, Any]:
        event = (callback.get("event") or "").strip()
        if not self._refresh_mediaserver:
            return self._save_mediaserver_refresh(
                {
                    "success": True,
                    "skipped": True,
                    "reason": "refresh_mediaserver_disabled",
                    "event": event,
                    "time": self._now(),
                },
                save_action=False,
            )

        refresh_events = self._split_config_values(self._refresh_events)
        if refresh_events and event not in refresh_events:
            return self._save_mediaserver_refresh(
                {
                    "success": True,
                    "skipped": True,
                    "reason": "event_not_matched",
                    "event": event,
                    "refresh_events": refresh_events,
                    "time": self._now(),
                },
                save_action=False,
            )

        result = self._refresh_preferred_mediaserver(reason="pan302_callback", callback=callback)
        self._save_action("refresh_mediaserver", bool(result.get("success")), result)
        return result

    def _refresh_preferred_mediaserver(
        self,
        reason: str,
        callback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self._emby_url and self._emby_api_key:
            return self._refresh_emby(reason=reason, callback=callback)
        if self._emby_url or self._emby_api_key:
            result = {
                "success": False,
                "target": "emby",
                "reason": reason,
                "event": (callback or {}).get("event"),
                "time": self._now(),
                "message": "Emby 地址和 API Key 需要同时填写",
            }
            return self._save_mediaserver_refresh(result)
        return self._refresh_moviepilot_mediaserver(reason=reason, callback=callback)

    def _emby_endpoint(self, path: str) -> str:
        endpoint = path
        if self._emby_url.lower().endswith("/emby") and endpoint.startswith("/emby/"):
            endpoint = endpoint[len("/emby"):]
        return "%s%s" % (self._emby_url, endpoint)

    def _refresh_emby(
        self,
        reason: str,
        callback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        event = (callback or {}).get("event")
        result: Dict[str, Any] = {
            "success": False,
            "target": "emby",
            "reason": reason,
            "event": event,
            "time": self._now(),
        }

        if self._refresh_delay > 0:
            sleep(min(self._refresh_delay, 300))

        try:
            query = urlencode({"api_key": self._emby_api_key})
            url = "%s?%s" % (self._emby_endpoint("/emby/Library/Refresh"), query)
            request = Request(
                url=url,
                data=b"",
                method="POST",
                headers={
                    "Accept": "application/json",
                    "X-Emby-Token": self._emby_api_key,
                },
            )
            with urlopen(request, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                result.update(
                    {
                        "success": True,
                        "status_code": resp.status,
                        "body": body,
                    }
                )
        except Exception as err:
            result["message"] = self._error_message(err)

        return self._save_mediaserver_refresh(result)

    def _refresh_moviepilot_mediaserver(
        self,
        reason: str,
        callback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        event = (callback or {}).get("event")
        result: Dict[str, Any] = {
            "success": False,
            "target": "moviepilot",
            "reason": reason,
            "event": event,
            "time": self._now(),
        }

        if ModuleManager is None:
            result["message"] = "当前 MoviePilot 运行环境无法导入 ModuleManager"
            return self._save_mediaserver_refresh(result)

        if self._refresh_delay > 0:
            sleep(min(self._refresh_delay, 300))

        refreshed = []
        errors = []
        try:
            modules = list(ModuleManager().get_running_modules("refresh_root_library") or [])
            if not modules:
                result["message"] = "未找到已启用且支持刷新的 MoviePilot 媒体服务器模块"
                return self._save_mediaserver_refresh(result)

            for module in modules:
                module_name = module.__class__.__name__
                try:
                    module_result = module.refresh_root_library()
                    refreshed.append(
                        {
                            "module": module_name,
                            "result": module_result,
                        }
                    )
                except Exception as err:
                    errors.append(
                        {
                            "module": module_name,
                            "message": self._error_message(err),
                        }
                    )

            result.update(
                {
                    "success": not bool(errors),
                    "refreshed": refreshed,
                    "errors": errors,
                }
            )
        except Exception as err:
            result["message"] = self._error_message(err)

        return self._save_mediaserver_refresh(result)

    def _save_mediaserver_refresh(self, result: Dict[str, Any], save_action: bool = True) -> Dict[str, Any]:
        self.save_data("last_mediaserver_refresh", result)
        if save_action and result.get("message"):
            self._log_warning("MoviePilot 媒体服务器刷新失败：%s" % result.get("message"))
        return result

    def _notify_callback(self, data: Dict[str, Any]):
        title = data.get("title") or "pan-302 任务通知"
        text = data.get("text") or data.get("event") or str(data)
        refresh_result = data.get("mediaserver_refresh") or {}
        if refresh_result and not refresh_result.get("skipped"):
            refresh_state = "成功" if refresh_result.get("success") else "失败"
            refresh_target = "Emby" if refresh_result.get("target") == "emby" else "MoviePilot 媒体服务器"
            text = "%s\n%s 刷新：%s" % (text, refresh_target, refresh_state)
        try:
            self.post_message(title=title, text=text)
        except Exception as err:
            self._log_warning("pan-302 回调通知发送失败：%s" % self._error_message(err))

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
                                "props": {"cols": 12, "md": 6},
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
                                "props": {"cols": 12, "md": 6},
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
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "emby_url",
                                            "label": "Emby 地址（可选）",
                                            "placeholder": "http://192.168.6.36:8096",
                                            "clearable": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "emby_api_key",
                                            "label": "Emby API Key（可选）",
                                            "type": "password",
                                            "clearable": True,
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
            "notify_on_callback": True,
            "emby_url": "",
            "emby_api_key": "",
        }

    def get_page(self) -> List[dict]:
        last_callback = self.get_data("last_callback") or {}
        last_refresh = self.get_data("last_mediaserver_refresh") or {}
        last_action = self.get_data("last_action") or {}

        return [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info" if self._refresh_mediaserver else "warning",
                                    "variant": "tonal",
                                    "text": "刷新目标：%s"
                                    % ("直连 Emby" if self._emby_url and self._emby_api_key else "MoviePilot 媒体服务器"),
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VSheet",
                                "props": {"class": "d-flex flex-wrap ga-2"},
                                "content": [
                                    self._api_button(
                                        "刷新媒体服务器",
                                        "plugin/Pan302Bridge/refresh_mediaserver",
                                        "primary",
                                    )
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "success",
                                    "variant": "tonal",
                                    "text": "最近回调：%s" % self._compact(last_callback),
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "text": "最近刷新：%s" % self._compact(last_refresh),
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "secondary",
                                    "variant": "tonal",
                                    "text": "最近动作：%s" % self._compact(last_action),
                                },
                            }
                        ],
                    },
                ],
            }
        ]

    @staticmethod
    def _api_button(text: str, api: str, color: str, params: Optional[dict] = None) -> dict:
        event = {
            "api": api,
            "method": "post",
        }
        if params:
            event["params"] = params
        return {
            "component": "VBtn",
            "props": {
                "color": color,
                "variant": "tonal",
                "text": text,
            },
            "events": {
                "click": event,
            },
        }

    def stop_service(self):
        pass
