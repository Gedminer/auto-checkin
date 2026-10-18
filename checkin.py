import os
import sys
import re
import time
import random
import hashlib
import urllib.parse
from datetime import datetime, timezone, timedelta

import requests

try:
    import cloudscraper
except Exception:
    cloudscraper = None

BASE_URL = (os.environ.get("TARGET_URL") or "").strip().rstrip("/")
COOKIE = (os.environ.get("TARGET_COOKIE") or "").strip()
CHECKIN_PATH = "/user/checkin"
TZ = timezone(timedelta(hours=8))
FORCE = (os.environ.get("FORCE") or "").strip().lower() in ("1", "true", "yes")
WINDOW_START = 5 * 60
WINDOW_END = 24 * 60

ALREADY = ("已签到", "已经签到", "已簽到", "已經簽到", "重复", "重複")


def build_masks():
    masks = set()
    host = urllib.parse.urlparse(BASE_URL).hostname or ""
    if host:
        masks.add(host)
        if "." in host:
            masks.add(host.split(".")[0])
    for w in (os.environ.get("MASK_WORDS") or "").split(","):
        w = w.strip()
        if w:
            masks.add(w)
    return tuple(sorted(masks, key=len, reverse=True))


MASK_WORDS = build_masks()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}


def redact(s):
    text = str(s)
    for w in MASK_WORDS:
        text = text.replace(w, "***")
    return re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "***", text)


def now():
    return datetime.now(TZ)


def log(msg):
    print(f"[{now().strftime('%Y-%m-%d %H:%M:%S')}] {redact(msg)}", flush=True)


def daily_target_minute(day):
    seed = int(hashlib.sha256(day.isoformat().encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed).randrange(WINDOW_START, WINDOW_END)


def passed_gate():
    n = now()
    target = daily_target_minute(n.date())
    target_hour, target_minute = divmod(target, 60)
    if n.hour != target_hour:
        log("不在今日签到时段，跳过")
        return False
    wait = (target_minute - n.minute) * 60 - n.second
    if wait > 0:
        log(f"随机等待 {wait} 秒后签到")
        time.sleep(wait)
    return True


def notify(title, text):
    sent = []
    token, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if token and chat:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": f"{title}\n{text}", "disable_web_page_preview": True},
                timeout=20,
            )
            sent.append("telegram")
        except Exception:
            pass
    bark = os.environ.get("BARK_URL")
    if bark:
        try:
            requests.post(bark.rstrip("/"), json={"title": title, "body": text}, timeout=20)
            sent.append("bark")
        except Exception:
            pass
    ntfy = os.environ.get("NTFY_URL")
    if ntfy:
        try:
            requests.post(
                ntfy,
                data=text.encode("utf-8"),
                headers={
                    "Title": title.encode("utf-8").decode("latin-1", "ignore"),
                    "Tags": "white_check_mark",
                },
                timeout=20,
            )
            sent.append("ntfy")
        except Exception:
            pass
    sck = os.environ.get("SERVERCHAN_KEY")
    if sck:
        try:
            requests.post(f"https://sctapi.ftqq.com/{sck}.send", data={"title": title, "desp": text}, timeout=20)
            sent.append("serverchan")
        except Exception:
            pass
    if sent:
        log("已发送通知: " + ",".join(sent))


def finish(ok, summary, detail="", title=None):
    log(summary)
    body = now().strftime("%Y-%m-%d %H:%M") + " " + summary
    if detail:
        body += "\n" + detail
    notify(title or ("签到成功" if ok else "签到失败"), body)
    return 0 if ok else 1


def main():
    if not BASE_URL:
        return finish(False, "缺少 TARGET_URL")
    if not COOKIE:
        return finish(False, "缺少 TARGET_COOKIE")

    if not FORCE and not passed_gate():
        return 0

    cookie = COOKIE if "=" in COOKIE else f"PHPSESSID={COOKIE}"
    headers = dict(HEADERS)
    headers["Cookie"] = cookie
    headers["Referer"] = BASE_URL + "/user"
    headers["Origin"] = BASE_URL

    session = cloudscraper.create_scraper() if cloudscraper is not None else requests.Session()

    log("开始签到")
    try:
        resp = session.post(BASE_URL + CHECKIN_PATH, headers=headers, timeout=60, allow_redirects=False)
    except Exception as exc:
        return finish(False, f"请求异常: {type(exc).__name__}")

    if resp.status_code in (301, 302, 303, 307, 308):
        return finish(False, "会话已失效，请更新 TARGET_COOKIE")
    if resp.status_code == 403:
        return finish(False, "被站点防护拦截(403)")
    if resp.status_code != 200:
        return finish(False, f"状态码异常: {resp.status_code}")

    text = resp.text.strip()
    if text[:1] == "<" and "cloudflare" in text.lower():
        return finish(False, "请求被拦截，请稍后重试")

    try:
        data = resp.json()
    except ValueError:
        return finish(False, "返回内容无法解析")

    ret = data.get("ret")
    msg = str(data.get("msg", "")).strip()
    already = any(k in msg for k in ALREADY)

    if ret == 1:
        if already:
            return finish(True, "今日已签到", msg, title="今日已签到")
        return finish(True, "签到成功", msg, title="签到成功")
    if already:
        return finish(True, "今日已签到", msg, title="今日已签到")
    return finish(False, "签到失败", msg)


if __name__ == "__main__":
    sys.exit(main())
