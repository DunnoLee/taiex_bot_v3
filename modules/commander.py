import requests
import threading
import time
from datetime import datetime
from config.settings import Settings

class TelegramCommander:
    """
    指揮官 (Commander) - 負責對外通訊
    目前功能: 單向通知 (發送系統狀態、訊號、成交回報)
    V3 特性: 使用 Thread 異步發送，不阻塞主交易迴圈。
    """
    def __init__(self):
        self.token = Settings.TELEGRAM_TOKEN
        self.chat_id = Settings.TELEGRAM_CHAT_ID
        
        # 簡單檢查
        if not self.token or not self.chat_id:
            print("⚠️ [Commander] 未設定 Telegram Token，將無法發送通知。")
            self.enabled = False
        else:
            self.base_url = f"https://api.telegram.org/bot{self.token}/"
            self.enabled = True
            print("📡 [Commander] 通訊模組已就緒")

    def _send_request(self, text: str):
        """實際發送 HTTP 請求的函數 (將在 Thread 中執行)"""
        if not self.enabled: return
        try:
            url = self.base_url + "sendMessage"
            # parse_mode='Markdown' 讓你可以用粗體字
            data = {
                "chat_id": self.chat_id, 
                "text": text,
                "parse_mode": "Markdown" 
            }
            requests.post(url, data=data, timeout=5)
        except Exception as e:
            print(f"⚠️ [Commander] 發送失敗: {e}")

    def send_message(self, text: str):
        """對外公開的發送方法 (非阻塞)"""
        # 開一個新的執行緒去寄信，主程式繼續跑，不用等
        t = threading.Thread(target=self._send_request, args=(text,))
        t.daemon = True # 設定為守護執行緒，主程式結束它也會跟著結束
        t.start()

    def send_startup_report(self, symbol: str, strategy_name: str):
        """發送系統啟動報告"""
        msg = (
            f"🚀 **TaiEx Bot V3 系統啟動**\n"
            f"------------------------\n"
            f"🎯 監控標的: `{symbol}`\n"
            f"🧠 載入策略: `{strategy_name}`\n"
            f"🕒 啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"------------------------\n"
            f"✅ 系統就緒，等待 08:45 開盤..."
        )
        self.send_message(msg)

    def send_signal_notification(self, signal):
        """發送交易訊號通知"""
        icon = "🔴 做多" if "LONG" in str(signal.signal_type) else ("🟢 做空" if "SHORT" in str(signal.signal_type) else "⚪️ 平倉")
        msg = (
            f"⚡️ **交易訊號觸發**\n"
            f"------------------------\n"
            f"{icon} {signal.symbol}\n"
            f"📊 觸發原因: {signal.reason}\n"
            f"🕒 時間: {signal.timestamp.strftime('%H:%M:%S')}"
        )
        self.send_message(msg)