# Razer Chroma SDK Integration

Extracted from `components.js` (692 lines), `ChromaSDKWS.js` (7003 lines),
and `ChromaAI6.js` (913 lines) — v2.6.2.0.

---

## Architecture Overview

```
┌─────────────────────────┐      HTTP REST API       ┌─────────────────────┐
│  Razer Axon (WebView2)  │ ──────────────────────── │  Chroma SDK Service │
│                         │   localhost:54235         │  (Razer Synapse)    │
│  ChromaSDKWS.js         │                           │                     │
│  ├── heartbeat (PUT)    │                           │  Controls RGB LEDs  │
│  ├── createEffect (POST)│                           │  on all devices     │
│  └── setEffect (PUT)    │                           │                     │
│                         │                           └─────────────────────┘
│  ChromaAI6.js           │
│  ├── TensorFlow.js      │      .chroma files
│  ├── AI color analysis  │ ◄──────────────────────── Wallpaper preset
│  └── Dynamic generation │
│                         │
│  components.js          │      SVG visualization
│  └── SVG LED mapping    │ ──── Preview in UI
└─────────────────────────┘
```

---

## Chroma SDK REST API (ChromaSDKWS.js)

### Connection

```
URL: http://localhost:54235/razer/chromasdk
Secure: https://chromasdk.io:54236/razer/chromasdk  (not used)
Heartbeat: PUT {uri}/heartbeat  (every few seconds)
```

### Init

```
POST http://localhost:54235/razer/chromasdk
Body: {
  "title": "Razer Axon",
  "description": "Wallpaper RGB effects",
  "author": { "name": "Razer", "contact": "https://razer.com" },
  "device_supported": ["keyboard", "mouse", "mousepad", "headset", "keypad", "chromalink"],
  "category": "application"
}
Response: { "uri": "http://localhost:xxxxx/chromasdk", "sessionid": "..." }
```

After init, all subsequent calls use the returned `uri`.

### Device Types

```javascript
var EChromaSDKDeviceTypeEnum = {
  DE_1D: 0,    // 1-dimensional (linear LED strips)
  DE_2D: 1     // 2-dimensional (grid LEDs)
};

var EChromaSDKDevice1DEnum = {
  DE_ChromaLink: 0,  // 5 LEDs
  DE_Headset: 1,     // 5 LEDs
  DE_Mousepad: 2,    // 15 LEDs
  DE_MAX: 3
};

var EChromaSDKDevice2DEnum = {
  DE_Keyboard: 0,          // 6 rows × 22 columns
  DE_Keypad: 1,            // 4 rows × 5 columns
  DE_Mouse: 2,             // 9 rows × 7 columns
  DE_KeyboardExtended: 3,  // 8 rows × 24 columns (with underglow)
  DE_MAX: 4
};
```

### LED Grid Dimensions

| Device | Type | Rows | Columns | Total LEDs |
|--------|------|------|---------|------------|
| Keyboard | 2D | 6 | 22 | 132 |
| KeyboardExtended | 2D | 8 | 24 | 192 (includes 50 underglow) |
| Mouse | 2D | 9 | 7 | 63 |
| Keypad | 2D | 4 | 5 | 20 |
| ChromaLink | 1D | — | — | 5 |
| Headset | 1D | — | — | 5 |
| Mousepad | 1D | — | — | 15 |

### Create Effect

Each device type has its own endpoint:

```
POST {uri}/keyboard      — Keyboard effects
POST {uri}/mouse         — Mouse effects
POST {uri}/mousepad      — Mousepad effects
POST {uri}/headset       — Headset effects
POST {uri}/keypad        — Keypad effects
POST {uri}/chromalink    — ChromaLink effects
```

Request body for CUSTOM effect (individual LED control):
```json
{
  "effect": "CHROMA_CUSTOM",
  "param": [[0, 0, 16711680, ...], [0, 0, ...], ...]
}
```

For 2D devices: array of rows, each row is array of BGR int colors.
For 1D devices: flat array of BGR int colors.

Response:
```json
{ "result": 0, "id": "effect-uuid" }
```

### Set Effect

```
PUT {uri}/effect
Body: { "id": "effect-uuid" }
```

### Color Format

**BGR integer** (not RGB):
```javascript
function getHexColor(bgrColor) {
  var red = (bgrColor & 0xFF);
  var green = (bgrColor & 0xFF00) >> 8;
  var blue = (bgrColor & 0xFF0000) >> 16;
  return 'rgb(' + red + ',' + green + ',' + blue + ')';
}
```

---

## .chroma Animation Files

Each wallpaper can include Chroma presets — one file per device:

```
wallpaper_Keyboard.chroma
wallpaper_Mouse.chroma
wallpaper_Mousepad.chroma
wallpaper_Headset.chroma
wallpaper_Keypad.chroma
wallpaper_ChromaLink.chroma
```

### Animation Structure

```javascript
{
  DeviceType: EChromaSDKDeviceTypeEnum,  // DE_1D or DE_2D
  Device: EChromaSDKDevice*Enum,         // specific device
  Frames: [
    {
      Colors: [[row0_colors], [row1_colors], ...],  // 2D: array of rows
      // or
      Colors: [led0, led1, led2, ...],               // 1D: flat array
      Duration: 0.1  // seconds per frame
    },
    ...
  ]
}
```

Colors are BGR integers. Frame playback loops continuously.

---

## SVG LED Visualization (components.js)

The UI shows a visual preview of Chroma effects using SVG graphics.
Each device has an SVG with `class="led"` elements that get colored.

### Device LED Maps

#### Keyboard (Extended — 8×24 + 50 underglow LEDs)

Key-to-grid mapping uses `(row, column)` format:

| Row | Keys |
|-----|------|
| 1 | Knob, Esc, F1-F12, PrintScreen, ScrollLock, Pause, Media keys |
| 2 | \`, 1-0, -, =, Backspace, Insert, Home, PageUp, NumPad top row |
| 3 | Tab, Q-P, \[, \], \\, Delete, End, PageDown, NumPad 7-9, + |
| 4 | Caps, A-L, ;, ', Enter, NumPad 4-6 |
| 5 | LShift, Z-M, ,, ., /, RShift, ↑, NumPad 1-3, Enter |
| 6 | LCtrl, Win, LAlt, Space, RAlt, Fn, Menu, RCtrl, ←, ↓, →, NumPad 0, . |
| 7 | Underglow LEDs 12-39 (bottom edge) |
| 0-7 col 0/23 | Underglow LEDs 1-11, 40-50 (sides) |

Special keys: M1-M5 (macro), Knob (BlackWidow V4).

#### Mouse (9×7 grid)

```
LED 0,3,5,7,9,11,13  — Left side (7 LEDs, top to bottom)
LED 2,4,6,8,10,12,14 — Right side (7 LEDs, top to bottom)
LED 1                 — Scroll wheel
LED 15                — Logo
```

Mouse LED addressing uses `RZLED2` enum:
```
RZLED2_LEFT_SIDE1..7   — Left strip
RZLED2_RIGHT_SIDE1..7  — Right strip
RZLED2_SCROLLWHEEL     — Scroll wheel
RZLED2_LOGO            — Logo
```

#### Mousepad (15 LEDs)

Linear strip, mapped in reverse order (LED 14 → 0).

#### Headset (5 LEDs)

```
LED 0 — Bottom left
LED 1 — Bottom right
LED 2 — Top right
LED 3 — Center
LED 4 — Top left
```

#### ChromaLink (5 LEDs)

```
LED 0 — Center (index 4 in SVG)
LED 1-4 — Peripheral (indices 0-3 in SVG)
```

#### Keypad (4×5 grid)

20 keys mapped directly from the color grid.

---

## Chroma AI (ChromaAI6.js)

Uses **TensorFlow.js** to analyze wallpaper colors and generate dynamic Chroma effects.

### Model

- Loads `/chroma/model.json` — pre-trained classification model
- Loads `/chroma/classNames.json` — color class names
- Input: image pixel colors
- Output: dominant color classification

### Color Analysis Pipeline

```
Wallpaper Image → Resize to 100×100 → Extract pixel colors
  → RGB → HSL conversion
  → TF.js model prediction → Primary color class
  → Generate Chroma effect based on:
      - Dominant hue
      - Saturation
      - Brightness distribution
      - Color temperature
```

### Effect Generation

ChromaAI generates per-device effects:

```javascript
ChromaAI.config = {
  enabled: true,
  speed: 1.0,          // animation speed multiplier
  intensity: 1.0,       // color intensity
  backgroundEnabled: true,
  foregroundEnabled: true,
  foregroundRed: 68,     // #44d62c (Razer Green)
  foregroundGreen: 214,
  foregroundBlue: 44,
  backgroundRed: 0,
  backgroundGreen: 0,
  backgroundBlue: 0
};
```

The AI mode can be overridden by wallpaper-specific `.chroma` preset files
(see PlaySourceInfo.ChromaPreset in wallpaper-player.md).

---

## Integration with OpenRazer (Linux)

On Linux, [OpenRazer](https://openrazer.github.io/) provides a D-Bus interface
for Razer device control. The Chroma SDK REST API (`localhost:54235`) is a
Windows-only service (part of Razer Synapse).

To support Chroma on Linux, OpenAxon could:
1. Parse `.chroma` animation files
2. Convert BGR color frames to RGB
3. Send colors to OpenRazer via D-Bus (`org.razer`)
4. Or use the AI color analysis to generate effects from wallpaper thumbnails
