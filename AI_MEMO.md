# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.12 / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures)
> **Architecture:** Engine-Centric (Feeder -> Engine -> Strategy -> Execution)

## 0. 開發協議 (Development Protocol) - STRICT
* **Logic Persistence:** DO NOT silently refactor user-defined logic. Explain "WHY" first.
* **Engine-First Architecture:** Business logic (Signal handling, Telegram commands, Order flow) MUST reside in `core/engine.py`.
    * `main_live.py` and `main_simulation.py` must be dumb launchers.
    * **Anti-Divergence:** Never duplicate logic between Live and Sim scripts.
* **Data Consistency:** Use `core/loader.py` for all historical data reading to ensure consistent parsing across modes.

## 1. 核心哲學 (Core Philosophy)
1.  **Strict Modularity:** Strategy is pure logic; Execution is separate.
2.  **Simulation Parity:** Live & Backtest share the exact same `BotEngine` class.
3.  **Data-Driven:** Parameters verified by 70k bars backtest (MA 30/240).
4.  **Interactive Control:** The bot must be controllable via Telegram (Bi-directional).

## 2. 系統架構 (System Architecture)
* **The Brain (Central):** `core/engine.py` (`BotEngine`)
    * Coordinates Feeder, Strategy, Executor, and Telegram.
    * Handles all user commands (`/buy`, `/sell`, `/sync`, `/stop`).
* **Core Modules:**
    * `core/loader.py`: Unified History Loader (CSV -> Bars).
    * `core/aggregator.py`: Tick -> Bar converter.
* **Feeder (Pluggable):**
    * `ShioajiFeeder` (Live) / `CsvHistoryFeeder` (Sim).
* **Strategy:** `MAStrategy` (V3.5)
    * Logic: Dual MA Cross (Fast/Slow) on Resampled Bars.
    * Buffer: 5000 bars.
* **Notification:** `TelegramCommander` (V3.3 - Trader Edition)
    * Supports Manual Trade & Position Sync.

## 3. 獲利模型 (The Holy Grail Parameters)
* **Optimization Date:** 2026-02-16
* **Best Parameters:**
    * **Timeframe:** 5 min Resample.
    * **MA:** Fast=30, Slow=240.
    * **Filter:** 5.0 pts.
    * **Stop Loss:** 300 pts.
* **Performance:** Net Profit **+$69,520 TWD** (Win Rate ~36%).

## 4. 開發日誌 (Development Log)
- [x] **Phase 1-5:** Skeleton, Optimization, Basic Telegram.
- [x] **Phase 6:** **Interactive Commander** (V3.3).
    - [x] Added `/buy`, `/sell`, `/sync` commands.
- [x] **Phase 7:** **Engine Refactoring (Crucial)**
    - [x] Consolidated logic into `core/engine.py`.
    - [x] Reduced `main_live` and `main_simulation` to bare-bones launchers.
    - [x] Implemented unified `core/loader.py`.
- [ ] **Phase 8:** **Dual-Track Data Feed** (Next Step)
    - [ ] Implement API Backfill to bridge CSV (Cold) and WebSocket (Hot).

## 5. 待辦事項 (User Wishlist)
* **Dual-Track Data:** Seamlessly merge CSV history + API recent bars + Live Ticks.
* **Real Execution:** Connect `RealExecutor` to Shioaji Order API.