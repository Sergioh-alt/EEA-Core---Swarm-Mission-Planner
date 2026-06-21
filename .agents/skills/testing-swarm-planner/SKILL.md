---
name: testing-swarm-planner
description: Test the EEA Swarm Mission Planner Streamlit app end-to-end. Use when verifying UI tabs, pipeline logic, or Plotly chart rendering.
---

# Testing EEA Swarm Mission Planner

## Prerequisites

- Python 3.12+ with dependencies from `requirements.txt`
- Streamlit running on port 8501
- Playwright (for programmatic slider/dropdown interaction)

## Setup

```bash
cd /home/ubuntu/repos/EEA-Swarm-Mission-Planner
pip install -r requirements.txt
streamlit run app.py --server.port 8501 --server.headless true &
```

Wait for "You can now view your Streamlit app" message before testing.

## Key Test Scenarios

### 1. Default Scenario (50ha Wheat, 4 drones, 5000mAh, 10L, 25C, 10km/h)

Expected values:
- **Recommendation**: GO WITH CAUTION, Feasible=YES, Confidence=68%, Coverage=99%, Duration=2h 03m
- **Swarm Planning**: 4 sectors, 2x2 grid, 12.5 ha/drone, 100% balance
- **Resources**: 400.0 L total liquid, 36 refills, Battery+Liquid bottleneck, 340% battery per drone
- **Risk Assessment**: Critical (0.80), 1 critical risk (Battery), Mission Viable=YES

### 2. High Wind Edge Case (40 km/h)

Expected: NO-GO, Feasible=NO, Confidence=0%, No-Fly conditions, 3 critical risks

### 3. Crop Type Change (Wheat to Rice)

Expected: Spray Rate changes 8.0 -> 15.0 L/ha, Complexity Low -> High, Duration increases

### 4. Mission Timeline (Phase 6 — default scenario)

Expected values for Drone 1 detail panel:
- **Overview**: Mission Duration=2h 07m, Drones=4, Total Events=104
- **Time breakdown**: Spray=72.0 min, Transit=1.0 min, Idle/Refill=54.0 min
- **Physics**: Speed=18.5 km/h, Wind Loss=-6.0%, Payload=10.0 kg, Turn Time=236s
- **Battery**: Base=377.5 Wh, Wind=+0.7 Wh, Payload=+113.2 Wh, Total=509.4 Wh (459%)
- **Liquid**: Needed=100.0 L, Loads=10, Refills=9, Refill Time=45.0 min
- **Event Log**: 26 events, starts with Launch, ends with Done

### 5. Wind Reactivity on Timeline (30 km/h)

Expected changes vs default (10 km/h):
- Speed: 18.5 → 15.5 km/h
- Wind Loss: -6.0% → -18.0%
- Battery Wind: 0.7 → 6.6 Wh
- Duration: 2h 07m → 2h 40m

## Interacting with Streamlit Sliders

**Important**: Streamlit sliders might not respond to direct click-drag via the computer tool. Use Playwright via CDP instead:

```python
import asyncio
from playwright.async_api import async_playwright

async def set_slider(label, target_value, current_value):
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:29229')
        context = browser.contexts[0]
        page = None
        for pg in context.pages:
            if 'localhost:8501' in pg.url:
                page = pg
                break
        if page is None:
            page = context.pages[0]
        
        slider = page.locator(f'div[aria-label="{label}"]')
        await slider.click()
        await asyncio.sleep(0.3)
        
        diff = target_value - current_value
        key = 'ArrowRight' if diff > 0 else 'ArrowLeft'
        for _ in range(abs(diff)):
            await page.keyboard.press(key)
            await asyncio.sleep(0.05)
        
        await asyncio.sleep(2)

asyncio.run(set_slider("Wind Speed (km/h)", 40, 10))
```

## Interacting with Streamlit Dropdowns

```python
# Change crop type via Playwright
crop_select = page.locator('input[aria-label*="Crop Type"]')
await crop_select.click()
await asyncio.sleep(1)
await page.keyboard.type('Rice')
await asyncio.sleep(0.5)
await page.keyboard.press('Enter')
await asyncio.sleep(3)
```

## Playwright Page Index

**Important**: The Streamlit page index varies depending on whether Chrome has other tabs open. Check `context.pages` length and find the page with URL containing `localhost:8501`. The page may be at index 0 (if only one tab) or index 1 (if chrome://new-tab-page is open). Use this pattern:

```python
page = None
for p in context.pages:
    if 'localhost:8501' in p.url:
        page = p
        break
if page is None:
    page = context.pages[0]
```

## Known Issues

- Plotly might not support 8-character hex colors with alpha (e.g., `#2196F333`). Use `rgba()` format instead. This was fixed in `ui/swarm_view.py` with a `_hex_to_rgba()` helper.
- Streamlit slider thumb positions are hard to calculate for click-drag; use Playwright arrow keys instead.
- When using Playwright CDP, the Streamlit page index may vary — always search by URL rather than hardcoding an index.

## Verification Checklist

- [ ] All 5 main tabs render without errors (Recommendation, Swarm Planning, Resources, Risk Assessment, Mission Timeline)
- [ ] All Plotly charts render (sector map, route preview, battery bars, liquid bars, timeline Gantt, risk radar)
- [ ] Pipeline is reactive (changing inputs updates all tabs including Timeline)
- [ ] NO-GO triggers correctly when wind > 35 km/h
- [ ] Crop profiles update sidebar card and pipeline outputs
- [ ] Assignment Table shows correct column headers and row count matching drone count
- [ ] Timeline Gantt shows colored segments per drone (Launch, Transit, Spray, Refill, Batt Swap, Return)
- [ ] Drone expander panels show Physics, Battery, Liquid sections with correct values
- [ ] Event Log table renders with Time, Type, Description, Duration columns
