import itertools
import pandas as pd
import sys
import os
import ast # 用來把字串轉回字典
import multiprocessing

# 💡 導航修正：確保能找到 config 資料夾
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings
from modules.mock_feeder import CsvHistoryFeeder
from modules.mock_executor import MockExecutor
from core.engine import BotEngine
from core.recorder import TradeRecorder

def evaluate_single_combo(args):
    """
    工人函數：專門負責跑「單一一組」參數的回測，並回傳成績。
    args 是一個 tuple: (策略類別, 參數字典, 歷史資料路徑)
    """
    strategy_class, params, history_file = args
    
    # 🤫 絕對靜音模式：把所有 print 丟進黑洞，大幅提升速度，畫面也不會亂
    original_stdout = sys.stdout
    devnull = open(os.devnull, 'w')
    sys.stdout = devnull
    
    try:
        # 1. 準備組件
        strategy = strategy_class(**params)
        executor = MockExecutor(initial_capital=1000000)
        # speed=0 代表極速回測，不等待
        feeder = CsvHistoryFeeder(history_file, speed=0) 
        
        # 2. 組裝引擎 (關閉 Telegram 避免干擾)
        bot = BotEngine(strategy, feeder, executor, symbol="TMF", enable_telegram=False)
        
        # 3. 開跑！
        bot.start()
        
        # 4. 期末強制結算
        bot.inject_flatten_signal(reason="期末結算")
        
        # 5. 計算成績單
        trades_list = getattr(executor, 'trades', [])
        total_trades = len(trades_list)
        win_count = getattr(executor, 'win_count', 0)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        total_pnl = getattr(executor, 'total_pnl', 0)
        
        # 🛡️ 升級：照妖鏡雷達 (多空分離 + 持倉時間版)
        long_pnl = 0
        short_pnl = 0
        total_holding_minutes = 0
        valid_time_records = 0
        
        current_pnl = 0
        peak_pnl = 0
        max_drawdown = 0
        
        # 掃描每一筆交易紀錄
        for t in trades_list:
            if isinstance(t, dict):
                pnl_value = float(t.get('pnl', 0.0))
                direction = str(t.get('direction', ''))
                entry_t = t.get('entry_time')
                exit_t = t.get('exit_time')
                
                # 分離多空損益
                if direction == 'LONG': long_pnl += pnl_value
                elif direction == 'SHORT': short_pnl += pnl_value
                
                # 計算持倉時間
                if entry_t and exit_t:
                    duration = exit_t - entry_t
                    total_holding_minutes += duration.total_seconds() / 60.0
                    valid_time_records += 1
            else:
                pnl_value = float(t) # 為了相容舊帳本
                
            # 計算落袋最大回撤 (Trade-Close MDD)
            current_pnl += pnl_value
            if current_pnl > peak_pnl:
                peak_pnl = current_pnl  
            drawdown = peak_pnl - current_pnl 
            if drawdown > max_drawdown:
                max_drawdown = drawdown 
                
        # 計算風報比
        reward_risk_ratio = round((total_pnl / max_drawdown), 2) if max_drawdown > 0 else float('inf')

        # 計算平均持倉時間格式化
        avg_holding_time = (total_holding_minutes / valid_time_records) if valid_time_records > 0 else 0
        if avg_holding_time > 60:
            holding_str = f"{int(avg_holding_time//60)}h {int(avg_holding_time%60)}m"
        else:
            holding_str = f"{int(avg_holding_time)}m"

        sys.stdout = original_stdout
        devnull.close()
        
        return {
            '參數組合': str(params),
            '總淨利': int(total_pnl),
            'MDD(最大回撤)': int(max_drawdown),
            '風報比': reward_risk_ratio,
            '多單獲利': int(long_pnl),
            '空單獲利': int(short_pnl),
            '平均持倉': holding_str,
            '交易次數': total_trades,
            '勝率(%)': round(win_rate, 2)
        }
        
    except Exception as e:
        sys.stdout = original_stdout
        devnull.close()
        return {
            '參數組合': str(params), '總淨利': 0, 'MDD(最大回撤)': 0,
            '風報比': 0, '多單獲利': 0, '空單獲利': 0, '平均持倉': '0m',
            '交易次數': 0, '勝率(%)': 0, 'Error': str(e)
        }
    
def split_data_for_oos(history_file: str, train_ratio=0.7):
    """資料切割機：將歷史 CSV 切成 70% 訓練集與 30% 盲測集"""
    print(f"🔪 [OOS] 準備切割歷史資料: {history_file}")
    df = pd.read_csv(history_file)
    
    # 確保照時間排序，避免切錯
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.sort_values('datetime', inplace=True)
         
    split_idx = int(len(df) * train_ratio)
    df_is = df.iloc[:split_idx]  # In-Sample (訓練用)
    df_oos = df.iloc[split_idx:] # Out-of-Sample (盲測用)
    
    is_file = history_file.replace('.csv', '_IS.csv')
    oos_file = history_file.replace('.csv', '_OOS.csv')
    
    df_is.to_csv(is_file, index=False)
    df_oos.to_csv(oos_file, index=False)
    
    print(f"📊 總資料量: {len(df)} 筆")
    print(f"🏋️ 訓練集 (In-Sample): {len(df_is)} 筆 -> 供 Optimizer 尋優")
    print(f"🕵️ 盲測集 (Out-of-Sample): {len(df_oos)} 筆 -> 供終極驗證")
    print("-" * 50)
    
    return is_file, oos_file

def run_grid_search(strategy_class, param_grid: dict, history_file: str):
    """
    🔥 多核心極速網格搜索最佳化器 (Multi-Core Grid Search Optimizer)
    """
    print(f"🔍 啟動最佳化引擎: 測試 {strategy_class.__name__} ...")
    
    # 1. 產生所有參數的排列組合
    keys = param_grid.keys()
    values = param_grid.values()
    combinations = list(itertools.product(*values))
    total_tasks = len(combinations)
    print(f"📊 總共需要測試 {total_tasks} 組參數組合")

    # 2. 把任務打包，準備發給工人
    tasks = []
    for combo in combinations:
        params = dict(zip(keys, combo))
        # 每一包任務就是: (策略類別, 這組參數, 歷史資料)
        tasks.append((strategy_class, params, history_file))

    results = []

    # ==========================================
    # 🚀 核心升級：啟動多核心平行運算
    # ==========================================
    num_cores = multiprocessing.cpu_count() # 自動偵測你的電腦有幾顆核心
    # 為了避免電腦卡死，我們留 1 顆核心給系統和滑鼠用
    use_cores = max(1, num_cores - 1) 
    
    print(f"🔥 喚醒 {use_cores} 顆 CPU 核心全速運轉中...\n")

    # 建立多核心資源池
    try: # 👈 加上這行，開始監聽緊急停止信號
        with multiprocessing.Pool(processes=use_cores) as pool:
            # imap_unordered 是一個超強的方法：哪個核心先做完，就先交卷，不用照順序等
            for i, result in enumerate(pool.imap_unordered(evaluate_single_combo, tasks)):
                
                # 只要沒有發生 Error，就把成績收進來
                if 'Error' not in result:
                    results.append(result)
                else:
                    # 🚨 加上這行：讓黑洞裡的錯誤印在螢幕上！
                    print(f"\n❌ [崩潰警告] 參數: {result['參數組合']} | 錯誤原因: {result['Error']}")

                # 🚀 狂暴回報模式：每跑完 1 組就印出來，讓你知道程式還活著！
                percent = ((i + 1) / total_tasks) * 100
                print(f"✅ 核心回報: 已完成 {i + 1} / {total_tasks} 組 (進度: {percent:.1f}%)")

    except KeyboardInterrupt: # 👈 當你按下 Ctrl+C 時，會觸發這裡！
        print("\n\n🚨🚨🚨 接收到指揮官的緊急停機指令 (Ctrl+C)！ 🚨🚨🚨")
        print("正在強制終止所有 CPU 核心，請稍候...")
        pool.terminate() # 殘酷地殺死所有工人
        pool.join()      # 等待他們確實死亡
        sys.exit(0)      # 讓整個主程式直接結束
    # ==========================================

    # 3. 整理並輸出排行榜
    df_results = pd.DataFrame(results)
    
    if df_results.empty:
        print("⚠️ 警告：沒有任何成功的測試結果！")
        return None

    # 依據淨利由高到低排序
    df_results = df_results.sort_values(by='總淨利', ascending=False).reset_index(drop=True)
    
    print("\n" + "="*50)
    print(f"🏆 {strategy_class.__name__} 最佳化排行榜 (Top 20)")
    print("="*50)
    # 把過長的參數字串截斷，畫面才不會爆掉
    df_display = df_results.copy()
    df_display['參數組合'] = df_display['參數組合'].apply(lambda x: x[:60] + " ...}")
    
    # 印出整齊的表格
    print(df_display.head(20).to_string(index=False, justify='center'))
    print("="*50 + "\n")
    
    # 貼心地把第一名的完整參數印在最下面給指揮官複製
    print(f"👑 【榜首完整參數】\n{df_results.iloc[0]['參數組合']}\n")

    return df_results

# ==========================================
# 🚀 執行區塊
# ==========================================
if __name__ == "__main__":
    print("請選擇要最佳化的策略靶場:")
    print("1: 🛡️ 長劍部隊 (MaAdxStrategy) -> 針對 TMF 大數據 (純多頭尋優)")
    print("2: 🗡️ 刺客部隊 (MaAdx2Strategy) -> 針對 2022 熊市 (純空頭尋優)")
    print("3: 非對稱雙向 (AsymMaAdxStrategy)")
    choice = input("輸入代碼 (1/2/3): ")

    strate = None
    HISTORY_FILE = None
    param_grid = {}
    
    if choice == '1':
        from strategies.ma_adx_strategy import MaAdxStrategy
        strate = MaAdxStrategy
        HISTORY_FILE = "data/history/TMF_History.csv"
        # 這是你的霸主參數 (單一測試)
        param_grid = {
            'fast_window': [15],
            'slow_window': [300],
            'enable_adx': [True],
            'adx_threshold': [25],
            'adx_period': [14],
            'resample': [60], 
            'filter_point': [100.0],
            'stop_loss': [800.0],
            'enable_vol_filter': [True],
            'vol_ma_period': [20],
            'vol_multiplier': [1.5],
            'enable_trailing_stop': [True],
            'trailing_trigger': [300],
            'trailing_dist': [300],
            'ma_type_fast': ["EMA"],
            'ma_type_slow': ["SMA"],
            'enable_short': [False] # 純多頭
        }
        #{'fast_window': 15, 'slow_window': 300, 'enable_adx': True, 'adx_threshold': 25, 'adx_period': 14, 'resample': 60, 'filter_point': 100.0, 'stop_loss': 800.0, 'enable_vol_filter': True, 'vol_ma_period': 20, 'vol_multiplier': 1.5, 'enable_trailing_stop': True, 'trailing_trigger': 300, 'trailing_dist': 300, 'ma_type_fast': 'EMA', 'ma_type_slow': 'SMA', 'enable_short': False}
    elif choice == '2':
        from strategies.ma_adx_2_strategy import MaAdx2Strategy
        strate = MaAdx2Strategy
        HISTORY_FILE = "data/history/MTX_2022_Bear.csv"
        # 🚀 擴大網格：讓最佳化器去尋找最佳空軍參數！
        param_grid = {
            'fast_window': [5, 10, 15],      # 測極短的快線
            'slow_window': [60, 120, 240],   # 空頭反彈快，慢線不能太長
            'enable_adx': [True],
            'adx_threshold': [25],
            'adx_period': [14],
            'resample': [15, 30, 60],        # 測 15分、30分、60分K
            'filter_point': [50.0, 100.0],   # 濾網縮小，反應才夠快
            'stop_loss': [400.0, 800.0],
            'enable_vol_filter': [False],    # 先關閉爆量濾網
            'vol_ma_period': [20],
            'vol_multiplier': [1.5],
            'enable_trailing_stop': [True],
            'trailing_trigger': [200, 300],  # 只要賺 200 點就準備跑
            'trailing_dist': [200, 300],     # 反彈 200 點就平倉，絕不留戀！
            'ma_type_fast': ["EMA"],
            'ma_type_slow': ["SMA"],
            'enable_long': [False],          # 關閉多頭
            'enable_short': [True]           # 純空軍
        }
    elif choice == '3':
        from strategies.asym_ma_adx_strategy import AsymMaAdxStrategy
        strate = AsymMaAdxStrategy
        HISTORY_FILE = "data/history/MTX_History_Huge.csv"
        # 🚀 擴大網格：讓最佳化器去尋找最佳空軍參數！
        param_grid = {
            'fast_window': [15],      # 測極短的快線
            'resample': [60],        # 測 15分、30分、60分K
            'filter_point': [100.0],   # 濾網縮小，反應才夠快
            'ma_type_fast': ["EMA"],
            'ma_type_slow': ["SMA"],
            # 🛡️ 左腦 (做多專用)
            'slow_window_long': [300], 
            'enable_vol_long': [True], 
            # 🗡️ 右腦 (做空專用)
            'slow_window_short': [240], 
            'enable_vol_short': [False], 
            # 共用模組
            #'enable_adx': [True],
            'adx_threshold': [25],
            'adx_period': [14],
            'vol_ma_period': [20],
            'vol_multiplier': [1.5],
            # 防禦機制
            'stop_loss': [800.0],
            'enable_trailing_stop': [True],
            'trailing_trigger': [300],  # 只要賺 200 點就準備跑
            'trailing_dist': [300]     # 反彈 200 點就平倉，絕不留戀！
        }
    else:
        print("❌ 輸入錯誤，結束程式。")
        sys.exit(0) # 👈 防呆機制，直接離開

    
    # ==========================================
    # 🛡️ OOS 盲測三部曲
    # ==========================================
    
    # 1. 切割資料 (70% 訓練, 30% 盲測)
    # 🚀 修正：把 train_ratio 從 1 改回 0.7，這樣才有資料做 OOS 盲測
    is_file, oos_file = split_data_for_oos(HISTORY_FILE, train_ratio=0.7)
    
    # 2. 只用 IS (訓練集) 跑網格搜索
    df_results = run_grid_search(strate, param_grid, is_file)
    
    if df_results is not None and not df_results.empty:
        # 3. 抓出排行榜第一名的參數
        best_params_str = df_results.iloc[0]['參數組合']
        best_params = ast.literal_eval(best_params_str)
        
        print("\n" + "👑"*25)
        print(f"🛡️ 啟動樣本外盲測 (Out-of-Sample Validation)")
        print(f"使用 IS 最佳參數: {best_params}")
        print("👑"*25)
        
        # 4. 用 OOS (盲測集) 跑一次第一名的參數
        oos_result = evaluate_single_combo((strate, best_params, oos_file))
        
        # 5. 印出殘酷的對照表
        is_pnl = df_results.iloc[0]['總淨利']
        is_winrate = df_results.iloc[0]['勝率(%)']
        oos_pnl = oos_result['總淨利']
        oos_winrate = oos_result['勝率(%)']
        
        print(f"🏋️ [訓練集 IS] 淨利: ${is_pnl:,.0f} | 勝率: {is_winrate}%")
        print(f"🕵️ [盲測集 OOS] 淨利: ${oos_pnl:,.0f} | 勝率: {oos_winrate}%")
        
        print("\n📝 盲測結果判定：")
        if oos_pnl > 0:
            print("✅ 恭喜指揮官！策略通過盲測，沒有嚴重的過度擬合，具備實戰價值！")
        else:
            print("❌ 警告！策略在盲測集陣亡。出現過度擬合 (Overfitting)，請減少參數或放寬濾網！")