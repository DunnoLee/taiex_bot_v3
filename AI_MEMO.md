# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.12 / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures)
> **Architecture:** Event-Driven (Feeder -> Aggregator -> Strategy -> Execution)

## 1. 核心哲學 (Core Philosophy)
1.  **Strict Modularity:** Strategy is pure logic; Execution is separate.
2.  **Simulation Parity:** Live & Backtest share the exact same logic code.
3.  **Data-Driven:** All parameters are verified by optimization (70k bars backtest), not guessing.
4.  **Interactive Control:** The bot must be controllable via Telegram (Bi-directional).

## 2. 系統架構 (System Architecture)
* **Feeder:**
    * `ShioajiFeeder`: Live Market Data (TMF).
    * `CsvHistoryFeeder`: For Backtesting & Simulation.
* **Translator:** `BarAggregator` (Tick -> 1m Bar).
* **Strategy:** `MAStrategy` (V3.4)
    * **Logic:** Dual MA Cross (Fast/Slow) on **Resampled K-Bars**.
    * **Safety:** Dynamic Stop Loss mechanism.
    * **Warm-up:** Supports loading historical data (CSV) for instant MA calculation.
* **Notification:** `TelegramCommander` (V3.2 - Interactive)
    * Supports `/start`, `/stop` (Pause Trading), `/status`, `/balance`, `/kill` (Shutdown).
    * Includes "Zombie Message" protection (ignores old commands).

## 3. 獲利模型 (The Holy Grail Parameters)
* **Optimization Date:** 2026-02-16
* **Data Source:** TMF History (70,000 bars)
* **Best Parameters (Champion Set):**
    * **Timeframe:** 5 min Resample.
    * **Fast Window:** 30 (approx. 2.5 hours).
    * **Slow Window:** 240 (approx. 20 hours).
    * **Filter Threshold:** 5.0 pts (Avoid whipsaw).
    * **Stop Loss:** **300 pts** (Optimal point).
* **Performance:** Net Profit **+$69,520 TWD** (Win Rate ~36%, High Risk/Reward Ratio).

## 4. 開發日誌 (Development Log)
- [x] **Phase 1-3:** Skeleton, Strategy Porting, Mock Replay.
- [x] **Phase 4:** Live Data Connection (Shioaji TMF).
- [x] **Phase 5:** Optimization (Found optimal params: 30/240/300).
- [x] **Phase 6:** **Interactive Commander** (Completed V3.2).
    - [x] Implemented `/stop` (Pause) & `/start` (Resume) logic.
    - [x] Implemented `main_simulation.py` for risk-free wargaming.
- [ ] **Phase 7:** **Production Readiness**
    - [ ] Implement Historical Data Pre-loading (Warm-up).
    - [ ] Real Order Execution (Shioaji Order API).

## 5. 當前狀態 (Current Context)
* **Status:** System is profitable in backtests and fully interactive in simulation.
* **Current Task:** Implementing "History Pre-loading" to ensure the bot has enough data (MA240) immediately upon startup.
* **Data Format:** Confirmed using Shioaji export format (Time/Open/High/Low/Close/Volume).