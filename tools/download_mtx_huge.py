import os
import sys
import pandas as pd
import shioaji as sj

# 💡 導航修正 (確保能讀到 config)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import Settings

def download_huge_history():
    print("==========================================")
    print("🚀 TaiEx Bot V3 - 小台指(MXF) 重型歷史挖礦機")
    print("==========================================")
    
    api = sj.Shioaji()
    print("🔌 正在連線 Shioaji API...")
    try:
        api.login(
            api_key=Settings.SHIOAJI_API_KEY, 
            secret_key=Settings.SHIOAJI_SECRET_KEY
        )
    except Exception as e:
        print(f"❌ 連線失敗: {e}")
        return

    # 1. 鎖定小台指「連續合約 (MXFR1)」
    try:
        contract = api.Contracts.Futures.MXF.MXFR1
        print(f"📄 鎖定合約: {contract.name} ({contract.code})")
    except Exception as e:
        print(f"❌ 找不到連續合約: {e}")
        api.logout()
        return

    # 2. 設定你要的大範圍時間 (2021 到 2024 年底)
    start_date = "2021-01-01"
    end_date = "2024-12-31"
    
    print(f"🔄 正在向永豐主機請求 K 棒 (從 {start_date} 到 {end_date})...")
    print("⏳ 資料量極大(約30萬筆)，這可能需要 1~3 分鐘，請耐心等候不要關閉程式！")
    
    # 3. 呼叫 API 下載
    kbars = api.kbars(
        contract=contract, 
        start=start_date, 
        end=end_date
    )
    
    df = pd.DataFrame({**kbars})
    if df.empty:
        print("⚠️ 下載失敗，找不到資料。")
        api.logout()
        return

    # 4. 欄位格式化 (統一轉成你的回測引擎看得懂的格式)
    df['ts'] = pd.to_datetime(df['ts'])
    df.rename(columns={
        'ts': 'datetime', 
        'Open': 'open', 'High': 'high', 'Low': 'low', 
        'Close': 'close', 'Volume': 'volume'
    }, inplace=True)
    
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]

    # 5. 確保資料夾存在並存檔
    csv_path = "data/history/MTX_History_Huge.csv"
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    df.to_csv(csv_path, index=False)
    print(f"✅ 挖礦完成！成功下載 {len(df)} 筆小台指 1 分鐘 K 棒。")
    print(f"💾 終極修羅場檔案已儲存至: {csv_path}")

    api.logout()

if __name__ == "__main__":
    download_huge_history()