import pandas as pd
import os

def slice_history_by_date(input_csv, output_csv, start_date, end_date):
    """
    歷史資料時光切割機
    將巨大的 CSV 歷史檔，依照指定日期區間切出「純牛市」、「純熊市」等測試集。
    """
    print(f"🔪 [Slicer] 正在載入巨大歷史檔案: {input_csv} ...")
    
    if not os.path.exists(input_csv):
        print(f"❌ 找不到檔案 {input_csv}，請確認路徑！")
        return

    df = pd.read_csv(input_csv)
    
    # 確保有時間欄位並轉為 datetime 格式
    if 'datetime' not in df.columns:
        print("❌ CSV 中找不到 'datetime' 欄位！")
        return
        
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # 開始切割
    print(f"✂️ 正在精準切割區間：{start_date} 到 {end_date}")
    mask = (df['datetime'] >= start_date) & (df['datetime'] <= end_date)
    df_sliced = df.loc[mask]
    
    if df_sliced.empty:
        print("⚠️ 警告：這個日期區間內沒有任何資料！")
    else:
        # 存檔
        df_sliced.to_csv(output_csv, index=False)
        print(f"✅ 切割完成！共抽出 {len(df_sliced)} 根 K 棒。")
        print(f"💾 已儲存至專屬戰場：{output_csv}")
        print("-" * 50)

if __name__ == "__main__":
    # 預設的輸入檔案 (請改成你用 downloader 抓下來的大檔案名稱)
    SOURCE_FILE = "data/history/MTX_History_Huge.csv"
    
    # ==========================================
    # 🌍 在這裡定義你要切出來的歷史修羅場！
    # ==========================================
    
    # 1. 2022年 暴力升息緩跌熊市 (測試空單能不能抱住波段)
    slice_history_by_date(
        SOURCE_FILE, 
        "data/history/MTX_2022_Bear.csv", 
        start_date="2022-01-01", 
        end_date="2022-10-31"
    )
    
    # 2. 2023年 盤整洗盤區 (測試防護網夠不夠堅固，會不會被雙巴)
    slice_history_by_date(
        SOURCE_FILE, 
        "data/history/MTX_2023_Chop.csv", 
        start_date="2023-01-01", 
        end_date="2023-05-31"
    )

    # 3. 2020年 疫情 V 轉極端市 (壓力測試最高殿堂)
    slice_history_by_date(
        SOURCE_FILE, 
        "data/history/MTX_2020_Crash.csv", 
        start_date="2020-02-01", 
        end_date="2020-05-31"
    )