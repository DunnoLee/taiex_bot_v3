import sys
import time
import threading
from collections import deque
from datetime import datetime
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console

class LogInterceptor:
    """魔法攔截器：把原本要 print 到螢幕的字抓下來，放進儀表板下半部，並存入檔案"""
    def __init__(self, log_file="data/backtest_results/live_process.log"):
        self.logs = deque(maxlen=15) # 下半部只顯示最新的 15 行 Log
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr  # 🚀 新增：記住原本的 stderr
        self.log_file = log_file

    def write(self, text):
        if text.strip(): # 忽略空白換行
            time_str = datetime.now().strftime("%H:%M:%S")
            log_line = f"[{time_str}] {text.strip()}"
            self.logs.append(log_line)
            # 同時寫入實體檔案，永久保存
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
                
    def flush(self):
        pass

class DashboardUI:
    def __init__(self, bot):
        self.bot = bot
        self.interceptor = LogInterceptor()

    def generate_layout(self) -> Layout:
        """每次畫面更新時，重新組裝儀表板"""
        layout = Layout()
        layout.split_column(
            Layout(name="upper", ratio=1), # 上半部：儀表板
            Layout(name="lower", ratio=1)  # 下半部：日誌區
        )

        # === 建立上半部：數據表格 ===
        st = self.bot.strategy
        ex = getattr(self.bot, 'executor', None) # 👈 找到掌管資金的執行官
        
        # 優先讀取 Executor 的真實部位，如果拿不到，才去讀策略的影子部位
        pos = getattr(ex, 'current_position', getattr(st, 'position', 0))

        pos_str = "[green]🟩 做多[/green]" if pos > 0 else "[red]🟥 做空[/red]" if pos < 0 else "[white]⬜ 空手[/white]"
        
        table = Table(show_header=False, expand=True, box=None)
        table.add_column("Key1", style="cyan", width=15)
        table.add_column("Val1", width=25)
        table.add_column("Key2", style="cyan", width=15)
        table.add_column("Val2", width=25)

        table.add_row("🤖 策略名稱:", f"{st.name}", "🕒 系統時間:", f"{datetime.now().strftime('%H:%M:%S')}")
        table.add_row("💼 目前部位:", f"{pos_str} (Qty: {pos})", "⚙️ 運行狀態:", "🟢 監聽中")
        
        # 🚀 魔法在這裡：向策略索取專屬的儀表板數據！
        # 如果這個策略有寫 get_ui_dict()，就抓它的資料；如果沒有，就顯示預設訊息
        metrics = getattr(st, 'get_ui_dict', lambda: {"提示": "本策略尚未提供監控指標"})()
        
        # 把策略給我們的字典，動態填入兩欄式的表格裡
        items = list(metrics.items())
        for i in range(0, len(items), 2):
            k1, v1 = items[i]
            k2, v2 = items[i+1] if i+1 < len(items) else ("", "")
            table.add_row(f"📊 {k1}:", str(v1), f"📊 {k2}:" if k2 else "", str(v2))

        upper_panel = Panel(table, title="[bold yellow]🚀 TaiEx Bot V3 戰術儀表板[/bold yellow]", border_style="blue")
        layout["upper"].update(upper_panel)

        # === 建立下半部：滾動日誌 ===
        log_text = Text("\n".join(self.interceptor.logs))
        lower_panel = Panel(log_text, title="[bold white]📝 系統執行日誌 (Live)[/bold white]", border_style="green")
        layout["lower"].update(lower_panel)

        return layout

    def start_ui(self, bot_thread=None):
        """啟動儀表板 (支援與背景引擎連動)"""
        # 1. 啟動攔截器
        sys.stdout = self.interceptor
        sys.stderr = self.interceptor # 🚀 新增：把錯誤管線也導向儀表板

        # 🚀 新增：強迫 Telegram 等第三方套件的 logging 模組也寫進我們的攔截器
        import logging
        logging.basicConfig(stream=self.interceptor, level=logging.INFO, force=True)

        # 🚀 關鍵修復：告訴 Rich 把畫面畫在「原本的真實螢幕」上，不准畫進攔截器裡！
        from rich.console import Console
        custom_console = Console(file=self.interceptor.original_stdout)
        
        # 2. 啟動 Rich Live 畫面
        with Live(
            self.generate_layout(), 
            console=custom_console, 
            refresh_per_second=2, 
            screen=True,
            redirect_stdout=False,   # 👈 補上這行
            redirect_stderr=False    # 👈 補上這行
        ) as live:
            try:
                while True:
                    # 🚀 模擬回測支援：如果背景引擎跑完死掉了，儀表板就跟著自動下班
                    if bot_thread and not bot_thread.is_alive():
                        break 
                        
                    live.update(self.generate_layout())
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
            finally:
                # 3. 程式結束時，把 print 還給系統
                sys.stdout = self.interceptor.original_stdout
                sys.stderr = self.interceptor.original_stderr # 🚀 新增：歸還 stderr