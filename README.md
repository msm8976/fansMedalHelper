# B 站粉丝牌助手

用于批量处理 B 站直播粉丝牌日常任务

## 功能

- 多账号粉丝牌日常任务
- 支持白名单、黑名单筛选主播 UID
- 仅对未开播直播间发送弹幕，并按账号/直播间做每日去重
- 点亮灯牌（点赞或弹幕点亮，取决于直播状态）
- 应援团签到

## 使用

复制配置模板：

```bash
cp users.example.yaml users.yaml
```

参考 [配置说明](#配置说明) 填写 `users.yaml`

获取 `access_key`：

```bash
uv run login.py
```

单次运行：

```bash
uv run main.py
```

配置 `CRON` 后会按 cron 表达式定时运行；也可以使用：

```bash
uv run main.py --auto
```

## 配置说明

- `USERS[].access_key`：账号登录凭据，必填。
- `USERS[].white_uid`：主播 UID 白名单，多个 UID 用英文逗号分隔；填非 `0` 后只处理白名单。
- `USERS[].banned_uid`：主播 UID 黑名单，多个 UID 用英文逗号分隔；白名单启用时黑名单失效。
- `CRON`：内置定时器表达式，例如 `0 0 * * *`。
- `SENDKEY`：Server 酱推送 key。
- `MOREPUSH`：onepush 多平台推送配置。
- `PROXY`：推送代理地址。
- `ASYNC`：点赞任务是否异步执行，`0` 为同步，`1` 为异步。
- `LIKE_CD`：同步点赞间隔秒数，默认 `5`；设为 `0` 关闭点赞。
- `DANMAKU_NUM`：每个直播间弹幕发送次数；设为 `0` 关闭弹幕发送。
- `DANMAKU_CD`：弹幕发送间隔秒数；设为 `0` 关闭弹幕发送。
- `DANMAKU_ALL_OFFLINE`：是否对所有未开播粉丝牌发送弹幕，`0` 为只发送给未点亮粉丝牌，`1` 为不管是否点亮，只要未开播就发送。
- `WATCHINGLIVE`：每个直播间观看分钟数，默认 `0` 关闭；如需拿满观看亲密度，需要设为 `150`。
- `WEARMEDAL`：弹幕前是否自动佩戴对应粉丝牌，`0` 关闭，`1` 开启。
- `SIGNINGROUP`：应援团签到间隔秒数，默认 `0` 关闭；设为大于 `0` 的秒数开启。

## 当前任务行为

开播中的直播间只执行点赞任务，不发送弹幕；每个开播直播间点赞 30 次。

弹幕默认只发送给未开播且未点亮的粉丝牌，用于尝试点亮牌子；开启 `DANMAKU_ALL_OFFLINE: 1` 后，会发送给所有未开播粉丝牌。

同一账号同一直播间每天最多成功发送一次弹幕，发送记录保存在 `.state/danmaku.json`。

观看直播心跳默认关闭；每 15 分钟约增加 1 点观看亲密度，单日上限 10 点，拿满需要设置为 `WATCHINGLIVE: 150`。

报告消息包含今日任务概览、未点亮粉丝牌和当前佩戴粉丝牌信息。

## 相对上游的修改

上游基准提交：`fdc626fc5e0ba42f9ea0da2f7f5cf13db7fc3a26`。该提交之后均为本 fork 修改。

- 重构为模块化 Python 结构，拆分 API、配置、服务、统计、日志、异常和模型等模块。
- 移除 Go 登录工具，新增 Python 扫码登录脚本 `login.py`。
- 移除仓库内置 `onepush` 源码，改为通过依赖安装。
- 移除远程检查更新工作流和入口脚本中的相关逻辑。
- 调整粉丝牌规则：不再按 20 级牌子区分，按新版单牌亲密度处理；点赞不按亲密度筛选，观看任务阈值为 10。
- 修改点亮逻辑：直播时点赞，下播时弹幕点亮，并限制同账号同房间每日最多成功发送一次弹幕。
- 新增并保留 `DANMAKU_NUM`、`WATCHINGLIVE`、`WEARMEDAL`、`SIGNINGROUP` 等配置。
- 默认关闭观看直播任务，并移除旧的 `WATCHINGALL` 配置。
- 更新粉丝牌佩戴 API、点赞 V3 接口签名和相关依赖版本。
- 简化统计报告，删除未满 30 亲密度数量日志和按亲密度分组输出。
- 曾新增视频投币模块，后续已移除该功能和相关兼容代码。
- 增加 `pyproject.toml`、`ruff.toml`，整理依赖和代码检查配置。

## 参考

- 原仓库：[XiaoMiku01/fansMedalHelper](https://github.com/XiaoMiku01/fansMedalHelper)
- 推送库：[y1ndan/onepush](https://github.com/y1ndan/onepush)
- Go 语言实现：[ThreeCatsLoveFish/MedalHelper](https://github.com/ThreeCatsLoveFish/MedalHelper)
- B 站挂机助手：[andywang425/BLTH](https://github.com/andywang425/BLTH)
