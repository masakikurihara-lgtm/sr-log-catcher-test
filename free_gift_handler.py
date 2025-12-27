import websocket
import json
import threading
import requests
import queue
import time
import streamlit as st

# --- 通信スレッドとメイン画面の間でデータを安全に受け渡すためのキュー ---
gift_queue = queue.Queue()

# ① 2台同時起動時の競合解消用：全スレッドで共有するキューのリスト
active_queues = []
queues_lock = threading.Lock()

class FreeGiftReceiver:
    def __init__(self, room_id, host, key):
        self.room_id = room_id
        self.host = host
        self.key = key
        self.ws = None
        self.thread = None
        self.is_running = False

    def on_message(self, ws, message):
        """WebSocketからメッセージを受信した時の処理"""
        if message.startswith("MSG"):
            try:
                parts = message.split("\t")
                if len(parts) < 3:
                    return
                
                # JSON部分を解析
                data = json.loads(parts[2])

                # ギフトメッセージ(t=2)のみを対象
                if data.get("t") == 2:
                    # ① 修正：全アクティブスレッドのキューにデータを投入
                    # これにより、複数タブを開いても全画面に反映されます
                    with queues_lock:
                        if not active_queues:
                            gift_queue.put(data)
                        else:
                            for q in active_queues:
                                q.put(data)
            except Exception as e:
                # スレッド内のエラーは標準出力（Logs）に送る
                print(f"WebSocket Message Error: {e}")

    def on_error(self, ws, error):
        print(f"WebSocket Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket Closed")
        # ② 修正：ここでは self.is_running を False にせず、run内の再接続ロジックに任せる

    def on_open(self, ws):
        """接続直後に購読命令(SUB)を送る（テストコードと同じ）"""
        ws.send(f"SUB\t{self.key}")
        print(f"WebSocket Connected: Room {self.room_id}")

    def run(self):
        """WebSocketのメインループ（② 修正：自動再接続機能を追加）"""
        ws_url = f"wss://{self.host}:443/"
        while self.is_running:
            try:
                self.ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open
                )
                # 30秒ごとにpingを送り、無通信による切断を防止
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                print(f"WebSocket Run Error: {e}")
            
            # 意図しない切断時、start()状態でいれば5秒後に再接続
            if self.is_running:
                print("WebSocket Reconnecting in 5 seconds...")
                time.sleep(5)

    def start(self):
        """バックグラウンドで受信を開始"""
        if not self.is_running:
            self.is_running = True
            # ① 修正：自身のキューをアクティブリストに登録
            with queues_lock:
                if gift_queue not in active_queues:
                    active_queues.append(gift_queue)
                    
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        """受信を停止"""
        self.is_running = False
        if self.ws:
            self.ws.close()
        # ① 修正：停止時にリストから除外
        with queues_lock:
            if gift_queue in active_queues:
                active_queues.remove(gift_queue)

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