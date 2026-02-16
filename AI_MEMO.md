# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.12 / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures)
> **Architecture:** Event-Driven (Feeder -> Aggregator -> Strategy -> Execution)

## 1. 核心哲學 (Core Philosophy)
1.  **Strict Modularity:** Strategy is pure logic.
2.  **Simulation Parity:** Live & Backtest share the exact same logic.
3.  **Data-Driven:** All parameters must be verified by backtesting, not guessing.

## 2. 系統架構 (System Architecture)
* **Feeder:** `ShioajiFeeder` (Live) / `CsvHistoryFeeder` (Mock)
* **Translator:** `BarAggregator` (Tick -> 1m Bar)
* **Strategy:** `MAStrategy` (V3.4)
    * **Logic:** Dual MA Cross (Fast/Slow) on **Resampled K-Bars**.
    * **Safety:** Hard Stop Loss mechanism.
* **Notification:** `TelegramCommander` (Bidirectional).

## 3. 獲利模型 (The Holy Grail Parameters)
* **Date Verified:** 2026-02-16
* **Data Source:** TMF History (70k bars)
* **Best Settings:**
    * **Timeframe:** 5 min Resample (Fast=30, Slow=240) -> 相當於 2.5hr vs 20hr 均線。
    * **Filter:** Threshold 5.0 pts.
    * **Risk Control:** Stop Loss **300 pts**.
* **Performance:** Net Profit **+$69,520 TWD** (Win Rate ~36%, High Risk/Reward Ratio).

## 4. 開發日誌 (Development Log)
- [x] **Phase 1-3:** Skeleton, Strategy Porting, Mock Replay.
- [x] **Phase 4:** Live Data Connection (Shioaji TMFB6).
- [x] **Phase 5:** Optimization (Found optimal params: 30/240/300).
- [ ] **Phase 6:** **Interactive Commander** (Bidirectional Telegram Control).
- [ ] **Phase 7:** Real Execution (Shioaji Order Placement).

## 5. 當前狀態 (Current Context)
* **Status:** Optimization Complete. System is profitable in backtests.
* **Next Priority:** Implement Interactive Commander (`/status`, `/stop`) to allow remote monitoring and control.