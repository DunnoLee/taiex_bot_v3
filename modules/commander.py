import requests
import threading
import time
from config.settings import Settings

class TelegramCommander:
    """
    雙向指揮官 V3.1 (Logic Fix)
    修正:
    1. /stop 改為「暫停交易」，不關閉程式。
    2. 新增 /start 恢復交易。
    3. 新增 /kill 關閉程式。
    4. 實作 /balance 指令路由。
    """
    def __init__(self):
        self.token = Settings.TELEGRAM_TOKEN
        self.chat_id = Settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}/"
        
        self.enabled = bool(self.token and self.chat_id)
        self.last_update_id = 0
        self.is_running = False
        
        # 回呼函數 (Callbacks)
        self.get_status_cb = None
        self.get_balance_cb = None
        self.toggle_trading_cb = None # True=開, False=關
        self.shutdown_cb = None       # 真的關閉程式

        if self.enabled:
            print("📡 [Commander] 雙向通訊模組 V3.1 已就緒")

    # --- 發送功能 ---
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

    # --- 監聽功能 ---
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
        text = result["message"]["text"].strip()
        sender_id = str(result["message"]["chat"]["id"])
        
        if sender_id != self.chat_id: return # 忽略陌生人

        print(f"📩 [Commander] 收到指令: {text}")

        # --- 指令路由 ---
        if text == "/start":
            self.send_message("▶️ **收到指令：恢復自動交易**")
            if self.toggle_trading_cb: self.toggle_trading_cb(True)

        elif text == "/stop":
            self.send_message("⏸ **收到指令：暫停自動交易 (系統仍在線上)**")
            if self.toggle_trading_cb: self.toggle_trading_cb(False)

        elif text == "/status":
            if self.get_status_cb: self.send_message(self.get_status_cb())

        elif text == "/balance":
            if self.get_balance_cb: self.send_message(self.get_balance_cb())
            else: self.send_message("⚠️ 無法取得餘額資訊")

        elif text == "/kill":
            self.send_message("💀 **收到指令：系統完全關閉 (Bye)**")
            if self.shutdown_cb: self.shutdown_cb()

        elif text == "/help":
            self.send_message(
                "🎮 **指令列表**\n"
                "`/start` - 恢復自動交易\n"
                "`/stop` - 暫停自動交易 (僅監控)\n"
                "`/status` - 系統狀態\n"
                "`/balance` - 帳戶權益\n"
                "`/kill` - 完全關閉程式"
            )
        else:
            self.send_message(f"❓ 未知指令: {text}")

    def set_callbacks(self, status_cb, balance_cb, toggle_cb, shutdown_cb):
        self.get_status_cb = status_cb
        self.get_balance_cb = balance_cb
        self.toggle_trading_cb = toggle_cb
        self.shutdown_cb = shutdown_cb