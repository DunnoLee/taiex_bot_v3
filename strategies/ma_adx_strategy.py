import pandas as pd
import numpy as np
from collections import deque
from core.base_strategy import BaseStrategy
from core.event import BarEvent, SignalEvent, SignalType, EventType
from config.settings import Settings

class MaAdxStrategy(BaseStrategy):
    """
    【樂高模組化】MA + 趨勢與籌碼多重濾網策略 (V3.8 Ultimate)
    特色：所有指標與防禦機制皆可透過「開關 (True/False)」自由組合！
    """
    def __init__(self, 
                 # ==========================================
                 # 核心動力：時間級別與均線交叉
                 # ==========================================
                 fast_window=10, slow_window=300, 
                 resample=15,         # 決定策略的大腦看幾分 K (例如 60 = 小時線)
                 filter_point=80.0,  # 均線交叉需要超過幾點才算數 (防震盪寬濾網)
                 
                 # ==========================================
                 # 模組 A：ADX 趨勢強度濾網
                 # ==========================================
                 enable_adx=True,     # 👈 [開關] 是否啟用 ADX 趨勢確認
                 adx_period=14, adx_threshold=25,
                 
                 # ==========================================
                 # 模組 B：Volume 爆量籌碼濾網
                 # ==========================================
                 enable_vol_filter=True, # 👈 [開關] 是否啟用爆量突破確認
                 vol_ma_period=20, vol_multiplier=1.5,
                 
                 # ==========================================
                 # 模組 C：防禦機制 (保命與鎖利)
                 # ==========================================
                 stop_loss=400.0,         # 基礎硬停損 (永遠開啟)
                 enable_trailing_stop=True, # 👈 [開關] 是否啟用移動停利
                 trailing_trigger=300.0,  # 賺超過幾點開始啟動追蹤
                 trailing_dist=300.0      # 從最高/低點回檔幾點就平倉
                 ):
        
        # 組合出漂亮的策略名稱，方便在日誌和 Telegram 中辨識
        name_parts = [f"MA({fast_window}/{slow_window}|{resample}m)"]
        if enable_adx: name_parts.append(f"ADX>{adx_threshold}")
        if enable_vol_filter: name_parts.append(f"Volx{vol_multiplier}")
        if enable_trailing_stop: name_parts.append(f"Trail({trailing_trigger}/{trailing_dist})")
        super().__init__(name=" + ".join(name_parts))
        
        # --- 綁定核心參數 ---
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.filter_point = filter_point
        self.resample_min = resample
        self.stop_loss = stop_loss
        
        # --- 綁定模組參數 ---
        self.enable_adx = enable_adx
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        
        self.enable_vol_filter = enable_vol_filter
        self.vol_ma_period = vol_ma_period
        self.vol_multiplier = vol_multiplier
        
        self.enable_trailing_stop = enable_trailing_stop
        self.trailing_trigger = trailing_trigger
        self.trailing_dist = trailing_dist
        
        # --- 策略狀態與快取 ---
        self.raw_bars = deque(maxlen=5000)
        self.silent_mode = True

        self.current_bucket_time = None 
        self.cached_ma_fast = None
        self.cached_ma_slow = None
        self.cached_adx = None
        self.cached_vol_ma = None
        self.cached_current_vol = None

        # 👇 加上這兩行：用來記憶上一根 60 分 K 的均線位置
        self.prev_ma_fast = None 
        self.prev_ma_slow = None

        self.bars_resampled = deque(maxlen=400) # 存放壓縮好的大顆粒 K 棒
        self.temp_1m_bars = []                  # 暫存區

        # 移動停利專用狀態記憶
        self.highest_price = 0.0
        self.lowest_price = float('inf')

        # 🚀 新增：波段鎖定記憶體 (1=已做多, -1=已做空, 0=全新波段)
        self.last_traded_wave = 0

    def on_bar(self, bar: BarEvent) -> SignalEvent:
        # ==========================================
        # 🛡️ 執行層 (1 分鐘微觀視角)：防禦機制掃描
        # 這段邏輯每 1 分鐘都會檢查一次，保護你的資金
        # ==========================================
        self.latest_price = bar.close
        current_price = bar.close
        
        # 1. 永遠開啟：硬停損檢查
        if self.position != 0:
            pnl = (current_price - self.entry_price) if self.position > 0 else (self.entry_price - current_price)
            if pnl <= -self.stop_loss:
                return SignalEvent(
                    type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, 
                    reason=f"🩸 硬停損觸發 (-{self.stop_loss:.0f} pts)"
                )

        # 2. 模組 C：移動停利 (如果開關有打開)
        if self.enable_trailing_stop and self.position != 0:
            if self.position > 0: # 多單移動停利
                self.highest_price = max(self.highest_price, bar.high)
                # 如果最高獲利已經超過啟動門檻...
                if (self.highest_price - self.entry_price) >= self.trailing_trigger:
                    # 如果從最高點跌落超過設定距離，就獲利了結！
                    if current_price <= (self.highest_price - self.trailing_dist):
                        return SignalEvent(
                            type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, 
                            reason=f"💰 多單移動停利！(獲利鎖定於 {current_price})"
                        )
                        
            elif self.position < 0: # 空單移動停利
                self.lowest_price = min(self.lowest_price, bar.low)
                if (self.entry_price - self.lowest_price) >= self.trailing_trigger:
                    if current_price >= (self.lowest_price + self.trailing_dist):
                        return SignalEvent(
                            type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.FLATTEN, 
                            reason=f"💰 空單移動停利！(獲利鎖定於 {current_price})"
                        )


        # ==========================================
        # ⚙️ 運算層：K 棒降維壓縮機 (將 1分K 轉成 N分K)
        # ==========================================
        bucket_minute = (bar.timestamp.minute // self.resample_min) * self.resample_min
        bucket_time = bar.timestamp.replace(minute=bucket_minute, second=0, microsecond=0)

        if self.current_bucket_time != bucket_time:
            if self.temp_1m_bars:
                self.bars_resampled.append({
                    'high': max(b.high for b in self.temp_1m_bars),
                    'low': min(b.low for b in self.temp_1m_bars),
                    'close': self.temp_1m_bars[-1].close,
                    'volume': sum(b.volume for b in self.temp_1m_bars)
                })
            
            self.temp_1m_bars = [bar]
            self.current_bucket_time = bucket_time

            # --- 只有換 K 棒時，才呼叫 Pandas 算指標 ---
            if len(self.bars_resampled) >= self.slow_window + max(self.adx_period, self.vol_ma_period) * 2:
                df_resampled = pd.DataFrame(self.bars_resampled)
                
                # 👇 先把目前的快慢線存進 prev (變成舊的)
                self.prev_ma_fast = self.cached_ma_fast
                self.prev_ma_slow = self.cached_ma_slow

                # 基礎動力：計算 MA
                self.cached_ma_fast = df_resampled['close'].rolling(window=self.fast_window).mean().iloc[-1]
                self.cached_ma_slow = df_resampled['close'].rolling(window=self.slow_window).mean().iloc[-1]

                # 模組 A：計算 ADX (如果開關打開)
                if self.enable_adx:
                    df_adx = df_resampled.copy()
                    df_adx['prev_close'] = df_adx['close'].shift(1)
                    df_adx['tr1'] = df_adx['high'] - df_adx['low']
                    df_adx['tr2'] = (df_adx['high'] - df_adx['prev_close']).abs()
                    df_adx['tr3'] = (df_adx['low'] - df_adx['prev_close']).abs()
                    df_adx['tr'] = df_adx[['tr1', 'tr2', 'tr3']].max(axis=1)
                    df_adx['up_move'] = df_adx['high'] - df_adx['high'].shift(1)
                    df_adx['down_move'] = df_adx['low'].shift(1) - df_adx['low']
                    df_adx['+dm'] = np.where((df_adx['up_move'] > df_adx['down_move']) & (df_adx['up_move'] > 0), df_adx['up_move'], 0)
                    df_adx['-dm'] = np.where((df_adx['down_move'] > df_adx['up_move']) & (df_adx['down_move'] > 0), df_adx['down_move'], 0)
                    atr = df_adx['tr'].ewm(span=self.adx_period, adjust=False).mean()
                    plus_di = 100 * (df_adx['+dm'].ewm(span=self.adx_period, adjust=False).mean() / atr)
                    minus_di = 100 * (df_adx['-dm'].ewm(span=self.adx_period, adjust=False).mean() / atr)
                    di_sum = plus_di + minus_di
                    di_sum = di_sum.replace(0, np.nan) 
                    dx = 100 * (abs(plus_di - minus_di) / di_sum)
                    self.cached_adx = dx.ewm(span=self.adx_period, adjust=False).mean().iloc[-1]

                # 模組 B：計算成交量均線 (如果開關打開)
                if self.enable_vol_filter and len(df_resampled) >= self.vol_ma_period:
                    self.cached_vol_ma = df_resampled['volume'].rolling(window=self.vol_ma_period).mean().iloc[-1]
                    self.cached_current_vol = df_resampled['volume'].iloc[-1]

        else:
            self.temp_1m_bars.append(bar)


        # ==========================================
        # 🎯 戰術層 (大顆粒視角)：進出場邏輯 (樂高組裝區)
        # ==========================================
        
        # 確保基礎均線已算好
        if self.cached_ma_fast is None or np.isnan(self.cached_ma_fast): 
            return None

        # 1. 計算目前的「波段狀態 (Wave State)」
        ma_diff = self.cached_ma_fast - self.cached_ma_slow
        
        current_wave = 0
        if ma_diff > self.filter_point:
            current_wave = 1   # 多頭波段
        elif ma_diff < -self.filter_point:
            current_wave = -1  # 空頭波段
        else:
            # 🌈 關鍵防護：一旦快慢線差距縮小，回到盤整區，就解除上一波的鎖定！
            self.last_traded_wave = 0

        # 2. 判斷是否為「尚未進場過」的新趨勢
        is_bullish = (current_wave == 1) and (self.last_traded_wave != 1)
        is_bearish = (current_wave == -1) and (self.last_traded_wave != -1)
        
        # 3. 模組檢查：預設全開綠燈 (True)，如果有開關被打開，才進行嚴格檢查
        adx_passed = True
        if self.enable_adx:
            adx_passed = (self.cached_adx is not None) and (self.cached_adx > self.adx_threshold)
            
        vol_passed = True
        if self.enable_vol_filter:
            vol_passed = (self.cached_vol_ma is not None) and (self.cached_current_vol > (self.cached_vol_ma * self.vol_multiplier))

        signal = None
        reason_parts = []

        # 4. 終極開火授權：必須是新波段，且所有濾網都亮綠燈！
        if is_bullish and adx_passed and vol_passed and self.position <= 0:
            
            self.last_traded_wave = 1 # 🔒 鎖定這個多頭波段，被洗掉也不准再追高！
            
            if self.filter_point > 0: reason_parts.append(f"金叉突破(+{self.filter_point}點)")
            else: reason_parts.append("MA金叉")
            
            if self.enable_adx: reason_parts.append(f"ADX強勢({self.cached_adx:.1f})")
            if self.enable_vol_filter: reason_parts.append(f"爆量({self.vol_multiplier}x)")
            
            signal = SignalEvent(
                type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.LONG, strength=1.0,
                reason=" | ".join(reason_parts)
            )
            self.entry_price = current_price
            self.highest_price = current_price
            self.lowest_price = current_price

        elif is_bearish and adx_passed and vol_passed and self.position >= 0:
            
            self.last_traded_wave = -1 # 🔒 鎖定這個空頭波段
            
            if self.filter_point > 0: reason_parts.append(f"死叉跌破(-{self.filter_point}點)")
            else: reason_parts.append("MA死叉")
            
            if self.enable_adx: reason_parts.append(f"ADX強勢({self.cached_adx:.1f})")
            if self.enable_vol_filter: reason_parts.append(f"爆量({self.vol_multiplier}x)")
            
            signal = SignalEvent(
                type=EventType.SIGNAL, symbol=bar.symbol, signal_type=SignalType.SHORT, strength=1.0,
                reason=" | ".join(reason_parts)
            )
            self.entry_price = current_price
            self.highest_price = current_price
            self.lowest_price = current_price

        return signal

    def _check_stop_loss(self, current_price: float, symbol: str) -> SignalEvent:
        if self.position == 0: return None
        pnl = (current_price - self.entry_price) if self.position > 0 else (self.entry_price - current_price)
        if pnl <= -self.stop_loss:
            return SignalEvent(
                type=EventType.SIGNAL, symbol=symbol, signal_type=SignalType.FLATTEN, 
                reason=f"STOP LOSS triggered (-{self.stop_loss:.0f} pts)"
            )
        return None

    def load_history_bars(self, bars_list: list):
        for bar in bars_list:
            if isinstance(bar, dict):
                # 確保載入完整的 OHLCV
                self.raw_bars.append({
                    'datetime': bar.get('datetime'),
                    'open': bar.get('open', bar.get('close')),
                    'high': bar.get('high', bar.get('close')),
                    'low': bar.get('low', bar.get('close')),
                    'close': bar.get('close'),
                    'volume': bar.get('volume', 0)
                })
            else:
                self.raw_bars.append({
                    'datetime': bar.timestamp, 'open': bar.open, 'high': bar.high, 
                    'low': bar.low, 'close': bar.close, 'volume': bar.volume
                })

    def get_ui_dict(self):
        """提供給 Dashboard UI 顯示的專屬指標"""
        ma_status = "⏳ 等待資料"
        if self.cached_ma_fast and self.cached_ma_slow:
            diff = self.cached_ma_fast - self.cached_ma_slow
            if diff > self.filter_point: ma_status = f"[green]多頭 (+{diff:.1f})[/green]"
            elif diff < -self.filter_point: ma_status = f"[red]空頭 ({diff:.1f})[/red]"
            else: ma_status = f"[yellow]盤整 ({diff:.1f})[/yellow]"
            
        return {
            "💰 目前報價": f"{getattr(self, 'latest_price', '等待開盤...')}",
            "快線 (MA)": f"{self.cached_ma_fast:.1f}" if self.cached_ma_fast else "N/A",
            "慢線 (MA)": f"{self.cached_ma_slow:.1f}" if self.cached_ma_slow else "N/A",
            "均線狀態": ma_status,
            "波段鎖定": "🔒 已鎖定" if getattr(self, 'last_traded_wave', 0) != 0 else "🔓 未鎖定",
            "ADX 強度": f"{self.cached_adx:.1f}" if self.cached_adx else "N/A",
            "當前爆量": f"{self.cached_current_vol}" if self.cached_current_vol else "N/A"
        }