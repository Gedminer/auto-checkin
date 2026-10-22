# auto-checkin

每天在随机时间自动签到，支持多种推送通知（Telegram / Bark / ntfy / Server酱）。

## 随机时间

- 触发时间覆盖 **UTC+8 的 05:00–24:00**（每半小时一次，避开整点高峰）。
- 脚本以当天日期为种子随机生成一个目标时刻（05:00–24:00 之间），**到达目标时刻后的第一次运行**执行签到，更早的运行自动跳过。
- GitHub Actions 的定时任务在高负载时段可能延迟或丢运行，因此脚本采用"到达即签"而非"整点命中"，确保目标时刻过后任何一次运行都能完成签到。
- 同一天后续运行会收到"今日已签到"，只记日志、不重复推送通知。
- 手动触发（`Run workflow`）则立即执行，忽略随机时间。

## 配置

仓库 `Settings → Secrets and variables → Actions` 中添加：

| Secret | 必填 | 说明 |
| --- | --- | --- |
| `TARGET_URL` | 是 | 站点地址 |
| `TARGET_COOKIE` | 是 | 登录后的完整 Cookie |
| `TG_BOT_TOKEN` | 否 | Telegram 机器人 Token |
| `TG_CHAT_ID` | 否 | Telegram 接收方 chat_id |
| `BARK_URL` | 否 | Bark 推送地址，如 `https://api.day.app/你的KEY` |
| `NTFY_URL` | 否 | ntfy 地址，如 `https://ntfy.sh/你的主题` |
| `SERVERCHAN_KEY` | 否 | Server酱 SendKey |

推送渠道任选其一或多个，配置了哪个就走哪个。

## 运行

`Actions` → `checkin` → `Run workflow`，或等待每日随机时间自动触发。

## Cookie 失效

登录 Cookie 到期后签到会失败并推送通知，此时重新获取 Cookie 并更新 `TARGET_COOKIE` 即可。登录时勾选"记住我"可显著延长有效期。

`local/` 目录为本地工具，不会提交到仓库。

