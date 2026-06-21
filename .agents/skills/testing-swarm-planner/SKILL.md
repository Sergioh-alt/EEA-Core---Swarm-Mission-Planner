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

## Interacting with Streamlit Sliders

**Important**: Streamlit sliders might not respond to direct click-drag via the computer tool. Use Playwright via CDP instead:

```python
import asyncio
from playwright.async_api import async_playwright

async def set_slider(label, target_value, current_value):
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://localhost:29229')
        context = browser.contexts[0]
        # Streamlit page is typically pages[1] (pages[0] is chrome://new-tab-page)
        page = context.pages[1]
        
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

## Known Issues

- Plotly might not support 8-character hex colors with alpha (e.g., `#2196F333`). Use `rgba()` format instead. This was fixed in `ui/swarm_view.py` with a `_hex_to_rgba()` helper.
- Streamlit slider thumb positions are hard to calculate for click-drag; use Playwright arrow keys instead.
- When using Playwright CDP, the Streamlit page is typically `context.pages[1]` (index 1), not `context.pages[0]` which is `chrome://new-tab-page`.

## Verification Checklist

- [ ] All 4 main tabs render without errors (Recommendation, Swarm Planning, Resources, Risk Assessment)
- [ ] All Plotly charts render (sector map, route preview, battery bars, liquid bars, timeline, risk radar)
- [ ] Pipeline is reactive (changing inputs updates all tabs)
- [ ] NO-GO triggers correctly when wind > 35 km/h
- [ ] Crop profiles update sidebar card and pipeline outputs
- [ ] Assignment Table shows correct column headers and row count matching drone count
