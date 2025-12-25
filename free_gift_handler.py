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

                # 【デバッグ用】届いたすべてのパケットの型（t）を表示
                # print(f"DEBUG: 受信パケット t={data.get('t')}") 

                # ギフトメッセージ(t=2)のみを対象
                if data.get("t") == 2:
                    # 【デバッグ用】ギフトデータの中身を表示
                    # print(f"DEBUG: ギフトデータ受信 g={data.get('g')}, n={data.get('n')}")
                    
                    if "raw_free_gift_queue" not in st.session_state:
                        st.session_state.raw_free_gift_queue = []
                    st.session_state.raw_free_gift_queue.append(data)
            except Exception as e:
                print(f"DEBUG: 解析エラー {e}")

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


# --- free_gift_handler.py の末尾に追加 ---

def get_streaming_server_info(room_id):
    """配信サーバーのホストとキーを取得する"""
    import requests
    try:
        res = requests.get(f"https://www.showroom-live.com/api/live/streaming_server?room_id={room_id}", timeout=5).json()
        if "streaming_url_list" in res and res["streaming_url_list"]:
            # 最初の配信サーバー情報を返す
            server = res["streaming_url_list"][0]
            return {"host": server["host"], "key": server["key"]}
    except Exception as e:
        print(f"Error fetching streaming info: {e}")
    return None

def update_free_gift_master(room_id):
    """無償ギフト（星・種）の情報を取得してsession_stateに保存する"""
    import requests
    import streamlit as st
    try:
        res = requests.get(f"https://www.showroom-live.com/api/live/gift_list?room_id={room_id}", timeout=5).json()
        master = {}
        # en_jpの中に無償ギフト(type=1)が含まれていることが多い
        for category in res.get("en_jp", []):
            for gift in category.get("list", []):
                if gift.get("is_not_free") == False: # 無償ギフトのみ
                    master[gift["gift_id"]] = {
                        "name": gift["gift_name"],
                        "image": gift["image"],
                        "point": gift["free_num_2020"] # 無償ギフトのポイント(通常1)
                    }
        st.session_state.free_gift_master = master
    except Exception as e:
        st.session_state.free_gift_master = {}
        print(f"Error updating gift master: {e}")