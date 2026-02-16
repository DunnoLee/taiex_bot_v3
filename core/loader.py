import pandas as pd
import os

def load_history_data(file_path: str, tail_count: int = 3000) -> list:
    """
    通用歷史資料讀取器
    功能: 讀取 Shioaji 格式 CSV，並回傳標準化的 K 棒列表
    """
    if not os.path.exists(file_path):
        print(f"⚠️ [Loader] 找不到檔案: {file_path}")
        return []

    try:
        print(f"📂 [Loader] 讀取歷史資料: {file_path} ...")
        df = pd.read_csv(file_path)
        
        # 1. 清理欄位 (去除空白)
        df.columns = [c.strip() for c in df.columns]
        
        # 2. 智慧欄位對應
        col_map = {}
        # 轉換為小寫以進行模糊比對
        lower_cols = {c.lower(): c for c in df.columns}
        
        # 找時間欄位
        if 'time' in lower_cols: 
            df['datetime'] = pd.to_datetime(df[lower_cols['time']])
        elif 'date' in lower_cols and 'time' in lower_cols:
             df['datetime'] = pd.to_datetime(df[lower_cols['date']].astype(str) + ' ' + df[lower_cols['time']].astype(str))
        else:
            raise ValueError(f"缺少時間欄位 (Time)")

        # 找收盤價
        if 'close' in lower_cols:
            close_col = lower_cols['close']
        else:
            raise ValueError(f"缺少收盤價欄位 (Close)")

        # 3. 取最後 N 筆
        recent_data = df.tail(tail_count)
        
        # 4. 轉為 list of dict
        bars = []
        for _, row in recent_data.iterrows():
            bars.append({
                'datetime': row['datetime'],
                'close': float(row[close_col])
            })
            
        return bars

    except Exception as e:
        print(f"❌ [Loader] 讀取失敗: {e}")
        return []