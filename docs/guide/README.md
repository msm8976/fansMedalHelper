# 使用指南

## 配置文件

复制 `users.example.yaml` 为 `users.yaml`，然后填写账号和任务配置。

```yaml
USERS:
  - access_key: XXXXXX
    white_uid: 0
    banned_uid: 0

CRON:
SENDKEY:
MOREPUSH:
PROXY:

ASYNC: 0
LIKE_CD: 3
DANMAKU_NUM: 10
DANMAKU_CD: 6
WATCHINGLIVE: 0
WEARMEDAL: 0
SIGNINGROUP: 2
```

## access_key

可以使用项目内扫码脚本获取 `access_key`：

```bash
uv run login.py
```

脚本会在控制台输出二维码和登录 URL，登录成功后只打印 `access_key`

## 任务行为

### 点赞

开播中的直播间会执行点赞任务。当前实现会对开播中且未满任务的粉丝牌点赞 30 次，无论粉丝牌是否已经点亮，用于获取点赞亲密度。

`LIKE_CD` 控制同步点赞时不同直播间之间的间隔；设置为 `0` 表示关闭点赞任务。

### 弹幕点亮

未开播时点赞不会点亮粉丝牌；未开播且未点亮的粉丝牌会发送弹幕尝试点亮。`DANMAKU_NUM` 控制发送次数，`DANMAKU_CD` 控制发送间隔；任一设置为 `0` 都可以关闭对应弹幕任务。

### 观看直播

观看直播任务默认关闭：

```yaml
WATCHINGLIVE: 0
```

如果需要开启，建议设置为：

```yaml
WATCHINGLIVE: 150
```

原因是当前规则约为每 15 分钟 +1 亲密度，单日上限 +10；设置 150 分钟可以覆盖当天观看亲密度上限。

### 应援团签到

`SIGNINGROUP` 控制应援团签到间隔，设置为 `0` 表示关闭。

## 报告消息

- 今日任务情况
- 未点亮粉丝牌列表
- 当前佩戴粉丝牌信息

## 运行

单次运行：

```bash
uv run main.py
```

如果 `users.yaml` 配置了 `CRON`，程序会按内置定时器运行。
