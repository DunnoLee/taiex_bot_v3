#專案起始環境安裝
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

在 VS Code 中，按下鍵盤快速鍵 Cmd + Shift + P (叫出命令面板)。
輸入 Python: Select Interpreter 並點選它。
在選單中，你應該會看到一個標示為 ('venv': venv) 或路徑指向 ./.venv/bin/python 的選項。

caffeinate -i