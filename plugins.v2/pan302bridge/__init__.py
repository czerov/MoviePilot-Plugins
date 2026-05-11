from datetime import datetime
from time import sleep
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

from app.plugins import _PluginBase

try:
    from app.log import logger
except Exception:  # pragma: no cover - MoviePilot runtime provides app.log.
    logger = None


class Pan302Bridge(_PluginBase):
    plugin_name = "Pan302 联动"
    plugin_desc = "接收 pan-302 回调，并在 STRM 生成后刷新 Emby 媒体库。"
    plugin_icon = "Moviepilot_A.png"
    plugin_version = "1.1.0"
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
    _quick_strm_name = ""
    _quick_transfer_rule_name = ""
    _auto_refresh_emby = True
    _emby_url = ""
    _emby_api_key = ""
    _emby_library_ids = ""
    _emby_refresh_events = "strm_generated,strm_sync_completed,share_transfer_completed,offline_move_completed"
    _emby_refresh_delay = 0

    def init_plugin(self, config: Optional[dict] = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._pan302_url = self._normalize_base_url(config.get("pan302_url"))
        self._pan302_token = (config.get("pan302_token") or "").strip()
        self._callback_token = (config.get("callback_token") or "").strip()
        self._notify_on_callback = bool(config.get("notify_on_callback", True))
        self._quick_strm_name = (config.get("quick_strm_name") or "").strip()
        self._quick_transfer_rule_name = (config.get("quick_transfer_rule_name") or "").strip()
        self._auto_refresh_emby = bool(config.get("auto_refresh_emby", True))
        self._emby_url = self._normalize_base_url(config.get("emby_url"))
        self._emby_api_key = (config.get("emby_api_key") or "").strip()
        self._emby_library_ids = (config.get("emby_library_ids") or "").strip()
        self._emby_refresh_events = (
            config.get("emby_refresh_events")
            or "strm_generated,strm_sync_completed,share_transfer_completed,offline_move_completed"
        ).strip()
        try:
            self._emby_refresh_delay = max(0, int(config.get("emby_refresh_delay") or 0))
        except (TypeError, ValueError):
            self._emby_refresh_delay = 0

    @staticmethod
    def _normalize_base_url(url: Optional[str]) -> str:
        return (url or "").strip().rstrip("/")

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _json_or_text(resp: requests.Response) -> Any:
        try:
            return resp.json()
        except ValueError:
            return {"text": resp.text}

    @staticmethod
    def _path_segment(value: str) -> str:
        return quote(str(value).strip(), safe="")

    @staticmethod
    def _split_config_values(value: str) -> List[str]:
        if not value:
            return []
        normalized = str(value).replace("\n", ",").replace(";", ",")
        return [item.strip() for item in normalized.split(",") if item.strip()]

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._pan302_token:
            headers["Authorization"] = "Bearer %s" % self._pan302_token
        return headers

    def _ensure_configured(self) -> Optional[Dict[str, Any]]:
        if not self._pan302_url:
            return {"success": False, "message": "pan-302 地址未配置"}
        return None

    def _pan302_request(
        self,
        method: str,
        path: str,
        payload: Optional[dict] = None,
        timeout: int = 15,
    ) -> Any:
        url = "%s%s" % (self._pan302_url, path)
        resp = requests.request(
            method=method.upper(),
            url=url,
            json=payload if payload is not None else None,
            headers=self._headers(),
            timeout=timeout,
        )
        resp.raise_for_status()
        return self._json_or_text(resp)

    def _pan302_get(self, path: str, timeout: int = 15) -> Any:
        return self._pan302_request("GET", path, timeout=timeout)

    def _pan302_post(self, path: str, payload: Optional[dict] = None, timeout: int = 30) -> Any:
        return self._pan302_request("POST", path, payload=payload or {}, timeout=timeout)

    def _emby_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._emby_api_key:
            headers["X-Emby-Token"] = self._emby_api_key
        return headers

    def _emby_endpoint(self, path: str) -> str:
        endpoint = path
        if self._emby_url.lower().endswith("/emby") and endpoint.startswith("/emby/"):
            endpoint = endpoint[len("/emby"):]
        return "%s%s" % (self._emby_url, endpoint)

    def _emby_request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        payload: Optional[dict] = None,
        timeout: int = 30,
    ) -> Any:
        if not self._emby_url:
            raise ValueError("Emby 地址未配置")
        if not self._emby_api_key:
            raise ValueError("Emby API Key 未配置")

        request_params = dict(params or {})
        request_params["api_key"] = self._emby_api_key
        resp = requests.request(
            method=method.upper(),
            url=self._emby_endpoint(path),
            params=request_params,
            json=payload if payload is not None else None,
            headers=self._emby_headers(),
            timeout=timeout,
        )
        resp.raise_for_status()
        data = self._json_or_text(resp)
        if data in ({}, {"text": ""}):
            return {"status_code": resp.status_code}
        return data

    def _emby_get(self, path: str, params: Optional[dict] = None, timeout: int = 15) -> Any:
        return self._emby_request("GET", path, params=params, timeout=timeout)

    def _emby_post(
        self,
        path: str,
        params: Optional[dict] = None,
        payload: Optional[dict] = None,
        timeout: int = 30,
    ) -> Any:
        return self._emby_request("POST", path, params=params, payload=payload, timeout=timeout)

    def _save_action(self, action: str, success: bool, data: Optional[dict] = None):
        payload = {
            "action": action,
            "success": success,
            "time": self._now(),
        }
        if data:
            payload.update(data)
        self.save_data("last_action", payload)

    @staticmethod
    def _error_message(err: Exception) -> str:
        if isinstance(err, requests.HTTPError) and err.response is not None:
            status = err.response.status_code
            try:
                detail = err.response.json()
            except ValueError:
                detail = err.response.text
            return "HTTP %s: %s" % (status, detail)
        return str(err)

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
                "path": "/pan302_status",
                "endpoint": self.api_pan302_status,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "获取 pan-302 状态",
            },
            {
                "path": "/transfer_status",
                "endpoint": self.api_transfer_status,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "查询 pan-302 传输任务状态",
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
            {
                "path": "/test_emby",
                "endpoint": self.api_test_emby,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "测试 Emby 连接",
            },
            {
                "path": "/refresh_emby",
                "endpoint": self.api_refresh_emby,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "刷新 Emby 媒体库",
            },
        ]

    def api_status(self) -> Dict[str, Any]:
        return {
            "success": True,
            "enabled": self._enabled,
            "pan302_url": self._pan302_url,
            "has_token": bool(self._pan302_token),
            "notify_on_callback": self._notify_on_callback,
            "auto_refresh_emby": self._auto_refresh_emby,
            "emby_url": self._emby_url,
            "has_emby_api_key": bool(self._emby_api_key),
            "emby_library_ids": self._split_config_values(self._emby_library_ids),
            "emby_refresh_events": self._split_config_values(self._emby_refresh_events),
            "last_connection": self.get_data("last_connection"),
            "last_pan302_status": self.get_data("last_pan302_status"),
            "last_emby_test": self.get_data("last_emby_test"),
            "last_emby_refresh": self.get_data("last_emby_refresh"),
            "last_action": self.get_data("last_action"),
            "last_callback": self.get_data("last_callback"),
        }

    def api_test_connection(self) -> Dict[str, Any]:
        not_configured = self._ensure_configured()
        if not_configured:
            return not_configured

        try:
            version = self._pan302_get("/api/version", timeout=10)
            result = {"version": version, "time": self._now()}
            self.save_data("last_connection", result)
            self._save_action("test_connection", True, {"result": version})
            return {"success": True, "data": version}
        except Exception as err:
            message = self._error_message(err)
            self._save_action("test_connection", False, {"message": message})
            self._log_warning("pan-302 连接测试失败：%s" % message)
            return {"success": False, "message": message}

    def api_pan302_status(self) -> Dict[str, Any]:
        not_configured = self._ensure_configured()
        if not_configured:
            return not_configured

        data: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        endpoints = {
            "version": "/api/version",
            "health": "/api/health",
            "stats": "/api/stats",
            "transfer_status": "/api/transfer/status",
            "strm_status": "/api/strm/status",
        }

        for key, path in endpoints.items():
            try:
                data[key] = self._pan302_get(path, timeout=10)
            except Exception as err:
                errors[key] = self._error_message(err)

        payload = {"time": self._now(), "data": data, "errors": errors}
        self.save_data("last_pan302_status", payload)
        self._save_action("pan302_status", not bool(errors), payload)
        return {"success": not bool(errors), "data": data, "errors": errors}

    def api_transfer_status(self) -> Dict[str, Any]:
        not_configured = self._ensure_configured()
        if not_configured:
            return not_configured

        try:
            result = self._pan302_get("/api/transfer/status", timeout=15)
            self._save_action("transfer_status", True, {"result": result})
            return {"success": True, "data": result}
        except Exception as err:
            message = self._error_message(err)
            self._save_action("transfer_status", False, {"message": message})
            return {"success": False, "message": message}

    def api_test_emby(self) -> Dict[str, Any]:
        try:
            system_info = self._emby_get("/emby/System/Info", timeout=10)
            folders = self._emby_get("/emby/Library/SelectableMediaFolders", timeout=10)
            result = {
                "time": self._now(),
                "system": system_info,
                "folders": folders,
            }
            self.save_data("last_emby_test", result)
            self._save_action("test_emby", True, {"result": result})
            return {"success": True, "data": result}
        except Exception as err:
            message = self._error_message(err)
            result = {
                "success": False,
                "time": self._now(),
                "message": message,
            }
            self.save_data("last_emby_test", result)
            self._save_action("test_emby", False, {"message": message})
            return {"success": False, "message": message}

    def api_refresh_emby(self, data: Optional[dict] = None) -> Dict[str, Any]:
        data = data or {}
        library_ids = data.get("library_ids")
        result = self._refresh_emby_libraries(
            reason="manual",
            library_ids=library_ids,
        )
        return result

    def api_trigger_strm_sync(self, data: Optional[dict] = None) -> Dict[str, Any]:
        not_configured = self._ensure_configured()
        if not_configured:
            return not_configured

        data = data or {}
        name = (data.get("name") or self._quick_strm_name or "").strip()
        path = "/api/strm/sync/%s" % self._path_segment(name) if name else "/api/strm/sync"

        try:
            result = self._pan302_post(path, timeout=60)
            self._save_action("strm_sync", True, {"name": name, "result": result})
            return {"success": True, "data": result}
        except Exception as err:
            message = self._error_message(err)
            self._save_action("strm_sync", False, {"name": name, "message": message})
            return {"success": False, "message": message}

    def api_trigger_transfer_rule(self, data: Optional[dict] = None) -> Dict[str, Any]:
        not_configured = self._ensure_configured()
        if not_configured:
            return not_configured

        data = data or {}
        name = (data.get("name") or self._quick_transfer_rule_name or "").strip()
        if not name:
            return {"success": False, "message": "缺少规则名称"}

        try:
            path = "/api/transfer/rules/trigger/%s" % self._path_segment(name)
            result = self._pan302_post(path, timeout=60)
            self._save_action("transfer_rule", True, {"name": name, "result": result})
            return {"success": True, "data": result}
        except Exception as err:
            message = self._error_message(err)
            self._save_action("transfer_rule", False, {"name": name, "message": message})
            return {"success": False, "message": message}

    def api_pan302_callback(self, data: Optional[dict] = None) -> Dict[str, Any]:
        data = data or {}
        if self._callback_token and data.get("token") != self._callback_token:
            self.save_data(
                "last_callback",
                {
                    "success": False,
                    "message": "callback token 不正确",
                    "time": self._now(),
                    "event": data.get("event"),
                },
            )
            return {"success": False, "message": "callback token 不正确"}

        callback = dict(data)
        callback["success"] = True
        callback.setdefault("time", self._now())
        emby_refresh = self._refresh_emby_from_callback(callback)
        callback["emby_refresh"] = emby_refresh
        self.save_data("last_callback", callback)

        if self._notify_on_callback:
            self._notify_callback(callback)

        return {"success": True, "emby_refresh": emby_refresh}

    def _refresh_emby_from_callback(self, callback: Dict[str, Any]) -> Dict[str, Any]:
        event = (callback.get("event") or "").strip()
        if not self._auto_refresh_emby:
            return self._save_emby_refresh(
                {
                    "success": True,
                    "skipped": True,
                    "reason": "auto_refresh_emby_disabled",
                    "event": event,
                    "time": self._now(),
                },
                save_action=False,
            )

        refresh_events = self._split_config_values(self._emby_refresh_events)
        if refresh_events and event not in refresh_events:
            return self._save_emby_refresh(
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

        return self._refresh_emby_libraries(reason="pan302_callback", callback=callback)

    def _refresh_emby_libraries(
        self,
        reason: str,
        callback: Optional[Dict[str, Any]] = None,
        library_ids: Optional[Any] = None,
    ) -> Dict[str, Any]:
        event = (callback or {}).get("event")
        result: Dict[str, Any] = {
            "success": False,
            "reason": reason,
            "event": event,
            "time": self._now(),
        }

        if not self._emby_url:
            result["message"] = "Emby 地址未配置"
            return self._save_emby_refresh(result)
        if not self._emby_api_key:
            result["message"] = "Emby API Key 未配置"
            return self._save_emby_refresh(result)

        if self._emby_refresh_delay > 0:
            sleep(min(self._emby_refresh_delay, 300))

        ids_value = library_ids if library_ids is not None else self._emby_library_ids
        if isinstance(ids_value, list):
            ids = [str(item).strip() for item in ids_value if str(item).strip()]
        else:
            ids = self._split_config_values(ids_value or "")

        try:
            if ids:
                refreshed = []
                params = {
                    "Recursive": "true",
                    "ImageRefreshMode": "Default",
                    "MetadataRefreshMode": "Default",
                    "ReplaceAllImages": "false",
                    "ReplaceAllMetadata": "false",
                }
                for library_id in ids:
                    refreshed.append(
                        {
                            "library_id": library_id,
                            "result": self._emby_post(
                                "/emby/Items/%s/Refresh" % self._path_segment(library_id),
                                params=params,
                                timeout=30,
                            ),
                        }
                    )
                result.update(
                    {
                        "success": True,
                        "mode": "libraries",
                        "library_ids": ids,
                        "result": refreshed,
                    }
                )
            else:
                result.update(
                    {
                        "success": True,
                        "mode": "all",
                        "result": self._emby_post("/emby/Library/Refresh", timeout=30),
                    }
                )
        except Exception as err:
            result["message"] = self._error_message(err)

        return self._save_emby_refresh(result)

    def _save_emby_refresh(self, result: Dict[str, Any], save_action: bool = True) -> Dict[str, Any]:
        self.save_data("last_emby_refresh", result)
        if save_action:
            self._save_action("emby_refresh", bool(result.get("success")), result)
        return result

    def _notify_callback(self, data: Dict[str, Any]):
        title = data.get("title") or "pan-302 任务通知"
        text = data.get("text") or data.get("event") or str(data)
        emby_refresh = data.get("emby_refresh") or {}
        if emby_refresh and not emby_refresh.get("skipped"):
            refresh_state = "成功" if emby_refresh.get("success") else "失败"
            text = "%s\nEmby 刷库：%s" % (text, refresh_state)
        try:
            self.post_message(title=title, text=text)
        except Exception as err:
            self._log_warning("pan-302 回调通知发送失败：%s" % self._error_message(err))

    def _log_warning(self, message: str):
        if logger:
            logger.warning(message)

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
                                            "clearable": True,
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
                                            "model": "callback_token",
                                            "label": "回调校验 Token",
                                            "type": "password",
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
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "auto_refresh_emby",
                                            "label": "pan-302 回调后刷新 Emby 媒体库",
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
                                            "label": "Emby 地址",
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
                                            "label": "Emby API Key",
                                            "type": "password",
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
                                            "model": "emby_library_ids",
                                            "label": "Emby 媒体库 ID",
                                            "placeholder": "多个用英文逗号分隔，留空刷新全部",
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
                                            "model": "emby_refresh_delay",
                                            "label": "Emby 刷库延迟秒数",
                                            "type": "number",
                                            "min": 0,
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
                                            "model": "emby_refresh_events",
                                            "label": "触发 Emby 刷库的回调事件",
                                            "placeholder": "strm_generated,strm_sync_completed",
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
                                            "model": "quick_strm_name",
                                            "label": "快捷 STRM 名称",
                                            "placeholder": "留空则执行全部 STRM 同步",
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
                                            "model": "quick_transfer_rule_name",
                                            "label": "快捷转移规则名称",
                                            "placeholder": "详情页按钮使用",
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
            "pan302_url": "",
            "pan302_token": "",
            "callback_token": "",
            "notify_on_callback": True,
            "auto_refresh_emby": True,
            "emby_url": "",
            "emby_api_key": "",
            "emby_library_ids": "",
            "emby_refresh_events": "strm_generated,strm_sync_completed,share_transfer_completed,offline_move_completed",
            "emby_refresh_delay": 0,
            "quick_strm_name": "",
            "quick_transfer_rule_name": "",
        }

    def get_page(self) -> List[dict]:
        last_connection = self.get_data("last_connection") or {}
        last_status = self.get_data("last_pan302_status") or {}
        last_emby_refresh = self.get_data("last_emby_refresh") or {}
        last_callback = self.get_data("last_callback") or {}
        last_action = self.get_data("last_action") or {}
        status_type = "success" if last_connection else "warning"
        status_text = "已连接" if last_connection else "未测试"

        return [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 6},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": status_type,
                                    "variant": "tonal",
                                    "text": "pan-302：%s；状态：%s" % (self._pan302_url or "未配置", status_text),
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 6},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "text": "版本信息：%s" % self._compact(last_connection.get("version")),
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info" if self._emby_url else "warning",
                                    "variant": "tonal",
                                    "text": "Emby：%s；回调后刷库：%s"
                                    % (self._emby_url or "未配置", "开启" if self._auto_refresh_emby else "关闭"),
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
                                "content": self._page_buttons(),
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "secondary",
                                    "variant": "tonal",
                                    "text": "最近状态：%s" % self._compact(last_status),
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
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
                        "props": {"cols": 12, "md": 3},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "text": "最近动作：%s" % self._compact(last_action),
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "warning",
                                    "variant": "tonal",
                                    "text": "最近 Emby 刷库：%s" % self._compact(last_emby_refresh),
                                },
                            }
                        ],
                    },
                ],
            }
        ]

    def _page_buttons(self) -> List[dict]:
        buttons = [
            self._api_button("测试连接", "plugin/Pan302Bridge/test_connection", "primary"),
            self._api_button("获取状态", "plugin/Pan302Bridge/pan302_status", "info"),
            self._api_button("全部 STRM 同步", "plugin/Pan302Bridge/trigger_strm_sync", "success"),
            self._api_button("查询传输任务", "plugin/Pan302Bridge/transfer_status", "secondary"),
            self._api_button("测试 Emby", "plugin/Pan302Bridge/test_emby", "primary"),
            self._api_button("刷新 Emby", "plugin/Pan302Bridge/refresh_emby", "warning"),
        ]
        if self._quick_strm_name:
            buttons.append(
                self._api_button(
                    "指定 STRM 同步",
                    "plugin/Pan302Bridge/trigger_strm_sync",
                    "success",
                    {"name": self._quick_strm_name},
                )
            )
        if self._quick_transfer_rule_name:
            buttons.append(
                self._api_button(
                    "执行转移规则",
                    "plugin/Pan302Bridge/trigger_transfer_rule",
                    "warning",
                    {"name": self._quick_transfer_rule_name},
                )
            )
        return buttons

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

    @staticmethod
    def _compact(value: Any) -> str:
        if value in (None, "", {}, []):
            return "暂无"
        text = str(value)
        if len(text) > 240:
            return text[:237] + "..."
        return text

    def stop_service(self):
        pass
