import pandas as pd
import numpy as np
from collections import deque
from core.base_strategy import BaseStrategy  # <--- 繼承這個
from core.event import BarEvent, TickEvent, SignalEvent, SignalType, EventType
from config.settings import Settings

class MAStrategy(BaseStrategy):
    """
    雙均線策略 V3.9 (Re-integrated)
    
    結合:
    1. BaseStrategy 的標準介面 (set_position, name).
    2. V3.4 的 Resample 與 Deque 優化邏輯.
    3. Settings 自動參數讀取.
    """
    def __init__(self, fast_window=None, slow_window=None, threshold=None, resample=None, stop_loss=None):
        # 1. 處理參數預設值 (優先使用傳入參數，否則讀 Settings)
        self.fast_window = fast_window if fast_window else getattr(Settings, 'STRATEGY_MA_FAST', 30)
        self.slow_window = slow_window if slow_window else getattr(Settings, 'STRATEGY_MA_SLOW', 240)
        self.threshold = threshold if threshold is not None else getattr(Settings, 'STRATEGY_THRESHOLD', 5.0)
        self.resample_min = resample if resample else getattr(Settings, 'STRATEGY_RESAMPLE_MIN', 5)
        self.stop_loss = stop_loss if stop_loss else getattr(Settings, 'STOP_LOSS_POINT', 300.0)

        # 2. 初始化父類別 (註冊名稱)
        name = f"MA({self.fast_window}/{self.slow_window})"
        super().__init__(name=name)
        
        # 3. 覆蓋父類別的 raw_bars，改用 deque 以提升效能
        # 父類別是用 list，這裡改用 deque (maxlen 會自動丟棄舊資料)
        self.raw_bars = deque(maxlen=5000)
        
        # entry_price 與 position 父類別已經有了，這裡不需要再宣告
        # self.silent_mode 用來控制 debug 輸出
        self.silent_mode = False 

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        """
        核心邏輯
        """
        # 1. 檢查硬止損 (Hard Stop Loss)
        # 注意: self.position 和 self.entry_price 來自父類別
        sl_signal = self._check_stop_loss(bar.close, bar.symbol)
        if sl_signal: return sl_signal

        # 2. 儲存資料 (存成 dict 以便轉 DataFrame)
        self.raw_bars.append({
            'datetime': bar.timestamp,
            'close': bar.close
        })

        # 3. 資料量檢查 (還不夠做一次 Resample 就不算)
        # 例如: 240根 * 5分鐘 = 需要 1200 根原始 1分K
        required_raw_bars = self.slow_window * self.resample_min
        if len(self.raw_bars) < required_raw_bars:
            return None

        # 4. 執行 Resample (關鍵邏輯！)
        # 將原始 K 棒轉為 Pandas DataFrame
        df = pd.DataFrame(self.raw_bars)
        df.set_index('datetime', inplace=True)
        
        # 重取樣：例如 '5min'，取最後一筆 (last)
        # dropna() 是為了避免剛開始 resample 時產生 NaN
        resampled = df['close'].resample(f"{self.resample_min}min").last().dropna()

        # Resample 後長度不夠也不算
        if len(resampled) < self.slow_window:
            return None

        # 5. 計算 MA
        # 使用 iloc[-1] 取最新的一個值
        ma_fast = resampled.rolling(window=self.fast_window).mean().iloc[-1]
        ma_slow = resampled.rolling(window=self.slow_window).mean().iloc[-1]
        
        if np.isnan(ma_fast) or np.isnan(ma_slow): return None

        current_price = bar.close # 訊號觸發以當前價格為準

        # 6. 產生訊號
        signal = None
        diff = ma_fast - ma_slow
        is_bullish = diff > self.threshold
        is_bearish = diff < -self.threshold

        # Debug 顯示 (每 5 分鐘印一次，避免洗版)
        if not self.silent_mode and bar.timestamp.minute % 5 == 0 and bar.timestamp.second == 0:
            status = "WAIT"
            if is_bullish: status = "BULL ZONE"
            if is_bearish: status = "BEAR ZONE"
            # print(f"🕵️ [{self.name}] P:{current_price:.0f} | Diff:{diff:.1f} ({status})")

        # 進場邏輯
        if is_bullish and self.position <= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL,
                symbol=bar.symbol,
                signal_type=SignalType.LONG,
                strength=1.0,
                reason=f"Golden Cross (Diff {diff:.1f} > {self.threshold})"
            )
            # 注意: entry_price 在 Engine 成交後會更新，但策略這裡也可以先記一下
            # 實際更新應由 Engine 回呼 set_position 時處理，或在此暫存
            self.entry_price = current_price

        elif is_bearish and self.position >= 0:
            signal = SignalEvent(
                type=EventType.SIGNAL,
                symbol=bar.symbol,
                signal_type=SignalType.SHORT,
                strength=1.0,
                reason=f"Death Cross (Diff {diff:.1f} < -{self.threshold})"
            )
            self.entry_price = current_price

        return signal

    def _check_stop_loss(self, current_price: float, symbol: str) -> SignalEvent:
        """停損檢查"""
        if self.position == 0: return None
        
        # 計算目前浮動損益 (Points)
        if self.position > 0:
            pnl = current_price - self.entry_price
        else:
            pnl = self.entry_price - current_price
        
        # 觸發停損
        if pnl <= -self.stop_loss:
            return SignalEvent(
                type=EventType.SIGNAL,
                symbol=symbol, 
                signal_type=SignalType.FLATTEN, 
                reason=f"STOP LOSS triggered (-{self.stop_loss:.0f} pts)"
            )
        return None

    def load_history_bars(self, bars_list: list):
        """
        覆蓋父類別方法
        因為我們用 deque 存 dict，父類別可能存物件，這裡統一格式
        """
        print(f"🔄 [{self.name}] 正在預載 {len(bars_list)} 根歷史 K 棒...")
        
        for bar in bars_list:
            # 判斷傳入的是 dict 還是 BarEvent 物件，做兼容處理
            if isinstance(bar, dict):
                data = {
                    'datetime': bar['datetime'],
                    'close': bar['close']
                }
            else:
                data = {
                    'datetime': bar.timestamp,
                    'close': bar.close
                }
            self.raw_bars.append(data)
            
        print(f"✅ [{self.name}] 預載完成，目前緩衝區長度: {len(self.raw_bars)}")