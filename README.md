# Desktop PRESS-B Matching Task

A desktop reimplementation of the PRESS-B concurrent variable-interval schedule task from [Klapes et al. (2020, JEAB)](literature/Klapes%20et%20al.%20(2020).pdf) and [Klapes (2021, JEAB)](literature/J%20Exper%20Analysis%20Behavior%20-%202021%20-%20Klapes%20-%20Methodological%20improvements%20to%20a%20Procedure%20for%20Rapidly%20Establishing.pdf), extended with a mouse-click modality for studying the matching law in humans.

## Overview

Participants respond on two concurrent random-interval (RI) schedules across a series of experimental conditions. The task measures how response allocation tracks reinforcement rate ratios — a test of the **generalized matching law** (GML).

The session sequence is:

1. **Consent** — participant reads and acknowledges consent
2. **Instructions** — task explanation
3. **Leaderboard** (optional) — point total display for motivation
4. **Acquisition** — equal RI schedules; participant learns the task
5. **Experimental** — 11 schedule pairs spanning RI 1:7 through RI 7:1
6. **Extinction** — reinforcers unavailable
7. **Debrief**

Blackouts (blank screen) separate phases. A **changeover delay (COD)** prevents immediate switching from being reinforced. A **forced-choice extension** extends a schedule if one alternative has received zero reinforcers, ensuring valid matching data.

After the session, GML parameters (sensitivity *a*, log bias *b*, R²) are fit via OLS and written to a text file alongside the raw data.

## Requirements

- Python 3.10+
- pygame >= 2.6.1
- numpy >= 1.24
- scipy >= 1.10

```bash
pip install -r requirements.txt
```

## Running

```bash
# Default settings
python main.py

# Set participant ID
python main.py --participant P01

# Open config editor before starting
python main.py --configure

# Load a saved config file
python main.py --config config.json

# Change output directory (default: ./data)
python main.py --output ./data/study1
```

Press **Escape** at any time to quit.

## Input Modalities

Set `modality` in the config or config editor.

### Keyboard (default)
| Key | Action |
|-----|--------|
| Space | Respond on active alternative |
| Ctrl (left or right) | Switch alternative (changeover) |

### Mouse
Click the left panel (Alt 1) or right panel (Alt 2). Clicking the inactive panel performs a changeover and immediately counts as a response on the new alternative.

## Default Schedule Parameters

| Parameter | Default |
|-----------|---------|
| COD | 500 ms |
| Acquisition RI | 0.7 s (both alts) |
| Acquisition duration | 60 s |
| Blackout between schedules | 5000 ms |
| Extinction duration | 30 s |
| Forced-choice extension | 30 s |

Experimental schedules (RI alt1 : RI alt2, each 200 s):

`7:1 · 5:1 · 3:1 · 2:1 · 1.5:1 · 1:1 · 1:1.5 · 1:2 · 1:3 · 1:5 · 1:7`

All parameters are researcher-configurable via JSON or the built-in config editor (`--configure`).

## Output Files

Files are written to `./data/` (or `--output` path), prefixed by session ID:

| File | Contents |
|------|----------|
| `<session>_events.csv` | Every response, reinforcer, changeover, and schedule start/end with ms-precision timestamps |
| `<session>_summaries.csv` | Per-schedule totals: B1, B2, R1, R2, changeovers, duration |
| `<session>_config.json` | Full config snapshot for that session |
| `<session>_gml.txt` | GML fit: sensitivity (*a*), log bias (log *b*), R² |

Timestamps use `time.perf_counter()` for sub-millisecond resolution.

## Project Structure

```
main.py              Entry point, event loop, input handling
src/
  config.py          ExperimentConfig dataclass and JSON serialization
  config_ui.py       In-app config editor (pygame)
  schedule.py        RISchedule and CODTimer
  session.py         ScheduleSession state machine
  display.py         Pygame rendering
  data.py            SessionRecorder, event/summary logging, GMLFit
  analysis.py        OLS generalized matching law fit
literature/          Key references (PDFs)
```

## Key References

- Klapes, B. T., et al. (2020). Rapid establishment of matching in humans. *JEAB*, 114(3).
- Klapes, B. T. (2021). Methodological improvements to PRESS-B. *JEAB*, 116(1).
- Bradshaw, C. M., et al. (1976). Behavior of humans in variable-interval schedules. *JEAB*, 26(1).
- Popa, A. (2013). *Matching in humans* [Doctoral dissertation].
