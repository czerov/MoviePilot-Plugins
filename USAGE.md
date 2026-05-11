# Pan302Bridge 使用说明

`Pan302Bridge` 是一个 MoviePilot V2 插件，用来连接 MoviePilot 和 pan-302。它可以让 MoviePilot 主动调用 pan-302 的 STRM 同步、转移规则等接口，也可以接收 pan-302 的任务完成回调并在 MoviePilot 内通知。

## 一、安装插件

### 方式一：通过 MoviePilot 插件市场安装

1. 确认插件仓库已经上传到 GitHub：

   ```text
   https://github.com/czerov/MoviePilot-Plugins
   ```

2. 打开 MoviePilot 后台。

3. 进入插件页面，打开插件仓库管理。

4. 添加第三方插件仓库地址：

   ```text
   https://github.com/czerov/MoviePilot-Plugins
   ```

5. 刷新插件市场。

6. 搜索并安装：

   ```text
   Pan302 联动
   ```

   或：

   ```text
   Pan302Bridge
   ```

### 方式二：通过环境变量添加插件仓库

如果你用 Docker 或 docker-compose 部署 MoviePilot，也可以在环境变量中加入：

```text
PLUGIN_MARKET=https://github.com/czerov/MoviePilot-Plugins
```

如果已有其它插件仓库，用英文逗号拼接：

```text
PLUGIN_MARKET=https://github.com/jxxghp/MoviePilot-Plugins,https://github.com/czerov/MoviePilot-Plugins
```

修改环境变量后需要重启 MoviePilot。

## 二、插件配置说明

安装后进入插件配置页，按下面填写。

### 启用 pan-302 联动

打开。

关闭时插件不会主动工作。

### pan-302 地址

填写 MoviePilot 可以访问到的 pan-302 地址。

示例：

```text
http://192.168.6.36:3000
```

注意：

- 如果 MoviePilot 运行在 Docker 容器里，不建议填 `localhost` 或 `127.0.0.1`，因为它们通常指向 MoviePilot 容器自己。
- 推荐填写 pan-302 所在机器的局域网 IP。
- 地址末尾不要加 `/api`，插件会自动拼接接口路径。

正确：

```text
http://192.168.6.36:3000
```

错误：

```text
http://192.168.6.36:3000/api
```

### pan-302 Token

填写 pan-302 的 Bearer Token。

只填 Token 本身，不要带 `Bearer` 前缀。

正确：

```text
eyJhbGciOiJIUzI1NiIs...
```

错误：

```text
Bearer eyJhbGciOiJIUzI1NiIs...
```

### 回调校验 Token

这是 pan-302 回调 MoviePilot 插件时使用的插件内部校验 Token。

可以自己设置一个复杂字符串，例如：

```text
pan302_mp_callback_20260511
```

这个值不是 MoviePilot 的 `API_TOKEN`，也不是 pan-302 Token。

### 收到 pan-302 回调后发送 MoviePilot 通知

建议打开。

打开后，pan-302 回调插件时，MoviePilot 会发送一条通知。

### 快捷 STRM 名称

可选。

如果留空，插件详情页里的“全部 STRM 同步”会调用 pan-302：

```text
POST /api/strm/sync
```

如果填写某个 STRM 配置名称，例如：

```text
电影
```

插件详情页里的“指定 STRM 同步”会调用：

```text
POST /api/strm/sync/电影
```

名称必须和 pan-302 中的 STRM 配置名称一致。

### 快捷转移规则名称

可选。

如果 pan-302 中有一个转移规则叫：

```text
115
```

这里就填写：

```text
115
```

插件详情页里的“执行转移规则”会调用：

```text
POST /api/transfer/rules/trigger/115
```

名称必须和 pan-302 中的转移规则名称一致。

## 三、推荐最小配置

第一次测试时建议只填这些：

```text
启用 pan-302 联动：打开
pan-302 地址：http://你的pan302内网IP:3000
pan-302 Token：填写 pan-302 Token
回调校验 Token：填写一个自定义复杂字符串
收到 pan-302 回调后发送 MoviePilot 通知：打开
快捷 STRM 名称：留空
快捷转移规则名称：留空
```

保存后进入插件详情页，点击：

```text
测试连接
```

如果能看到 pan-302 版本信息，说明 MoviePilot 到 pan-302 的连接已经正常。

## 四、插件详情页按钮

插件详情页会提供这些操作：

### 测试连接

调用 pan-302：

```text
GET /api/version
```

用于确认地址和 Token 配置是否可用。

### 获取状态

调用 pan-302：

```text
GET /api/version
GET /api/health
GET /api/stats
GET /api/transfer/status
GET /api/strm/status
```

用于查看 pan-302 当前运行状态。

### 全部 STRM 同步

调用 pan-302：

```text
POST /api/strm/sync
```

### 指定 STRM 同步

只有填写了“快捷 STRM 名称”才会显示。

调用 pan-302：

```text
POST /api/strm/sync/<快捷STRM名称>
```

### 执行转移规则

只有填写了“快捷转移规则名称”才会显示。

调用 pan-302：

```text
POST /api/transfer/rules/trigger/<快捷转移规则名称>
```

### 查询传输任务

调用 pan-302：

```text
GET /api/transfer/status
```

## 五、配置 pan-302 回调 MoviePilot

pan-302 回调 MoviePilot 插件时，需要配置两个 Token：

- URL 参数里的 `apikey`：MoviePilot 的 `API_TOKEN`。
- JSON 请求体里的 `token`：插件配置页里填写的“回调校验 Token”。

### 回调地址格式

```text
http://你的MoviePilot地址:3000/api/v1/plugin/Pan302Bridge/pan302_callback?apikey=你的MoviePilot_API_TOKEN
```

示例：

```text
http://192.168.6.20:3000/api/v1/plugin/Pan302Bridge/pan302_callback?apikey=moviepilot_api_token
```

### 回调请求体示例

```json
{
  "token": "pan302_mp_callback_20260511",
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

### 建议事件名

```text
share_transfer_completed
offline_move_completed
strm_generated
strm_sync_completed
transfer_failed
```

收到回调后，插件会：

1. 校验请求体里的 `token`。
2. 保存最近一次回调记录。
3. 如果开启通知，调用 MoviePilot 通知。

## 六、接口说明

插件 API 注册在：

```text
/api/v1/plugin/Pan302Bridge/<path>
```

当前支持：

```text
GET  /api/v1/plugin/Pan302Bridge/status
POST /api/v1/plugin/Pan302Bridge/test_connection
POST /api/v1/plugin/Pan302Bridge/pan302_status
POST /api/v1/plugin/Pan302Bridge/transfer_status
POST /api/v1/plugin/Pan302Bridge/trigger_strm_sync
POST /api/v1/plugin/Pan302Bridge/trigger_transfer_rule
POST /api/v1/plugin/Pan302Bridge/pan302_callback
```

## 七、常见问题

### 插件市场搜不到插件

检查：

- GitHub 仓库地址是否添加正确。
- 仓库是否是 `main` 分支。
- 仓库根目录是否有 `package.v2.json`。
- 插件代码是否在 `plugins.v2/pan302bridge/`。
- MoviePilot 是否能正常访问 GitHub。

### 测试连接失败

检查：

- `pan-302 地址` 是否能从 MoviePilot 容器访问。
- 地址末尾是否误加了 `/api`。
- pan-302 是否正在运行。
- pan-302 Token 是否正确。
- 如果 MoviePilot 在 Docker 内，不要使用 `localhost` 指向宿主机 pan-302。

### 回调失败或提示 token 不正确

检查：

- 回调 URL 里的 `apikey` 是否是 MoviePilot 的 `API_TOKEN`。
- 请求体里的 `token` 是否等于插件配置页的“回调校验 Token”。
- URL 路径是否为 `/api/v1/plugin/Pan302Bridge/pan302_callback`。

### 点击指定 STRM 或转移规则没有效果

检查：

- “快捷 STRM 名称”是否和 pan-302 中的名称完全一致。
- “快捷转移规则名称”是否和 pan-302 中的规则名称完全一致。
- 名称中如果有空格、大小写或中文，需要保持一致。

## 八、更新插件

如果后续插件代码有更新，需要：

1. 修改插件代码。
2. 同步修改 `plugins.v2/pan302bridge/__init__.py` 中的 `plugin_version`。
3. 同步修改 `package.v2.json` 中的 `version`。
4. 提交并推送到 GitHub。
5. 在 MoviePilot 插件市场刷新并更新插件。

