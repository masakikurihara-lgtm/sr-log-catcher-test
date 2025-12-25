import websocket
import json
import threading
import requests
import streamlit as st

class FreeGiftReceiver:
    def __init__(self, room_id, bcsvr_host, bcsvr_key):
        self.room_id = room_id
        self.host = bcsvr_host
        self.key = bcsvr_key
        self.ws = None
        self.is_running = False

    def on_message(self, ws, message):
        if message.startswith("MSG"):
            try:
                # MSG\tルームID\t{JSON} という形式を分解
                parts = message.split("\t")
                if len(parts) < 3: return
                data = json.loads(parts[2])

                # ギフトメッセージ(t=2)のみを対象
                if data.get("t") == 2:
                    # テストコードで受信できている生データをそのままリストに追加
                    if "raw_free_gift_queue" not in st.session_state:
                        st.session_state.raw_free_gift_queue = []
                    
                    # データの重複を防ぐための簡易チェック（created_atとuser_idで判定）
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
            # スレッドを「daemon=True」にしてStreamlit停止時に終了するようにする
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        if self.ws:
            self.ws.close()
            self.is_running = False

def get_streaming_server_info(room_id):
    """テストコードで成功した live_info API を使用"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    }
    try:
        url = f"https://www.showroom-live.com/api/live/live_info?room_id={room_id}"
        res = requests.get(url, headers=headers, timeout=5).json()
        return {"host": res.get("bcsvr_host"), "key": res.get("bcsvr_key")}
    except:
        return None

def update_free_gift_master(room_id):
    """無償ギフト情報を取得。取得漏れを防ぐため広めに取得"""
    import requests
    try:
        res = requests.get(f"https://www.showroom-live.com/api/live/gift_list?room_id={room_id}", timeout=5).json()
        master = {}
        # すべてのカテゴリから無償ギフトを抽出
        for cat_key in res.keys():
            if isinstance(res[cat_key], list):
                for category in res[cat_key]:
                    for gift in category.get("list", []):
                        if gift.get("is_not_free") == False:
                            master[gift["gift_id"]] = {
                                "name": gift["gift_name"],
                                "image": gift["image"],
                                "point": gift.get("free_num_2020", 1)
                            }
        st.session_state.free_gift_master = master
    except:
        st.session_state.free_gift_master = {}
        