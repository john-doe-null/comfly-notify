
import os
import json
import requests
from decimal import Decimal
from pathlib import Path

API_URL = "https://ai.comfly.org/api/user/self"

API_TOKEN = os.environ["API_TOKEN"]
NEW_API_USER = os.getenv("NEW_API_USER", "44031")

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
WEWORK_WEBHOOK = os.getenv("WEWORK_WEBHOOK", "")

DIVISOR = Decimal(os.getenv("BALANCE_DIVISOR", "500000"))
ALERT_THRESHOLD = Decimal(os.getenv("ALERT_THRESHOLD", "100"))
RECOVERY_THRESHOLD = Decimal(os.getenv("RECOVERY_THRESHOLD", "110"))

STATE_FILE = Path("state.json")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"alerted": False}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def send_message(message):
    results = []

    if FEISHU_WEBHOOK:
        try:
            r = requests.post(
                FEISHU_WEBHOOK,
                json={
                    "msg_type": "text",
                    "content": {"text": message}
                },
                timeout=15
            )
            r.raise_for_status()
            results.append("Feishu")
            print("飞书通知成功")
        except Exception as e:
            print("飞书通知失败:", e)

    if WEWORK_WEBHOOK:
        try:
            r = requests.post(
                WEWORK_WEBHOOK,
                json={
                    "msgtype": "text",
                    "text": {"content": message}
                },
                timeout=15
            )
            r.raise_for_status()
            results.append("WeCom")
            print("企微通知成功")
        except Exception as e:
            print("企微通知失败:", e)

    if not results:
        raise RuntimeError("没有任何通知渠道发送成功")

    return results


def main():
    if DIVISOR <= 0:
        raise ValueError("BALANCE_DIVISOR 必须大于 0")

    if RECOVERY_THRESHOLD <= ALERT_THRESHOLD:
        raise ValueError("恢复阈值必须大于报警阈值")

    response = requests.get(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_TOKEN}",
            "New-API-User": NEW_API_USER
        },
        timeout=20
    )
    response.raise_for_status()

    result = response.json()

    if not result.get("success"):
        raise RuntimeError(f"API 查询失败: {result}")

    quota = Decimal(str(result["data"]["quota"]))
    balance = quota / DIVISOR

    print(f"原始 quota: {quota}")
    print(f"换算余额: ${balance:.2f}")
    print(f"报警阈值: ${ALERT_THRESHOLD}")
    
    state = load_state()
    alerted = state.get("alerted", False)

    if balance <= ALERT_THRESHOLD and not alerted:
        message = (
            "⚠️ Comfly AI 余额不足预警\n"
            f"当前余额：${balance:.2f}\n"
            f"原始额度：{quota}\n"
            f"报警阈值：${ALERT_THRESHOLD}\n"
            "请及时充值，避免影响 API 使用。"
        )

        send_message(message)
        state["alerted"] = True
        save_state(state)

    elif balance >= RECOVERY_THRESHOLD and alerted:
        message = (
            "✅ Comfly AI 余额已恢复\n"
            f"当前余额：${balance:.2f}\n"
            f"恢复阈值：${RECOVERY_THRESHOLD}\n"
            "余额监控已解除报警状态。"
        )

        send_message(message)
        state["alerted"] = False
        save_state(state)

    elif alerted:
        print("余额仍处于报警区间，不重复发送通知")

    else:
        print("余额正常，无需报警")


if __name__ == "__main__":
    main()
