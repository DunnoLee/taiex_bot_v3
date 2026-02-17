# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.12 / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures) - Point Value: 10 TWD, Fee: 22 TWD.
> **Architecture:** Engine-Centric (Feeder -> Engine -> Strategy -> Executor)

## 0. 開發協議 (Development Protocol) - STRICT
* **Logic Persistence:** DO NOT silently refactor user-defined logic. Explain "WHY" first.
* **Engine-First Architecture:** Business logic (Signal handling, Telegram commands, Order flow) MUST reside in `core/engine.py`.
    * `main_live.py`, `main_simulation.py`, `main_backtest.py` are dumb launchers.
    * **Anti-Divergence:** Never duplicate logic between Live and Sim scripts.
* **Data Consistency:** Use `core/loader.py` for all historical data reading.

## 1. 核心哲學 (Core Philosophy)
1.  **Strict Modularity:** Strategy is pure logic; Execution is separate.
2.  **Simulation Parity:** Live & Backtest share the exact same `BotEngine` class.
3.  **Data-Driven:** Parameters verified by 70k bars backtest (MA 30/240).
4.  **Interactive Control:** The bot must be controllable via Telegram (Bi-directional).

## 2. 系統架構 (System Architecture)
* **The Brain:** `core/engine.py` (`BotEngine`)
    * Central coordinator. Handles Telegram commands (`/buy`, `/sell`, `/flat`, `/sync`).
    * Implements "Smart Order Logic" (Auto-reverse, Flatten detection).
* **Memory & Logs:** `core/recorder.py` (`TradeRecorder`)
    * Records every trade (Auto & Manual) to `data/YYYY-MM-DD/trade_log.csv`.
    * Compatible with V3 Analysis Tools.
* **Execution:** `MockExecutor` (V3.5)
    * Updated for TMF specs (Point: 10, Fee: 22).
    * Supports manual pyramiding (adding positions) and PnL calculation.
    * *Planned: Refactor into BaseExecutor (Shadow Ledger) + RealExecutor.*
* **Tools:**
    * `tools/stat_analyzer.py`: Performance report generator.
    * `tools/visualizer.py`: Chart plotter with Buy/Sell/StopLoss markers.

## 3. 獲利模型 (The Holy Grail Parameters)
* **Optimization Date:** 2026-02-16
* **Best Parameters:**
    * **Timeframe:** 5 min Resample.
    * **MA:** Fast=30, Slow=240.
    * **Filter:** 5.0 pts.
    * **Stop Loss:** 300 pts.
* **Performance:** Net Profit **+$69,520 TWD** (Win Rate ~36%).

## 4. 開發日誌 (Development Log)
- [x] **Phase 1-5:** Skeleton, Optimization.
- [x] **Phase 6:** **Interactive Commander** (V3.3).
- [x] **Phase 7:** **Engine Refactoring & Tools Revival** (Current)
    - [x] **Engine:** Consolidated logic. Added `manual_trade` with PnL tracking and Entry Price fix.
    - [x] **Manual Trading:** Implemented `/buy`, `/sell`, `/flat` (Flatten) with Smart Logic.
    - [x] **Recorder:** Created `core/recorder.py` to save CSV logs.
    - [x] **Tools:** Updated `visualizer.py` and `stat_analyzer.py` to support V3 log format.
    - [x] **Launchers:** Added `main_backtest.py` for silent high-speed testing.
- [ ] **Phase 8:** **Executor Architecture Refactoring** (Next Priority)
    - [ ] Create `core/base_executor.py` (Shadow Ledger) to unify logic between Mock and Real.
    - [ ] Implement `RealExecutor` for Shioaji API.
- [ ] **Phase 9:** **Dual-Track Data Feed**
    - [ ] Implement API Backfill (Hot Data).

## 5. 待辦事項 (User Wishlist)
* **Executor Refactoring:** Split logic into Base/Mock/Real to ensure consistency.
* **Dual-Track Data:** Seamlessly merge CSV history + API recent bars + Live Ticks.
* **Real Execution:** Connect `RealExecutor` to Shioaji Order API.