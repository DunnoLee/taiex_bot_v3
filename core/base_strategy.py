from abc import ABC, abstractmethod
from core.event import OrderEvent, FillEvent, SignalEvent
import json
import os

class BaseStrategy(ABC):
    """
    策略基底類別 (通用卡帶插槽)
    所有策略都必須繼承這個類別，並實作 on_bar 方法。
    """
    def __init__(self, name="Unknown Strategy"):
        self.name = name
        self.position = 0         # 策略建議的倉位
        self.entry_price = 0.0    # 進場價
        self.raw_bars = []        # K棒紀錄

    def get_state_file_path(self):
        """📂 動態生成專屬的記憶卡檔名，避免策略打架"""
        os.makedirs("data/states", exist_ok=True)
        # 利用 __class__.__name__ 自動抓取策略名稱 (例如: MaAdxStrategy_state.json)
        return f"data/states/{self.__class__.__name__}_state.json"

    def save_state(self):
        """💾 將當前狀態寫入該策略專屬的記憶卡"""
        state = {
            "position": getattr(self, 'position', 0),
            "entry_price": getattr(self, 'entry_price', 0.0),
            "highest_price": getattr(self, 'highest_price', 0.0),
            "lowest_price": getattr(self, 'lowest_price', float('inf')),
            "last_traded_wave": getattr(self, 'last_traded_wave', 0)
        }
        file_path = self.get_state_file_path()
        try:
            with open(file_path, "w") as f:
                json.dump(state, f)
        except Exception as e:
            print(f"⚠️ [記憶卡寫入失敗] {e}")

    def load_state(self):
        """💾 從專屬記憶卡還原最高/最低水位"""
        file_path = self.get_state_file_path()
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    state = json.load(f)
                    
                    # ⚠️ 關鍵防呆：只有當「記憶卡裡的部位」跟「真實部位」一致時，才還原水位！
                    if self.position != 0 and self.position == state.get("position", 0):
                        self.highest_price = state.get("highest_price", self.entry_price)
                        self.lowest_price = state.get("lowest_price", self.entry_price)
                        self.last_traded_wave = state.get("last_traded_wave", 0)
                        print(f"💾 [{self.__class__.__name__} 記憶卡還原成功] 恢復最高水位: {self.highest_price:.0f}")
            except Exception as e:
                print(f"⚠️ [{self.__class__.__name__} 記憶卡讀取失敗] {e}")
                
    @abstractmethod
    def on_bar(self, bar) -> 'SignalEvent':
        """
        核心邏輯：每根 K 棒進來時，策略要決定做什麼
        (子類別必須實作這個方法)
        """
        pass

    def load_history_bars(self, bars):
        """通用功能：載入歷史 K 棒"""
        self.raw_bars = bars
        print(f"[{self.name}] 已載入 {len(bars)} 根歷史數據")

    def set_position(self, pos):
        """通用功能：更新倉位"""
        self.position = pos