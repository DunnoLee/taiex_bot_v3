#專案起始環境安裝
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

pip install rich

在 VS Code 中，按下鍵盤快速鍵 Cmd + Shift + P (叫出命令面板)。
輸入 Python: Select Interpreter 並點選它。
在選單中，你應該會看到一個標示為 ('venv': venv) 或路徑指向 ./.venv/bin/python 的選項。

caffeinate -i

request:
***用main_simulation可以在市場沒開時也能虛擬完整流程, 最後只是接通真實tick + place_order是真實對永豐api下單:
它的邏輯跟 main_live.py 99% 一樣，唯一的差別是：
Feeder 換掉： 用 CsvHistoryFeeder 取代 ShioajiFeeder（假裝現在有行情）。
Executor 換掉： 用 MockExecutor 取代未來的 RealExecutor（假裝下單成交）。
Telegram 留著： 這是真的！你可以用手機跟這個「假行情」互動。

***telegram /buy, /sell, 手動下單

***sync倉位

***專案邏輯重點:
此專案目的是用做真實上線自動執行交易, 
所以main_live是主線, 所有收集資料, 策略判斷, 下單行為, 損益計算, 機器人訊息發布及接收執行,
都以實際要在main_live線中執行為主.
main_simulation是支線,是為了要盡可能測到主線100%程式而生, mock只是要模擬api端, 讓api沒tick資訊時,
或在可以下真正api下單命令前讓其餘程式碼能盡量跑通被測試到, 
最後只是最後把真實資料來源tick接通, 把下單命令換成api的真實命令,
所以兩條線跑過不同的程式碼越少越好.