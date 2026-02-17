import sys
import os
import pandas as pd
import glob

# 💡 導航修正：確保能找到 config 資料夾
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def merge_tmf_history(product_prefix="TMF"):
    history_dir = "data/history"
    # 搜尋所有 TMF2026XX_1min.csv 格式的檔案
    file_pattern = os.path.join(history_dir, f"{product_prefix}2026*_1min.csv")
    all_files = glob.glob(file_pattern)
    
    if not all_files:
        print(f"❌ 在 {history_dir} 找不到任何符合 {product_prefix} 的 CSV 檔案。")
        return

    print(f"📚 發現 {len(all_files)} 個檔案，準備開始大合併...")
    
    li = []
    for filename in all_files:
        print(f"📖 讀取中: {os.path.basename(filename)}")
        df = pd.read_csv(filename)
        
        # 💡 下載器已經改好名字了，這裡直接確保 Time 是日期格式
        if 'Time' in df.columns:
            df['Time'] = pd.to_datetime(df['Time'])
            li.append(df)
        else:
            print(f"⚠️ 警告：檔案 {filename} 裡面找不到 'Time' 欄位，跳過此檔案。")

    # 1. 垂直合併所有 DataFrame
    full_df = pd.concat(li, axis=0, ignore_index=True)

    # 2. 💡 關鍵：排序與去重
    # 因為不同月份合約在時間上會有大量重疊，我們保留最新的數據
    print("🧹 正在進行資料清洗 (排序與移除重複時間)...")
    full_df = full_df.sort_values(by='Time')
    
    # 如果時間相同，保留最後出現的一筆 (通常是越晚下載的越準)
    full_df = full_df.drop_duplicates(subset=['Time'], keep='last')
    
    # 3. 儲存成果
    output_path = f"data/history/{product_prefix}_FULL_REPLAY.csv"
    full_df.to_csv(output_path, index=False)
    
    print(f"---")
    print(f"✅ 合併成功！")
    print(f"📍 最終檔案: {output_path}")
    print(f"⏳ 時間起點: {full_df['Time'].min()}")
    print(f"⏳ 時間終點: {full_df['Time'].max()}")
    print(f"📊 總共累積 {len(full_df)} 根 1 分鐘 K 棒")

if __name__ == "__main__":
    # 如果你想合併其他商品，只需改這裡，例如 "MTX"
    merge_tmf_history("TMF")