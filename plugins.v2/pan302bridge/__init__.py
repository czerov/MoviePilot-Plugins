import json
import re
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.plugins import _PluginBase

try:
    from app.core.event import Event, eventmanager
    from app.schemas.types import EventType
except Exception:  # pragma: no cover - MoviePilot runtime provides event modules.
    Event = None
    EventType = None
    eventmanager = None

try:
    from app.core.module import ModuleManager
except Exception:  # pragma: no cover - MoviePilot runtime provides app.core.module.
    ModuleManager = None

try:
    from app.log import logger
except Exception:  # pragma: no cover - MoviePilot runtime provides app.log.
    logger = None


def _event_register(event_type):
    if eventmanager and event_type:
        return eventmanager.register(event_type)
    return lambda func: func


class Pan302Bridge(_PluginBase):
    plugin_name = "Pan302 联动"
    plugin_desc = "联动 MoviePilot 与 pan302，支持整理完成上传、分享转存回调和媒体库刷新。"
    plugin_icon = "Moviepilot_A.png"
    plugin_version = "1.6.0"
    plugin_author = "czerov"
    author_url = "https://github.com/czerov"
    plugin_config_prefix = "pan302bridge_"
    plugin_order = 50
    auth_level = 1

    _enabled = False
    _pan302_url = ""
    _pan302_token = ""
    _include_dirs = ""
    _transfer_folder = ""
    _refresh_mediaserver = True
    _refresh_events = "strm_generated,strm_sync_completed,share_transfer_completed,offline_move_completed"
    _refresh_delay = 0
    _notify_on_callback = True
    _notify_image_url = ""
    _emby_url = ""
    _emby_api_key = ""

    def init_plugin(self, config: Optional[dict] = None):
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._pan302_url = self._normalize_base_url(config.get("pan302_url") or config.get("pan302_host"))
        self._pan302_token = (config.get("pan302_token") or "").strip()
        self._include_dirs = (config.get("include_dirs") or "").strip()
        self._transfer_folder = (config.get("transfer_folder") or "").strip()
        self._notify_on_callback = bool(config.get("notify_on_callback", True))
        self._notify_image_url = (config.get("notify_image_url") or "").strip()
        self._emby_url = self._normalize_base_url(config.get("emby_url"))
        self._emby_api_key = (config.get("emby_api_key") or "").strip()
        self._log_info("Pan302Bridge 插件初始化完成")

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

    def _log_info(self, message: str):
        if logger:
            logger.info(message)

    def _pan302_headers(self, auth_mode: str = "bearer", json_body: bool = False) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if json_body:
            headers["Content-Type"] = "application/json"
        if self._pan302_token:
            if auth_mode == "raw":
                headers["Authorization"] = self._pan302_token
            else:
                headers["Authorization"] = "Bearer %s" % self._pan302_token
        return headers

    def _pan302_endpoint(self, path: str) -> str:
        if not self._pan302_url:
            raise ValueError("pan302 地址未配置")
        if path.startswith("/"):
            return "%s%s" % (self._pan302_url, path)
        return "%s/%s" % (self._pan302_url, path)

    @staticmethod
    def _decode_http_response(resp) -> Any:
        body = resp.read().decode("utf-8", errors="replace")
        if not body:
            return {"status_code": resp.status}
        try:
            return json.loads(body)
        except ValueError:
            return {"status_code": resp.status, "body": body}

    def _pan302_get(
        self,
        path: str,
        params: Optional[dict] = None,
        timeout: int = 30,
        auth_mode: str = "bearer",
    ) -> Any:
        if not self._pan302_token:
            raise ValueError("pan302 Token 未配置")

        try:
            return self._pan302_get_once(path, params=params, timeout=timeout, auth_mode=auth_mode)
        except HTTPError as err:
            if err.code not in (401, 403):
                raise
            fallback_mode = "raw" if auth_mode == "bearer" else "bearer"
            return self._pan302_get_once(path, params=params, timeout=timeout, auth_mode=fallback_mode)

    def _pan302_get_once(
        self,
        path: str,
        params: Optional[dict] = None,
        timeout: int = 30,
        auth_mode: str = "bearer",
    ) -> Any:
        query = urlencode(params or {})
        url = self._pan302_endpoint(path)
        if query:
            url = "%s?%s" % (url, query)
        request = Request(url=url, method="GET", headers=self._pan302_headers(auth_mode=auth_mode))
        with urlopen(request, timeout=timeout) as resp:
            return self._decode_http_response(resp)

    def _pan302_post(
        self,
        path: str,
        payload: Optional[dict] = None,
        params: Optional[dict] = None,
        timeout: int = 30,
        auth_mode: str = "bearer",
    ) -> Any:
        if not self._pan302_token:
            raise ValueError("pan302 Token 未配置")

        try:
            return self._pan302_post_once(path, payload=payload, params=params, timeout=timeout, auth_mode=auth_mode)
        except HTTPError as err:
            if err.code not in (401, 403):
                raise
            fallback_mode = "raw" if auth_mode == "bearer" else "bearer"
            return self._pan302_post_once(path, payload=payload, params=params, timeout=timeout, auth_mode=fallback_mode)

    def _pan302_post_once(
        self,
        path: str,
        payload: Optional[dict] = None,
        params: Optional[dict] = None,
        timeout: int = 30,
        auth_mode: str = "bearer",
    ) -> Any:
        query = urlencode(params or {})
        url = self._pan302_endpoint(path)
        if query:
            url = "%s?%s" % (url, query)
        data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        request = Request(
            url=url,
            data=data,
            method="POST",
            headers=self._pan302_headers(auth_mode=auth_mode, json_body=True),
        )
        with urlopen(request, timeout=timeout) as resp:
            return self._decode_http_response(resp)

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
            {
                "path": "/shortcut/status",
                "endpoint": self.api_shortcut_status,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "快捷指令查询 Pan302 状态",
            },
            {
                "path": "/shortcut/share",
                "endpoint": self.api_shortcut_share,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "快捷指令提交 115 分享转存",
            },
            {
                "path": "/shortcut/strm-sync",
                "endpoint": self.api_shortcut_strm_sync,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "快捷指令触发 STRM 同步",
            },
            {
                "path": "/shortcut/upload-sync",
                "endpoint": self.api_shortcut_upload_sync,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "快捷指令触发上传同步",
            },
            {
                "path": "/shortcut/rule-trigger",
                "endpoint": self.api_shortcut_rule_trigger,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "快捷指令触发转移规则",
            },
        ]

    def api_status(self) -> Dict[str, Any]:
        return {
            "success": True,
            "enabled": self._enabled,
            "refresh_mediaserver": self._refresh_mediaserver,
            "refresh_events": self._split_config_values(self._refresh_events),
            "pan302_url": self._pan302_url,
            "has_pan302_token": bool(self._pan302_token),
            "include_dirs": self._split_config_values(self._include_dirs),
            "transfer_folder": self._transfer_folder,
            "notify_on_callback": self._notify_on_callback,
            "notify_image_url": self._notify_image_url,
            "emby_url": self._emby_url,
            "has_emby_api_key": bool(self._emby_api_key),
            "last_callback": self.get_data("last_callback"),
            "last_pan302_upload": self.get_data("last_pan302_upload"),
            "last_pan302_share": self.get_data("last_pan302_share"),
            "last_shortcut_action": self.get_data("last_shortcut_action"),
            "last_mediaserver_refresh": self.get_data("last_mediaserver_refresh"),
            "last_action": self.get_data("last_action"),
        }

    def api_refresh_mediaserver(self, data: Optional[dict] = None) -> Dict[str, Any]:
        self._log_info("收到手动刷新媒体服务器请求")
        result = self._refresh_preferred_mediaserver(reason="manual", callback=data or {})
        self._save_action("refresh_mediaserver", bool(result.get("success")), result)
        return result

    def api_pan302_callback(self, data: Optional[dict] = None) -> Dict[str, Any]:
        data = data or {}
        callback = dict(data)
        callback["success"] = True
        callback.setdefault("time", self._now())
        self._log_info("收到 pan-302 回调：event=%s" % (callback.get("event") or ""))

        refresh_result = self._refresh_from_callback(callback)
        callback["mediaserver_refresh"] = refresh_result
        self.save_data("last_callback", callback)

        if self._notify_on_callback:
            self._notify_callback(callback)

        return {
            "success": True,
            "mediaserver_refresh": refresh_result,
        }

    def api_shortcut_status(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "success": True,
            "action": "shortcut_status",
            "target": "pan302",
            "time": self._now(),
            "checks": {},
        }
        for name, endpoint in (
            ("health", "/api/health"),
            ("transfer", "/api/transfer/status"),
            ("strm", "/api/strm/status"),
        ):
            try:
                result["checks"][name] = self._pan302_get(endpoint, timeout=15)
            except Exception as err:
                result["success"] = False
                result["checks"][name] = {
                    "success": False,
                    "message": self._error_message(err),
                }
        return self._save_shortcut_action(result)

    def api_shortcut_share(
        self,
        url: str = "",
        shareUrl: str = "",
        share_url: str = "",
        folder: str = "",
        dstId: str = "",
        dst_id: str = "",
        dst: str = "",
        driverType: str = "",
        driver_type: str = "",
        driver: str = "",
        receiveCode: str = "",
        receive_code: str = "",
        code: str = "",
        password: str = "",
    ) -> Dict[str, Any]:
        share_url = (url or shareUrl or share_url or "").strip()
        dst_id = (dstId or dst_id or dst or folder or self._transfer_folder or "").strip()
        receive_code = (receiveCode or receive_code or code or password or "").strip()
        driver_type = self._shortcut_driver_type(driverType, driver_type, driver)

        result: Dict[str, Any] = {
            "success": False,
            "action": "shortcut_share",
            "target": "pan302",
            "url": share_url,
            "dstId": dst_id,
            "driverType": driver_type,
            "time": self._now(),
        }
        if not share_url:
            result["message"] = "缺少 115 分享链接"
            return self._save_shortcut_action(result)

        parsed = self._parse_115_share_url(share_url)
        if not parsed:
            result["message"] = "不是有效的 115 分享链接"
            return self._save_shortcut_action(result)
        if not receive_code and parsed[1]:
            receive_code = parsed[1]

        if not dst_id:
            result["message"] = "缺少转存目录，请在插件配置 115 分享转存目录，或传入 folder/dstId"
            return self._save_shortcut_action(result)

        payload = {
            "shareUrl": share_url,
            "receiveCode": receive_code,
            "dstId": dst_id,
            "driverType": driver_type,
        }
        try:
            response = self._pan302_post("/api/transfer/share-receive", payload=payload, timeout=30)
            result.update({"success": True, "result": response})
            self.save_data("last_pan302_share", result)
            self._log_info("快捷指令提交 pan302 分享转存成功：%s" % share_url)
        except Exception as err:
            result["message"] = self._error_message(err)
            self._log_warning("快捷指令提交 pan302 分享转存失败：%s" % result["message"])
        return self._save_shortcut_action(result)

    def api_shortcut_strm_sync(self, name: str = "") -> Dict[str, Any]:
        task_name = (name or "").strip()
        path = "/api/strm/sync/%s" % quote(task_name, safe="") if task_name else "/api/strm/sync"
        return self._shortcut_pan302_post("shortcut_strm_sync", path, {"name": task_name})

    def api_shortcut_upload_sync(self, name: str = "") -> Dict[str, Any]:
        task_name = (name or "").strip()
        if not task_name:
            return self._save_shortcut_action(
                {
                    "success": False,
                    "action": "shortcut_upload_sync",
                    "target": "pan302",
                    "time": self._now(),
                    "message": "缺少上传同步配置名称 name",
                }
            )
        path = "/api/transfer/sync/upload/%s" % quote(task_name, safe="")
        return self._shortcut_pan302_post("shortcut_upload_sync", path, {"name": task_name})

    def api_shortcut_rule_trigger(self, name: str = "") -> Dict[str, Any]:
        rule_name = (name or "").strip()
        if not rule_name:
            return self._save_shortcut_action(
                {
                    "success": False,
                    "action": "shortcut_rule_trigger",
                    "target": "pan302",
                    "time": self._now(),
                    "message": "缺少转移规则名称 name",
                }
            )
        path = "/api/transfer/rules/trigger/%s" % quote(rule_name, safe="")
        return self._shortcut_pan302_post("shortcut_rule_trigger", path, {"name": rule_name})

    @_event_register(EventType.TransferComplete if EventType else None)
    def evt_transfer_complete(self, event: Event):
        if not self._enabled or not event or not getattr(event, "event_data", None):
            return

        transferinfo = event.event_data.get("transferinfo")
        if not transferinfo or not getattr(transferinfo, "success", False):
            return

        target_item = getattr(transferinfo, "target_item", None)
        if not target_item:
            return

        storage = str(getattr(target_item, "storage", "") or "").lower()
        item_type = str(getattr(target_item, "type", "") or "").lower()
        target_path = str(getattr(target_item, "path", "") or "").strip()

        if storage and "local" not in storage:
            return
        if item_type and "file" not in item_type:
            return
        if not target_path:
            return
        if not self._path_in_include_dirs(target_path):
            self._log_info("整理完成路径不在 pan302 包含目录中，跳过：%s" % target_path)
            return

        self._log_info("MoviePilot 整理完成，通知 pan302 上传：%s" % target_path)
        result = self._trigger_pan302_upload_by_path(target_path)
        self._save_action("pan302_upload_by_path", bool(result.get("success")), result)

    @_event_register(EventType.UserMessage if EventType else None)
    def evt_user_message(self, event: Event):
        if not self._enabled or not event or not getattr(event, "event_data", None):
            return

        message = (event.event_data.get("text") or event.event_data.get("message") or "").strip()
        if not message:
            return
        if message.startswith("#"):
            message = message[1:].strip()
        if not message.startswith("http") or not self._parse_115_share_url(message):
            return

        if not self._transfer_folder:
            self._log_warning("收到 115 分享链接，但未配置 pan302 分享转存目录")
            return

        self._log_info("收到 115 分享链接，通知 pan302 转存：%s" % message)
        result = self._submit_pan302_share(message)
        self._save_action("pan302_share_save", bool(result.get("success")), result)

    def _path_in_include_dirs(self, target_path: str) -> bool:
        include_dirs = self._split_config_values(self._include_dirs)
        if not include_dirs:
            return True
        normalized_target = target_path.replace("\\", "/")
        for include_dir in include_dirs:
            normalized_include = include_dir.replace("\\", "/").rstrip("/")
            if normalized_include and normalized_target.startswith(normalized_include):
                return True
        return False

    @staticmethod
    def _parse_115_share_url(share_url: str) -> Optional[Tuple[str, Optional[str]]]:
        pattern = re.compile(r"(?:115|anxia|115cdn)\.com/s/([^?&#]+)(?:\?password=([^&#]+))?")
        matches = pattern.search(share_url)
        if not matches:
            return None
        return matches.groups()

    @staticmethod
    def _shortcut_driver_type(*values: str) -> str:
        for value in values:
            normalized = (value or "").strip()
            if normalized:
                return normalized
        return "115"

    def _save_shortcut_action(self, result: Dict[str, Any]) -> Dict[str, Any]:
        result.setdefault("time", self._now())
        self.save_data("last_shortcut_action", result)
        self._save_action(result.get("action") or "shortcut", bool(result.get("success")), result)
        return result

    def _shortcut_pan302_post(
        self,
        action: str,
        path: str,
        meta: Optional[dict] = None,
        payload: Optional[dict] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "success": False,
            "action": action,
            "target": "pan302",
            "path": path,
            "time": self._now(),
        }
        if meta:
            result.update(meta)
        try:
            response = self._pan302_post(path, payload=payload or {}, timeout=30)
            result.update({"success": True, "result": response})
            self._log_info("快捷指令调用 pan302 成功：%s" % action)
        except Exception as err:
            result["message"] = self._error_message(err)
            self._log_warning("快捷指令调用 pan302 失败：%s，%s" % (action, result["message"]))
        return self._save_shortcut_action(result)

    def _trigger_pan302_upload_by_path(self, target_path: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "success": False,
            "target": "pan302",
            "action": "upload_by_path",
            "path": target_path,
            "time": self._now(),
        }
        try:
            if not Path(target_path).exists():
                self._log_warning("整理完成文件在 MoviePilot 宿主内不存在，仍尝试通知 pan302：%s" % target_path)
            response = self._pan302_get(
                "/api/sync/upload-by-path",
                params={"path": target_path},
                timeout=30,
                auth_mode="bearer",
            )
            result.update({"success": True, "result": response})
        except Exception as err:
            result["message"] = self._error_message(err)

        self.save_data("last_pan302_upload", result)
        if result.get("success"):
            self._log_info("pan302 upload-by-path 调用成功：%s" % target_path)
        else:
            self._log_warning("pan302 upload-by-path 调用失败：%s" % result.get("message"))
        return result

    def _submit_pan302_share(self, share_url: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "success": False,
            "target": "pan302",
            "action": "save_share",
            "url": share_url,
            "folder": self._transfer_folder,
            "time": self._now(),
        }
        try:
            response = self._pan302_get(
                "/strm/api/task/save-share",
                params={"url": share_url, "folder": self._transfer_folder},
                timeout=30,
                auth_mode="raw",
            )
            result.update({"success": True, "result": response})
        except Exception as err:
            result["message"] = self._error_message(err)

        self.save_data("last_pan302_share", result)
        if result.get("success"):
            self._log_info("pan302 分享转存调用成功：%s" % share_url)
        else:
            self._log_warning("pan302 分享转存调用失败：%s" % result.get("message"))
        return result

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
        image = (
            data.get("image")
            or data.get("image_url")
            or data.get("poster")
            or data.get("poster_url")
            or self._notify_image_url
        )
        refresh_result = data.get("mediaserver_refresh") or {}
        if refresh_result and not refresh_result.get("skipped"):
            refresh_state = "成功" if refresh_result.get("success") else "失败"
            refresh_target = "Emby" if refresh_result.get("target") == "emby" else "MoviePilot 媒体服务器"
            text = "%s\n%s 刷新：%s" % (text, refresh_target, refresh_state)
        try:
            if image:
                try:
                    self.post_message(title=title, text=text, image=image)
                except TypeError as err:
                    self._log_warning(
                        "当前 MoviePilot 版本不支持通知图片参数，已回退为纯文本通知：%s"
                        % self._error_message(err)
                    )
                    self.post_message(title=title, text=text)
            else:
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
                                        "component": "VTextField",
                                        "props": {
                                            "model": "pan302_url",
                                            "label": "pan302 地址",
                                            "placeholder": "http://192.168.6.36:3000",
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
                                            "model": "pan302_token",
                                            "label": "pan302 Token",
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
                                            "model": "transfer_folder",
                                            "label": "115 分享转存目录",
                                            "placeholder": "/转存监控",
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
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "include_dirs",
                                            "label": "整理完成包含目录",
                                            "placeholder": "留空则不限制；多目录可换行或逗号分隔",
                                            "rows": 2,
                                            "auto-grow": True,
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
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "notify_image_url",
                                            "label": "通知默认图片 URL",
                                            "placeholder": "当 Pan302 回调没有携带 image 时，使用该图片作为 MoviePilot 通知卡片图片",
                                            "rows": 2,
                                            "auto-grow": True,
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
            "pan302_url": "",
            "pan302_token": "",
            "include_dirs": "",
            "transfer_folder": "",
            "notify_on_callback": True,
            "notify_image_url": "",
            "emby_url": "",
            "emby_api_key": "",
        }

    def get_page(self) -> List[dict]:
        last_callback = self.get_data("last_callback") or {}
        last_upload = self.get_data("last_pan302_upload") or {}
        last_share = self.get_data("last_pan302_share") or {}
        last_shortcut = self.get_data("last_shortcut_action") or {}
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
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info" if self._pan302_url and self._pan302_token else "warning",
                                    "variant": "tonal",
                                    "text": "pan302 主动联动：%s；包含目录：%s"
                                    % (
                                        "已配置" if self._pan302_url and self._pan302_token else "未完整配置",
                                        self._compact(self._split_config_values(self._include_dirs)),
                                    ),
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
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "text": "最近 pan302 上传：%s" % self._compact(last_upload),
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
                                    "text": "最近 pan302 分享转存：%s" % self._compact(last_share),
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
                                    "text": "最近快捷指令：%s" % self._compact(last_shortcut),
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
