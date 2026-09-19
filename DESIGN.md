# Wave-Rider — Design Document

> Single source of truth for the project. Reconciles the strategy notes (`Doc001.txt`)
> and the build spec (`Doc002.txt`) into one agreed plan. Those two files are kept
> as background/archive only — where they disagree, **this document wins**.

---

## 1. Goal (v1)

Build a **detector + notifier**, not a trading system.

For years I've watched SPY make sharp, fast directional moves in the final ~15 minutes
of the session and only recently learned these are driven by **Market-on-Close (MOC)
order imbalances** from institutions. The v1 goal is simple:

> **Get a notification on my phone when that late-day imbalance move is happening,
> so I don't have to watch the chart every single day.**

No trade execution in v1. Manual trading (or later automation) only happens *after*
the detector proves it reliably catches the events I already recognize by eye.

### Non-goals (v1)
- No placing, routing, or automating trades.
- No paid data feeds.
- No options contract execution logic.
- No backtesting framework beyond simple metric logging.

---

## 2. Core decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Purpose | Alert-only detector | Prove the concept before risking capital |
| Instrument | SPY, 1-minute bars | The thing I actually watch |
| Data feed | Alpaca free tier (IEX) | Free; upgrade to SIP only after proof of concept |
| Notifications | Telegram bot → phone | Already installed; free; reliable delivery |
| Hosting | Cloud droplet + `systemd` | Always-on; survives reboots while I travel |
| Detector | Price-velocity primary + range/persistence + volume secondary, combined into a composite score | IEX price data is reliable; IEX **volume** is thin (~2–3% of consolidated tape), so price leads |
| First mode | Phase 0 "Observation" (log, don't alert) | Calibrate the trigger against real events before turning on alerts |
| Automation | `AUTOMATE_TRADES = False`, stubbed | Reserve a clean hook for later without building it now |

---

## 3. Reconciling the two source docs

The two source documents disagreed on several concrete parameters. Resolutions:

| Topic | Doc001 | Doc002 | Resolution (v1) |
|---|---|---|---|
| Active window | 3:45–4:00 PM | 15:45–15:54 | **3:45–4:00 PM ET** for observation (capture the whole tail incl. the close) |
| "Final 15 min" label | 3:45–4:00 (correct) | called 3:45–3:55 "15 min" (is 10 min) | Use correct 3:45–4:00 window |
| Volume threshold | ≥300% above avg (~4×) | 4.5× rolling avg | **Not a hard gate in v1** — volume is one *weighted input* to the score; calibrate empirically |
| Signal features | Marubozu, VWAP break >1.5×ATR | volume 4.5× + velocity ≥$0.35/min | **Hybrid composite score** (see §5) |
| Exit logic | wick/climax/2-min stall | 3:54:30 hard cutoff | **Deferred** — no positions in v1 |
| Options selection | single SPY contract | 0DTE ATM cache at 3:30 | **Deferred** to Phase 2 |
| Data premise | "read the MOC feed" | infer footprints (can't afford feed) | **Infer footprints** — free tier can't see the real auction feed |
| Capital/risk | $2k→$50k, 15% sizing | n/a | **Deferred** — not relevant until trading |

---

## 4. Architecture

Adapted from `Doc002.txt`'s module layout, trimmed to alert-only.

```
wave-rider/
├── DESIGN.md                 # this file
├── .gitignore
├── requirements.txt
├── main.py                   # conductor: market-hours loop, wiring
├── config/
│   └── settings.py           # all tunable parameters (mirrors §5 thresholds)
├── src/
│   ├── data_feed.py          # pull SPY 1-min bars from Alpaca (IEX), retry/backoff
│   ├── imbalance_engine.py   # rolling metrics + composite score + trigger decision
│   ├── observer.py           # Phase 0: append per-minute metrics to disk
│   ├── alert_dispatcher.py   # Telegram send (with retry); alert cooldown
│   └── execution_manager.py  # stub; AUTOMATE_TRADES=False; placeholder for later
├── data/
│   └── observations/         # daily metric logs (gitignored)
└── deploy/
    └── wave-rider.service    # systemd unit (Restart=always)
```

### Secrets & config
- Secrets (Alpaca API key/secret, Telegram bot token, chat ID) live in a local
  `.env` file on the droplet, loaded at runtime. **Never committed.**
- `config/settings.py` holds only non-secret tunables (thresholds, window times).

---

## 5. Detector logic

Runs on each closed 1-minute SPY bar during the active window (3:45–4:00 PM ET).

**Metrics per bar:**
- **Velocity** — `abs(close - open)` for the minute, normalized against the day's
  typical 1-min move (e.g., a rolling median/std of earlier bars). "Is this minute
  much bigger than a normal minute today?"
- **Range expansion** — bar `high - low` vs the day's average bar range.
- **Persistence** — count of consecutive same-direction bars (a *drive*, not a blip).
- **Volume surge** — bar volume vs rolling average. Secondary weight (IEX volume is thin).

**Composite score** — weighted sum of the normalized metrics into a single number.
A single tunable `TRIGGER_SCORE` decides when to fire, instead of brittle hard cutoffs.
Direction (CALL-side / PUT-side) is taken from the sign of the move.

**Trigger discipline:**
- **Cooldown** — after firing, suppress repeat alerts for N minutes so one event = one alert.
- **One-shot per window** option — optionally cap to a single alert per session.

Starting weights/thresholds are **first guesses** to be tuned from Phase 0 data.
Provisional defaults (subject to calibration):

| Parameter | Provisional value |
|---|---|
| `ACTIVE_WINDOW` | 15:45:00–16:00:00 ET |
| `VELOCITY_WEIGHT` | 0.5 |
| `RANGE_WEIGHT` | 0.2 |
| `PERSISTENCE_WEIGHT` | 0.2 |
| `VOLUME_WEIGHT` | 0.1 |
| `TRIGGER_SCORE` | TBD after Phase 0 |
| `ALERT_COOLDOWN_MIN` | 5 |

---

## 6. Phase roadmap

1. **Phase 0 — Observe.** Log per-minute metrics for the window every trading day to
   `data/observations/`. No alerts. After ~2 weeks, compare the log to my memory of the
   real events and set `TRIGGER_SCORE`. Proves whether free IEX data even surfaces the
   footprints.
2. **Phase 1 — Alert MVP.** Fire a Telegram notification when the score crosses the
   trigger. Alert-only. This is the actual product goal.
3. **Phase 2 — Enrich.** Alert also names the ATM 0DTE contract + direction (still info only).
4. **Phase 3 — Better data.** Add a SIP feed (Alpaca Pro / Polygon) for trustworthy
   volume once the PoC holds.
5. **Phase 4 — Automate.** Opt-in execution behind `AUTOMATE_TRADES`, with a hard
   pre-close exit safeguard. Only if earlier phases prove out.

---

## 7. Resilience (I travel for work)

- **`systemd` service** with `Restart=always` — survives crashes and droplet reboots.
- **Persistent logs** — observation metrics written to disk as they're produced, so a
  mid-week restart resumes with history intact instead of losing the week.
- **Robust networking** — try/except with retry/backoff around data pulls and Telegram
  sends so a transient network drop doesn't kill the process.
- **Heartbeat (optional)** — a daily "I'm alive" Telegram ping so I know it's still running.

---

## 8. Setup notes (for later, when scaffolding)

- **Telegram:** create a bot via BotFather to get a **bot token**; obtain my **chat ID**;
  put both in `.env` on the droplet.
- **Alpaca:** generate free-tier API key/secret; store in `.env`.
- **Droplet:** install Python, clone repo, `pip install -r requirements.txt`, drop the
  `.env`, enable the `systemd` unit.

---

## 9. Open items to revisit
- Final `TRIGGER_SCORE` and metric weights (set from Phase 0 data).
- Whether to cap to one alert per session or allow multiple.
- Timezone/DST handling for the ET window on a UTC droplet.
- Half-day / holiday early-close handling (1:00 PM close).
