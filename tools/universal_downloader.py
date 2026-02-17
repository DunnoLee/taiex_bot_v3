import sys
import os
import shioaji as sj
import pandas as pd
import time

# 💡 導航修正
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Settings

class DataDownloader:
    def __init__(self):
        self.api = sj.Shioaji()
        self.api.login(Settings.SHIOAJI_API_KEY, Settings.SHIOAJI_SECRET_KEY)
        print("🔍 正在同步全市場期貨索引...")
        self.api.fetch_contracts([sj.constant.SecurityType.Future])
        time.sleep(1)

    def _get_exchange_code(self, prefix, month_str):
        """
        💡 翻譯機：將 202602 轉為 TMFB6
        """
        month_map = {
            "01":"A", "02":"B", "03":"C", "04":"D", "05":"E", "06":"F",
            "07":"G", "08":"H", "09":"I", "10":"J", "11":"K", "12":"L"
        }
        year_last_digit = month_str[3] # 取 2026 的 6
        month_code = month_map.get(month_str[4:]) # 取 202602 的 02
        return f"{prefix}{month_code}{year_last_digit}"

    def download(self, prefix, months):
        save_dir = "data/history"
        os.makedirs(save_dir, exist_ok=True)

        for month in months:
            # 自動翻譯：202602 -> TMFB6
            ex_code = self._get_exchange_code(prefix, month)
            print(f"------------------------------------------")
            print(f"📡 正在搜尋合約: {month} (交易所代碼: {ex_code})...")
            
            try:
                # 這次我們直接從 TMF 群組裡找這個翻譯後的代碼
                group = getattr(self.api.Contracts.Futures, prefix)
                target_contract = next((c for c in group if c.code == ex_code), None)

                if not target_contract:
                    print(f"❌ 依然找不到 {ex_code}。")
                    continue

                print(f"✅ 找到合約 {ex_code}！正在下載歷史 K 線...")
                kbars = self.api.kbars(
                    contract=target_contract, 
                    start="2025-01-01", 
                    end="2026-12-31"
                )
                
                df = pd.DataFrame({**kbars})
                if df.empty:
                    print(f"⚠️ {ex_code} 下載成功但無資料。")
                    continue
                
                # 欄位轉換：確保合併器能讀取
                df.rename(columns={'ts': 'Time'}, inplace=True)
                df['Time'] = pd.to_datetime(df['Time'])
                
                # 儲存檔名還是用你習慣的格式，方便辨認
                file_path = f"{save_dir}/{prefix}{month}_1min.csv"
                df.to_csv(file_path, index=False)
                print(f"🎊 {month} 下載成功！筆數: {len(df)}")
                
            except Exception as e:
                print(f"❌ {month} 執行失敗: {e}")

        self.api.logout()

if __name__ == "__main__":
    downloader = DataDownloader()
    # 💡 這樣輸入 202602，它就會自動去找 TMFB6
    downloader.download("TMF", ["202602", "202603"])