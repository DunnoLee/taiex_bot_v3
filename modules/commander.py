import requests
import threading
import time
from config.settings import Settings
import queue

class TelegramCommander:
    """
    雙向指揮官 V3.3 (Trader Edition)
    新增:
    1. 手動交易指令: /buy, /sell
    2. 同步指令: /sync (強制同步真實倉位)
    """
    def __init__(self):
        self.token = Settings.TELEGRAM_TOKEN
        self.chat_id = Settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}/"
        
        self.enabled = bool(self.token and self.chat_id)
        self.last_update_id = 0
        self.is_running = False
        
        # 🕒 記錄啟動時間 (這行是關鍵！)
        self.startup_time = int(time.time())
        
        # 回呼函數
        self.get_status_cb = None
        self.get_balance_cb = None
        self.toggle_trading_cb = None
        self.shutdown_cb = None
        # 新增 flatten_cb
        self.manual_trade_cb = None
        self.sync_position_cb = None
        self.flatten_cb = None  # <--- 新增這個


        if self.enabled:
            print("📡 [Commander] 雙向通訊模組 V3.2 (防殭屍版) 已就緒")

    # --- 發送功能 (不變) ---
    def send_message(self, text: str):
        if not self.enabled: return
        try:
            url = self.base_url + "sendMessage"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
            threading.Thread(target=requests.post, args=(url,), kwargs={'data': data}, daemon=True).start()
        except Exception as e:
            print(f"⚠️ [Commander] 發送失敗: {e}")

    def send_startup_report(self, symbol: str, strategy_info: str):
        self.send_message(
            f"🚀 **TaiEx Bot V3 啟動**\n"
            f"🎯 標的: `{symbol}`\n"
            f"🧠 策略: `{strategy_info}`\n"
            f"💡 輸入 `/help` 查看指令"
        )

    def send_signal_notification(self, signal):
        icon = "🔴 做多" if "LONG" in str(signal.signal_type) else ("🟢 做空" if "SHORT" in str(signal.signal_type) else "⚪️ 平倉")
        self.send_message(
            f"⚡️ **訊號觸發**\n"
            f"{icon} {signal.symbol}\n"
            f"📊 原因: {signal.reason}\n"
            f"🕒 時間: {signal.timestamp.strftime('%H:%M:%S')}"
        )

    # --- 監聽功能 (不變) ---
    def start_listening(self):
        if not self.enabled: return
        self.is_running = True
        threading.Thread(target=self._poll_updates, daemon=True).start()
        print("👂 [Commander] 開始監聽 Telegram 指令...")

    def _poll_updates(self):
        while self.is_running:
            try:
                url = self.base_url + "getUpdates"
                params = {"offset": self.last_update_id + 1, "timeout": 30}
                resp = requests.get(url, params=params, timeout=35)
                if resp.status_code == 200:
                    data = resp.json()
                    if data["ok"]:
                        for result in data["result"]:
                            self.last_update_id = result["update_id"]
                            self._handle_message(result)
            except Exception:
                time.sleep(5)
            time.sleep(1)

    def _handle_message(self, result):
        if "message" not in result or "text" not in result["message"]: return
        message = result["message"]
        text = message["text"].strip()
        sender_id = str(message["chat"]["id"])
        
        
        # 1. 檢查發送者
        if sender_id != self.chat_id: return

        # 2. 🛡️ 檢查訊息時間 (防殭屍邏輯)
        # Telegram 的 date 是 Unix Timestamp
        msg_date = message.get("date", 0)
        
        # 如果訊息時間 < 程式啟動時間，代表這是「過去的幽靈」，忽略它
        if msg_date < self.startup_time:
            print(f"⏳ [Commander] 忽略歷史訊息: {text} (Time: {msg_date})")
            return

        print(f"📩 [Commander] 收到指令: {text}")

        # --- 指令路由 (新增交易功能) ---
        parts = text.split() # 支援參數，例如 /buy 2 (買兩口)
        cmd = parts[0].lower()
        
        # --- 指令路由 (不變) ---
        if cmd == "/start":
            self.send_message("▶️ **收到指令：恢復自動交易**")
            if self.toggle_trading_cb: self.toggle_trading_cb(True)

        elif cmd == "/stop":
            self.send_message("⏸ **收到指令：暫停自動交易**")
            if self.toggle_trading_cb: self.toggle_trading_cb(False)

        elif cmd == "/status":
            if self.get_status_cb: self.send_message(self.get_status_cb())

        elif cmd == "/balance":
            if self.get_balance_cb: self.send_message(self.get_balance_cb())

        # 🆕 新增：手動下單
        elif cmd == "/buy":
            qty = 1
            if len(parts) > 1 and parts[1].isdigit():
                qty = int(parts[1])
            self.send_message(f"🔴 **收到手動指令：買進 {qty} 口**")
            if self.manual_trade_cb: self.manual_trade_cb("BUY", qty)

        elif cmd == "/sell":
            qty = 1
            if len(parts) > 1 and parts[1].isdigit():
                qty = int(parts[1])
            self.send_message(f"🟢 **收到手動指令：賣出 {qty} 口**")
            if self.manual_trade_cb: self.manual_trade_cb("SELL", qty)

        # 🆕 新增：強制同步
        elif cmd == "/sync":
            self.send_message("🔄 **收到指令：強制同步真實倉位...**")
            if self.sync_position_cb: 
                new_pos = self.sync_position_cb()
                self.send_message(f"✅ **同步完成**\n目前策略認知倉位已修正為: {new_pos}")

        elif cmd == "/kill":
            self.send_message("💀 **收到指令：系統完全關閉 (Bye)**")
            if self.shutdown_cb: self.shutdown_cb()

        # 🆕 新增：一鍵平倉
        elif cmd == "/flat" or cmd == "/flatten":
            self.send_message("⚠️ **收到指令：強制全平倉 (Flatten All)**")
            if self.flatten_cb: self.flatten_cb()

        elif cmd == "/help":
            self.send_message(
                "🎮 **指令列表**\n"
                "`/start` - 恢復自動交易\n"
                "`/stop` - 暫停自動交易\n"
                "`/buy [口數]` - 手動買進\n"
                "`/sell [口數]` - 手動賣出\n"
                "`/flat` - ⚠️ 一鍵全平倉\n"  # <--- 加這行
                "`/sync` - 同步真實倉位\n"
                "`/status` - 系統狀態\n"
                "`/balance` - 權益數查詢\n"
                "`/kill` - 關閉程式"
            )
        else:
            self.send_message(f"❓ 未知指令: {text}")

    # 記得更新 callback 設定介面
    def set_callbacks(self, status_cb, balance_cb, toggle_cb, shutdown_cb, manual_trade_cb, sync_position_cb,flatten_cb):
        self.get_status_cb = status_cb
        self.get_balance_cb = balance_cb
        self.toggle_trading_cb = toggle_cb
        self.shutdown_cb = shutdown_cb
        self.manual_trade_cb = manual_trade_cb  # 🆕
        self.sync_position_cb = sync_position_cb # 🆕
        self.flatten_cb = flatten_cb