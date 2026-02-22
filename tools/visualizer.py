import pandas as pd
import matplotlib.pyplot as plt
import sys
import os

# --- 設定 ---
# 為了畫出背景 K 線，我們需要讀取歷史資料
# 請確認這個路徑是正確的
HISTORY_FILE = "data/history/TMF_History.csv" 

def visualize(log_path):
    print(f"🎨 [Visualizer] 正在繪製: {log_path} ...")
    
    if not os.path.exists(log_path):
        print(f"❌ 找不到 Log 檔案: {log_path}")
        return
    
    if not os.path.exists(HISTORY_FILE):
        print(f"❌ 找不到歷史 K 線檔案: {HISTORY_FILE} (無法繪製背景)")
        return

    try:
        # 1. 讀取交易 Log
        df_log = pd.read_csv(log_path)
        df_log['Time'] = pd.to_datetime(df_log['Time'])
        
        # 2. 讀取歷史 K 線 (背景)
        print(f"📂 讀取歷史資料: {HISTORY_FILE} ...")
        df_hist = pd.read_csv(HISTORY_FILE)
        df_hist.columns = [c.strip() for c in df_hist.columns] # 清理欄位
        
        # 處理 Shioaji 時間格式
        if 'datetime' in df_hist.columns:
            df_hist['datetime'] = pd.to_datetime(df_hist['datetime'])
        else:
            print("❌ 歷史資料缺少 'Time' 欄位")
            return
            
        df_hist.set_index('datetime', inplace=True)
        
        # 3. 裁切歷史資料範圍 (只畫回測期間)
        start_time = df_log['Time'].min()
        end_time = df_log['Time'].max()
        
        # 稍微前後多抓一點時間，讓圖好看一點
        margin = pd.Timedelta(hours=4)
        mask = (df_hist.index >= start_time - margin) & (df_hist.index <= end_time + margin)
        df_view = df_hist.loc[mask]
        
        if df_view.empty:
            print("⚠️ 歷史資料與 Log 時間對不上，無法繪圖")
            return

        # 4. 開始繪圖
        plt.figure(figsize=(15, 8))
        
        # 畫價格線 (用收盤價代替 K 線，比較快)
        plt.plot(df_view.index, df_view['close'], label='Price', color='gray', alpha=0.5, linewidth=1)
        
        # -------------------------------------------------------
        # 💡 新增邏輯：區分「普通買賣」與「停損出場」
        # -------------------------------------------------------

        # 標記買賣點
        # 1. 找出所有交易點
        buys = df_log[df_log['Action'].isin(['LONG', 'BUY', 'FLATTEN_SHORT'])]
        sells = df_log[df_log['Action'].isin(['SHORT', 'SELL', 'FLATTEN_LONG'])]
        
        # 2. 進一步篩選「停損單」 (Message 包含 "Stop Loss")
        # 注意：要在 pandas 處理字串包含，需確保 Message 欄位不是 NaN
        df_log['Message'] = df_log['Message'].fillna('')
        stop_losses = df_log[df_log['Message'].str.contains('Stop Loss', case=False)]
        
        # 3. 畫「普通買進」 (排除停損單，避免重疊畫)
        # 這裡簡單起見，我們畫所有買單，然後把停損單「疊」在上面或用不同顏色
        
        # 🔴 普通買點 (紅上三角)
        if not buys.empty:
            plt.scatter(buys['Time'], buys['Price'], marker='^', color='red', s=80, label='Buy', zorder=5)

        # 🟢 普通賣點 (綠下三角)
        if not sells.empty:
            plt.scatter(sells['Time'], sells['Price'], marker='v', color='green', s=80, label='Sell', zorder=5)

        # ❌ 停損出場 (黑叉叉) - 這是你要的！
        if not stop_losses.empty:
            plt.scatter(stop_losses['Time'], stop_losses['Price'], marker='x', color='black', s=150, linewidths=3, label='STOP LOSS', zorder=10)
            
        plt.title(f"TaiEx Bot V3 Backtest Result\n({start_time.date()} ~ {end_time.date()})")
        plt.xlabel("Date")
        plt.ylabel("Price")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # 顯示圖表
        print("🖼️ 圖表繪製完成，正在開啟視窗...")
        plt.show()

    except Exception as e:
        print(f"❌ 繪圖失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 如果有傳入參數就用參數，否則用預設路徑
    log_path = sys.argv[1] if len(sys.argv) > 1 else "data/backtest_results/backtest_log.csv"
    visualize(log_path)