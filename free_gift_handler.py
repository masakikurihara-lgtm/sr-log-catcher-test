import websocket
import json
import threading
import time
import streamlit as st

class FreeGiftReceiver:
    def __init__(self, room_id, bcsvr_host, bcsvr_key):
        self.room_id = room_id
        self.host = bcsvr_host
        self.key = bcsvr_key
        self.ws = None
        self.thread = None
        self.is_running = False

    def on_message(self, ws, message):
        if message.startswith("MSG"):
            try:
                parts = message.split("\t")
                if len(parts) < 3: return
                data = json.loads(parts[2])

                # ギフトメッセージ(t=2)のみを対象
                if data.get("t") == 2:
                    # app.pyのsession_stateにデータを追加するためのキュー(リスト)に保存
                    if "raw_free_gift_queue" not in st.session_state:
                        st.session_state.raw_free_gift_queue = []
                    st.session_state.raw_free_gift_queue.append(data)
            except Exception:
                pass

    def on_open(self, ws):
        ws.send(f"SUB\t{self.key}")

    def run(self):
        ws_url = f"wss://{self.host}:443/"
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_open=self.on_open
        )
        self.ws.run_forever()

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        if self.ws:
            self.ws.close()
            self.is_running = False