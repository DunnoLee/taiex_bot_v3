import pandas as pd
import os

def rescue_history_data():
    file_path = "data/history/TMF_History.csv"
    if not os.path.exists(file_path):
         print("找不到檔案！")
         return

    print("🛠️ 正在啟動 CSV 資料急救包...")
    df = pd.read_csv(file_path)
    print(f"原始欄位: {list(df.columns)}")

    # 欄位配對表 (舊大寫 : 新小寫)
    pairs = [
        ('Time', 'datetime'), ('time', 'datetime'), 
        ('Open', 'open'), ('High', 'high'), 
        ('Low', 'low'), ('Close', 'close'), 
        ('Volume', 'volume')
    ]

    for old_col, new_col in pairs:
        if old_col in df.columns:
            if new_col in df.columns and old_col != new_col:
                # 兩者都存在：把舊欄位的資料填入新欄位的 NaN 空缺中
                df[new_col] = df[new_col].combine_first(df[old_col])
                df.drop(columns=[old_col], inplace=True)
            elif old_col != new_col:
                # 只有舊欄位：直接改名
                df.rename(columns={old_col: new_col}, inplace=True)

    # 確保只留下我們需要的標準欄位
    keep_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
    final_cols = [c for c in keep_cols if c in df.columns]
    df = df[final_cols]

    # 重新排序與存檔
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.sort_values('datetime', inplace=True)
    df.to_csv(file_path, index=False)
    
    print(f"✅ 修復完成！目前欄位: {list(df.columns)}")

if __name__ == "__main__":
    rescue_history_data()