import websocket
import json
import threading
import requests
import queue
import time
import streamlit as st

class FreeGiftReceiver:
    def __init__(self, room_id, host, key, target_queue):
        self.room_id = room_id
        self.host = host
        self.key = key
        self.ws = None
        self.thread = None
        self.is_running = False
        self.target_queue = target_queue  # セッション固有のキューを受け取る

    def on_message(self, ws, message):
        if message.startswith("MSG"):
            try:
                parts = message.split("\t")
                if len(parts) < 3:
                    return
                data = json.loads(parts[2])
                if data.get("t") == 2:
                    # このレシーバーに割り当てられた専用キューに入れる
                    self.target_queue.put(data)
            except Exception as e:
                print(f"WebSocket Message Error: {e}")

    def on_error(self, ws, error):
        print(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket Closed: {close_msg}")
        self.is_running = False

    def on_open(self, ws):
        # 接続維持のための設定
        ws.send(f"SUB\t{self.key}")
        print(f"WebSocket Connected: Room {self.room_id}")

    def run(self):
        """WebSocketのメインループ"""
        # hostに wss:// が含まれていないことを確実にする
        clean_host = self.host.replace("wss://", "").replace("/", "")
        ws_url = f"wss://{clean_host}:443/"
        
        while self.is_running:
            try:
                self.ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open
                )
                # 重要: 接続維持を強化
                self.ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print(f"WebSocket Run Error: {e}")
            
            if self.is_running:
                time.sleep(5)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        self.is_running = False
        if self.ws:
            self.ws.close()

# --- Streamlit側で呼び出す管理関数 ---

def get_gift_queue():
    """セッションごとに固有のキューを返す"""
    if "free_gift_queue" not in st.session_state:
        st.session_state.free_gift_queue = queue.Queue()
    return st.session_state.free_gift_queue

def init_free_gift_receiver(room_id):
    """
    メイン画面から呼び出し。
    レシーバーが未起動、または古い場合に初期化して起動する。
    """
    # 接続情報の取得
    info = get_streaming_server_info(room_id)
    if not info:
        return None
    
    # セッション固有のキューを取得
    user_queue = get_gift_queue()
    
    # レシーバーの作成
    receiver = FreeGiftReceiver(room_id, info['host'], info['key'], user_queue)
    return receiver



def get_streaming_server_info(room_id):
    """
    テストコードで成功した live_info API を使用して接続情報を取得する。
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    }
    try:
        url = f"https://www.showroom-live.com/api/live/live_info?room_id={room_id}"
        res = requests.get(url, headers=headers, timeout=5).json()
        
        host = res.get("bcsvr_host")
        key = res.get("bcsvr_key")
        
        if host and key:
            return {"host": host, "key": key}
    except Exception as e:
        print(f"API Error (live_info): {e}")
    return None

def update_free_gift_master(room_id):
    """
    APIから無償ギフト（星・種）のマスター情報を取得して
    st.session_state.free_gift_master に保存する。
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
    }
    try:
        url = f"https://www.showroom-live.com/api/live/gift_list?room_id={room_id}"
        res = requests.get(url, headers=headers, timeout=5).json()
        
        master = {}
        for cat_key in res.keys():
            category_list = res[cat_key]
            if isinstance(category_list, list):
                for category in category_list:
                    gifts = category.get("list", [])
                    for gift in gifts:
                        # 修正：free かつ point が 1 のものだけを「無償ギフト（星・種）」とみなす
                        if gift.get("free") == True and gift.get("point") == 1:
                            master[str(gift["gift_id"])] = {
                                "name": gift["gift_name"],
                                "image": gift["image"],
                                "point": 1
                            }
        st.session_state.free_gift_master = master
    except Exception as e:
        print(f"API Error (gift_list): {e}")
        if "free_gift_master" not in st.session_state:
            st.session_state.free_gift_master = {}