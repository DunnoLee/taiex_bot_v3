import os
import sys
import pandas as pd
import shioaji as sj
from datetime import datetime, timedelta

# 💡 導航修正
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Settings

class UniversalDownloader:
    """
    TaiEx Bot V3 智慧歷史資料下載器
    功能：自動比對現有 CSV，只下載缺少的資料並接合去重。
    """
    def __init__(self):
        self.api = sj.Shioaji()
        self.target_contract = getattr(Settings, "TARGET_CONTRACT", "TMF202603")
        self.csv_path = "data/history/TMF_History.csv"
        
        # 確保資料夾存在
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)

    def _resolve_code(self, target_str):
        """通用合約翻譯 (例如 TMF202603 -> TMFC6)"""
        try:
            if len(target_str) < 9: return target_str
            symbol = target_str[:3]
            year_str = target_str[3:7]
            month_str = target_str[7:]
            month_map = {"01":"A", "02":"B", "03":"C", "04":"D", "05":"E", "06":"F", "07":"G", "08":"H", "09":"I", "10":"J", "11":"K", "12":"L"}
            month_code = month_map.get(month_str)
            year_code = year_str[-1]
            return f"{symbol}{month_code}{year_code}"
        except: return target_str

    def run(self):
        print("🔌 正在連線 Shioaji API...")
        try:
            self.api.login(
                api_key=Settings.SHIOAJI_API_KEY, 
                secret_key=Settings.SHIOAJI_SECRET_KEY
            )
        except Exception as e:
            print(f"❌ 連線失敗: {e}")
            return

        # 1. 解析合約
        code = self._resolve_code(self.target_contract)
        try:
            contract = self.api.Contracts.Futures.TMF[code]
            print(f"📄 鎖定合約: {contract.name} ({contract.code})")
        except Exception as e:
            print(f"❌ 找不到合約 {self.target_contract}: {e}")
            self.api.logout()
            return

        # 2. 判斷起始時間 (Smart Append)
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d") # 預設抓 30 天
        existing_df = pd.DataFrame()
        
        if os.path.exists(self.csv_path):
            try:
                existing_df = pd.read_csv(self.csv_path)
                
                # 💡 [修復關鍵] 在合併前，強制把舊 CSV 的標題全部轉成小寫並清理
                existing_df.columns = existing_df.columns.str.strip().str.lower()
                
                # 相容舊版的 time
                if 'time' in existing_df.columns:
                    existing_df.rename(columns={'time': 'datetime'}, inplace=True)
                
                if 'datetime' in existing_df.columns:
                    existing_df['datetime'] = pd.to_datetime(existing_df['datetime'])
                    last_time = existing_df['datetime'].max()
                    start_date = (last_time - timedelta(days=1)).strftime("%Y-%m-%d")
                    print(f"📂 發現現有資料，最後時間: {last_time}。將從 {start_date} 開始回補。")
            except Exception as e:
                print(f"⚠️ 讀取現有 CSV 失敗 ({e})，將重新下載。")

        # 3. 呼叫 API 下載
        print(f"🔄 正在下載 K 棒 (從 {start_date} 到今日)...")
        kbars = self.api.kbars(
            contract=contract, 
            start=start_date, 
            end=datetime.now().strftime("%Y-%m-%d")
        )
        
        new_df = pd.DataFrame({**kbars})
        if new_df.empty:
            print("⚠️ 找不到任何新資料 (可能是休市或尚未開盤)。")
            self.api.logout()
            return

        # 4. 欄位格式化
        new_df['ts'] = pd.to_datetime(new_df['ts'])
        new_df.rename(columns={
            'ts': 'datetime', 
            'Open': 'open', 'High': 'high', 'Low': 'low', 
            'Close': 'close', 'Volume': 'volume'
        }, inplace=True)
        
        # 只保留我們需要的欄位
        new_df = new_df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
        print(f"📥 成功下載 {len(new_df)} 筆新資料。")

        # 5. 合併與去重 (Merge & Drop Duplicates)
        if not existing_df.empty:
            final_df = pd.concat([existing_df, new_df], ignore_index=True)
            # 以 datetime 為準，去除重複的 K 棒 (保留最後抓到的最新資料)
            final_df.drop_duplicates(subset=['datetime'], keep='last', inplace=True)
        else:
            final_df = new_df

        # 確保照時間排序
        final_df.sort_values('datetime', inplace=True)
        final_df.reset_index(drop=True, inplace=True)

        # 6. 存檔
        final_df.to_csv(self.csv_path, index=False)
        print(f"✅ 更新完成！目前資料庫共有 {len(final_df)} 筆 K 棒。")
        print(f"   => 儲存路徑: {self.csv_path}")

        self.api.logout()

if __name__ == "__main__":
    print("==========================================")
    print("🚀 TaiEx Bot V3 - 歷史資料更新工具")
    print("==========================================")
    downloader = UniversalDownloader()
    downloader.run()