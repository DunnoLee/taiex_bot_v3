import os
import csv
import datetime
from config.settings import Settings

class TradeRecorder:
    """
    交易記錄器 (Black Box)
    功能:
    1. 自動建立日期資料夾 (data/YYYY-MM-DD/)
    2. 將每筆交易即時寫入 trade_log.csv
    3. 支援與舊版工具相容的格式
    """
    def __init__(self, base_dir="data"):
        self.base_dir = base_dir
        self.today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        self.log_dir = os.path.join(self.base_dir, self.today_str)
        self.log_file = os.path.join(self.log_dir, "trade_log.csv")
        
        # 確保資料夾存在
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            print(f"📂 [Recorder] 建立今日資料夾: {self.log_dir}")

        # 如果檔案不存在，寫入 Header (欄位名稱需參考你提供的 sample)
        # 假設舊版格式包含: Time, Action, Price, Qty, Strategy, PnL, Msg
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Symbol", "Action", "Price", "Qty", "Strategy", "Real_PnL", "Message"])

    def write_trade(self, timestamp, symbol, action, price, qty, strategy_name, pnl, msg):
        """寫入一筆交易"""
        try:
            with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    symbol,
                    action,
                    price,
                    qty,
                    strategy_name,
                    pnl,
                    msg
                ])
            # print(f"📝 [Recorder] 交易已記錄") 
        except Exception as e:
            print(f"❌ [Recorder] 寫入失敗: {e}")