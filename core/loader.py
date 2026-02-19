import pandas as pd
import os

def load_history_data(file_path: str, tail_count: int = 15000) -> list:
    """
    通用歷史資料讀取器 (V3.9 相容升級版)
    功能: 讀取 Shioaji 格式 CSV，並回傳標準化的 K 棒列表
    保留原作者的智慧欄位比對邏輯，新增 datetime 與完整 OHLCV 支援。
    """
    if not os.path.exists(file_path):
        print(f"⚠️ [Loader] 找不到檔案: {file_path}")
        return []

    try:
        print(f"📂 [Loader] 讀取歷史資料: {file_path} ...")
        df = pd.read_csv(file_path)
        
        # 1. 清理欄位 (去除空白)
        df.columns = [c.strip() for c in df.columns]
        
        # 2. 智慧欄位對應 (這招保留！)
        col_map = {}
        # 轉換為小寫以進行模糊比對
        lower_cols = {c.lower(): c for c in df.columns}
        
        # --- 找時間欄位 (新增 'datetime' 判斷) ---
        if 'datetime' in lower_cols:
            df['datetime'] = pd.to_datetime(df[lower_cols['datetime']])
        elif 'time' in lower_cols: 
            df['datetime'] = pd.to_datetime(df[lower_cols['time']])
        elif 'date' in lower_cols and 'time' in lower_cols:
             df['datetime'] = pd.to_datetime(df[lower_cols['date']].astype(str) + ' ' + df[lower_cols['time']].astype(str))
        else:
            raise ValueError(f"缺少時間欄位 (Time / datetime)")

        # --- 找收盤價 ---
        if 'close' in lower_cols:
            close_col = lower_cols['close']
        else:
            raise ValueError(f"缺少收盤價欄位 (Close)")

        # (加值服務) 找出其他 OHLCV 欄位，未來擴充策略時備用
        open_col = lower_cols.get('open')
        high_col = lower_cols.get('high')
        low_col = lower_cols.get('low')
        vol_col = lower_cols.get('volume') or lower_cols.get('vol')

        # 3. 取最後 N 筆
        recent_data = df.tail(tail_count)
        
        # 4. 轉為 list of dict
        bars = []
        for _, row in recent_data.iterrows():
            bar_dict = {
                'datetime': row['datetime'],
                'close': float(row[close_col])
            }
            # 安全地塞入其他資料 (如果有找到的話)
            if open_col: bar_dict['open'] = float(row[open_col])
            if high_col: bar_dict['high'] = float(row[high_col])
            if low_col: bar_dict['low'] = float(row[low_col])
            if vol_col: bar_dict['volume'] = int(row[vol_col])

            bars.append(bar_dict)
            
        return bars

    except Exception as e:
        print(f"❌ [Loader] 讀取失敗: {e}")
        return []