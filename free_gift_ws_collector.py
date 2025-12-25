import websocket
import json
import time
import requests
import sys
import os

# -----------------------------
# 起動引数チェック
# -----------------------------
if len(sys.argv) < 2:
    print("Usage: python free_gift_ws_collector.py <ROOM_ID>")
    sys.exit(1)

ROOM_ID = sys.argv[1]

SAVE_PATH = f"free_gift_log_{ROOM_ID}.jsonl"

# -----------------------------
# LIVE INFO 取得
# -----------------------------
LIVE_INFO_URL = f"https://www.showroom-live.com/api/live/live_info?room_id={ROOM_ID}"
info = requests.get(LIVE_INFO_URL).json()

if "bcsvr_key" not in info:
    print("このルームは現在配信していません")
    sys.exit(0)

ws_url = f"ws://{info['bcsvr_host']}:{info['bcsvr_port']}/{info['bcsvr_key']}"

print("WS URL:", ws_url)

# -----------------------------
# WS callbacks
# -----------------------------
def on_message(ws, message):
    if not message.startswith("MSG"):
        return
    try:
        payload = json.loads(message.split("\t", 2)[2])
    except Exception:
        return

    if payload.get("t") == 2:  # ギフト
        with open(SAVE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

def on_error(ws, error):
    print("WS Error:", error)

def on_close(ws):
    print("WS Closed - reconnecting in 5s")
    time.sleep(5)
    start()

def start():
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# -----------------------------
# start
# -----------------------------
start()
