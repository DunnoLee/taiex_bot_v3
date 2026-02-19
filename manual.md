🎮 TaiEx Bot V3 終極操作手冊
1. 總開關與面板設定 (The Control Panel)
機器的所有全域設定都在你的 .env 檔案和 config/settings.py 裡。這是你開機前必看的儀表板。

實戰/演習切換開關 (The Safety Switch)：

settings.py 裡的 DRY_RUN=True：演習模式。機器人會接收真實行情、計算真實訊號，但下單那一刻會「攔截」並改為印出 Log。新手上路或換新策略時必開。

settings.py 裡的 DRY_RUN=False：實戰模式。真槍實彈，直接把單子打進永豐期貨交易所。

標的切換旋鈕 (Target Contract)：

.env 裡的 TARGET_CONTRACT=TMF202603。每個月第三個禮拜三結算後，你要手動進來把這裡改成下個月（例如 TMF202604），機器人就會自動翻譯成新的合約代碼。

2. 每日保養與開機SOP (Daily Routine)
機器人雖然是自動的，但還是需要指揮官的日常維護，確保它的「大腦」資料是最新的。

🌙 盤後保養 (下午 14:00 之後 或 睡前)

收盤與結算： 機器人通常會在盤中一直跑，確認今天收盤後，你可以到 Telegram 下達 /kill 關機，或者直接在終端機按 Ctrl+C。

更新歷史資料 (最重要的一步)： 執行你的下載器：python universal_downloader.py
目的： 把今天的 K 棒確實寫入 data/history/TMF_History.csv。這樣明天開機時，API 就不需要從上個禮拜開始補資料，幾秒鐘就能完成「雙軌對接」。

☀️ 盤前點火 (早上 08:30 ~ 08:45)

確認合約： 檢查 .env 的 TARGET_CONTRACT 是否正確。

確認開關： 確認 DRY_RUN 是 True 還是 False。

啟動主機： 執行 python main_live.py。

監控儀表板： 打開你的 Telegram，你會看到：

收到啟動報告。

收到「雙軌對接完成」的通知（確認補了幾根 K 棒，沒跳出紅色警告）。

倉位校準： 在 Telegram 輸入 /sync，讓機器人的大腦與永豐 API 帳戶的真實倉位對齊。

放手讓它跑： 接下來就交給策略處理了！

3. 遊戲卡帶抽換教學 (How to Swap Strategies)
目前機器的卡槽裡插的是 MAStrategy (雙均線策略)。如果你想微調參數，或換別的策略，都在 main_live.py 裡操作。

打開 main_live.py，找到這段程式碼：

Python
    # -----------------------------------------------------
    # 4. 初始化 策略 (Game Cartridge)
    # -----------------------------------------------------
    my_strategy = MAStrategy(
        fast_window=30,     # 短均線參數 (可微調)
        slow_window=240,    # 長均線參數 (可微調)
        stop_loss=300.0,    # 硬停損點數 (可微調)
        filter_point=5.0    # 交叉濾網點數 (可微調)
    )
微調參數 (Tuning)： 你可以直接在這裡修改數字。例如把 fast_window 改成 15，下次開機它就會用 15MA 去算。

換卡帶 (Swapping)： 如果我們未來寫了一個 RsiStrategy.py，你只要在這裡改成：

Python
from modules.rsi_strategy import RsiStrategy
my_strategy = RsiStrategy(rsi_period=14, overbought=70, oversold=30)
Engine 會完美接納它，完全不需要改動其他底層程式碼！

4. 指揮官遙控器 (Telegram Commands Recap)
不要忘了你在 Telegram 上擁有的最高權限：

/status：檢查目前模式 (Live/Dry)、機器人以為的倉位、以及券商真實的倉位。

/balance：看目前賺賠。會分別列出「策略算出來的」跟「券商戶頭裡的」。

/sync：神級指令。如果你發現機器人倉位跟券商不同步（例如你手癢用永豐 APP 自己下了一口單），立刻點這個，機器人會馬上認列真實倉位。

/buy 1 / /sell 1：手動干預。會自動啟動「智慧反手」（如果你有空單卻喊 Buy，它會先幫你平倉）。

/flat：一鍵清倉，緊急逃生用。

/kill：拔插頭。