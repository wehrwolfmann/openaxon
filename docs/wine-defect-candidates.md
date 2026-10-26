# Wine defects — upstream candidates, analysed one by one

Measurements were taken on 2026-08-12 on **wine-11.15** (vanilla, package `wine 11.15-1.1`,
no staging, no DXVK) in a separate clean prefix `~/.wine-axon-bugs`.
Upstream freshness was checked against `master` on gitlab.winehq.org, duplicates —
via Bugzilla REST (`https://bugs.winehq.org/rest/bug?quicksearch=…`).

Ready-to-paste texts are in `~/Downloads/wine-axon/`,
reproducers are in its `repro/` subfolder.

Rules: fixes for Windows programs go **to Wine, not to Proton**; no report is filed
without our own measurement.

## Summary

| Candidate | Verdict | Where |
|---|---|---|
| `DCompositionCreateDevice` → `E_NOTIMPL` (WebView2) | **duplicate** of bug 58921 + bug 55432 | comment + attachment in both |
| `riched20`: `\ctint`/`\cshade` in `\colortbl` | **confirmed, no duplicate** | new bug, Product Wine / Component richedit |
| `shell32`: `IShellLinkW::QueryInterface` → `E_NOINTERFACE` | **dropped** — the behaviour is correct | at most a one-line ERR→WARN patch |
| `riched20`: `ReadStyleSheet skipping optional destination` | **deferred** — no visible breakage measured | — |
| `combase`: missing WinRT telemetry class | **dropped** — harmless, the class is not needed | — |
| Stubs (`WerRegisterCustomMetadata`, `clusapi`, `DecryptFileW`, …) | **dropped** — `fixme` noise | — |
| `wineserver -w` and the resident `MicrosoftEdgeUpdate.exe` | **not a Wine defect** | note in winetricks / AppDB |
| A layered window (`WS_EX_LAYERED`) turns black when a D3D swap chain is attached to it — hence the black WPF menu | **confirmed, no duplicate**, cause found and fix verified | new bug, Product Wine / Component winex11.drv |
| Russian labels in the tray icon menu render as boxes (WPF finds no fallback font) | **confirmed, no duplicate** | new bug, Product Wine / Component gdi32 |
| `explorer`: `WM_CONTEXTMENU` is also sent for icon version 3 | **deferred** — no measurement on real Windows | — |

---

## 1. DirectComposition / WebView2 — a duplicate, but the comment is valuable

The weightiest candidate turned out to be filed already, and twice:

* **bug 58921** "WebView2 does not work with Windows version setting 8.1 or newer"
  (UNCONFIRMED, filed 2025-11-04, duplicates 59370 and 59431 are attached to it).
  Comment zero has the same workaround we found: per-app `Version=win8`
  for `msedgewebview2.exe`.
* **bug 55432** "PlanetSide 2 launcher is completely white (needs
  dcomp.dll.DCompositionCreateDevice implementation)" (NEW since 2023-08, component `dcomp`).

**Not fixed upstream.** `dlls/dcomp/device.c` in master is 47 lines: all three entry
points print a FIXME and return `E_NOTIMPL`; only these are implemented in `dcomp.spec`,
the other 14 exports are `stub`. wine-staging has a separate patch set
`dcomp-DCompositionCreateDevice2` (which also caused a regression — bug 59918), upstream
has MR 10567 in progress; vanilla Wine remains a stub.

Measured on 11.15 with our own reproducer `repro/dcomp_min.c` (~90 lines, no
WebView2 or Razer needed — the program makes exactly the call Chromium makes
when the reported Windows version is ≥ 8.1):

```
reported Windows version: 10.0 build 19045
D3D11CreateDevice hr=0x00000000 feature_level=0xb000
QI IDXGIDevice hr=0x00000000
DCompositionCreateDevice(IDCompositionDevice)         hr=0x80004001
DCompositionCreateDevice2(IDCompositionDevice2)       hr=0x80004001
DCompositionCreateDevice3(IDCompositionDesktopDevice) hr=0x80004001
```

The D3D11 device and its `IDXGIDevice` are created fine — only creation of the
DirectComposition device fails. That is the single point because of which the
Chromium viz process hits a CHECK and the frame never reaches the window.

The value of our contribution: confirmation on 11.15, a third affected application
(Razer Axon 2.9.1.0 — the whole UI is WebView2, runtime 151.0.4129.78), and most
importantly a reproducer without the 120 MB installer, without Steam and without DXVK
(earlier measurements in 55432 were made with DXVK, for which the reporter was told off).

Text of the two comments: `02-dcomp-webview2-ДУБЛИКАТ-комментарии.md`.

---

## 2. `riched20`: `\ctint`/`\cshade` break the colour table — NEW BUG

This is the only candidate that goes upstream as a standalone bug.

The cause is in `dlls/riched20/reader.c`. The keyword table knows exactly three
colour table words:

```c
{ rtfColorName, rtfRed,   "red",   0 },
{ rtfColorName, rtfGreen, "green", 0 },
{ rtfColorName, rtfBlue,  "blue",  0 },
```

`\ctint`, `\cshade` and the theme words (`\cmaindarkone`, `\caccentone` …) —
legal inside `\colortbl` according to the RTF specification — are not recognised.
`ReadColorTbl()` cuts the entry short on them, prints `err:richedit:ReadColorTbl malformed entry`
and starts a **new** colour entry from the next token. One source entry
turns into three, every subsequent `\cfN` shifts its index, and the bogus entries
are created with the value "default colour", which is why the text gets `CFE_AUTOCOLOR`
instead of its own colour.

Measurement (`repro/riched_colortbl.c` — three documents that are identical per the
specification; we read `EM_GETCHARFORMAT` after `EM_STREAMIN`):

```
expected for every line: crTextColor=0x0000ff (R=255 G=0 B=0)

A plain colortbl      crTextColor=0x0000ff (R=255 G=0 B=0)
B \ctint\cshade       crTextColor=0x007fff (R=255 G=127 B=0)  [CFE_AUTOCOLOR]
C Word theme colour   crTextColor=0x007fff (R=255 G=127 B=0)  [CFE_AUTOCOLOR]
```

This is not exotic: Word 2007 and newer writes it this way for any document with theme
colours, and this is exactly the kind of RTF that Inno Setup installers put into the
licence — hence our six `malformed entry` messages when the Razer licence is shown.

No duplicate. The closest neighbours: **bug 20482** (2009, component richedit) — it has the same
`ReadColorTbl malformed entry`, but was filed for a symptom of a specific program
("Tunnelier dialog too tall") and the cause has not been analysed in 17 years; **bug 44966** —
about `ReadStyleSheet`, a different place. Our report gives the cause, a minimal example and
a ready unit test.

Text: `01-riched20-colortbl-ctint-cshade.md`.

---

## 3. `shell32`: `IShellLinkW::QueryInterface` → `E_NOINTERFACE` — dropped

Running `RazerAxon.exe` with `WINEDEBUG=+shell` in our own prefix showed exactly which
IIDs are queried and left unanswered:

| IID | What it is |
|---|---|
| `{ecc8691b-c1db-4dc0-855e-65f6c551af49}` | `INoMarshal` |
| `{94ea2b94-e9cc-49e0-c0ff-ee64ca8f5b90}` | `IAgileObject` |
| `{00000003-0000-0000-c000-000000000046}` | `IMarshal` |
| `{5c13e51c-4f32-4726-a3fd-f3edd63da3a0}` | an undocumented interface the COM runtime probes right after `CoCreateInstance` |

All four are standard COM runtime "probes" right after an object is created,
and `E_NOINTERFACE` is the **correct** answer to them: the shell link object is not agile and
is marshalled the standard way. There is no behavioural defect; right after these four
queries `IShellLinkW` and `IPersistFile` are returned normally, and `SetPath` works.

What remains is cosmetic: Wine prints a failed `QueryInterface` at `ERR` level
(`dlls/shell32/shelllink.c`, end of `IShellLinkW_fnQueryInterface`), although by common
Wine practice a failed QI is `WARN`/`TRACE`. Because of this, the log of any program
carries four red lines for no reason. Good as a one-line patch in an MR,
but not as a bug report — a report about a log level would be closed.

---

## 4. `riched20`: `ReadStyleSheet skipping optional destination` — deferred

The message is printed when a style sheet entry starts with `\*` (`{\*\cs10 …}`) —
Wine skips such an entry entirely. Bug 44966 (REOPENED, richedit) already sits on
this same spot. We could not measure any visible breakage in our scenario: the licence text
is shown, and styles are barely used in Wine's implementation. Without a measured
user-visible symptom we do not file — otherwise it would be a second 44966.

---

## 5. `combase`: missing WinRT telemetry class — dropped

`RoGetActivationFactory` does not find
`Windows.System.Diagnostics.Telemetry.PlatformTelemetryClient` (requested from inside Edge
Update). It is a Microsoft telemetry class — there is no reason to implement it in Wine,
failing is the correct behaviour, and installation does not suffer from it. Nothing to file.
Similar "missing WinRT class" bugs exist in Bugzilla (for example 56914 about
`Windows.Data.Json.JsonObject`), but there the class is genuinely needed by the application.

## 6. Stubs along the way — dropped

`WerRegisterCustomMetadata`, `clusapi:ClusterEnum`, `advapi:DecryptFileW`,
`nls:get_dummy_preferred_ui_language`, `msi:internal_ui_handler` — all `fixme`,
none of them broke anything. These are regular markers of unfinished code, not defects;
a "saw a fixme" report would be closed.

## 7. `wineserver -w` and the resident `MicrosoftEdgeUpdate.exe` — not in Wine

Installing WebView2 leaves a perpetual `MicrosoftEdgeUpdate.exe /c` in the prefix, after
which any winetricks verb hangs on `wineserver -w` (measured: the process stayed alive for 1010 s,
killing exactly that PID unblocked the installation immediately). Wine behaves
correctly — it honestly waits for the last process of the prefix. The place for a fix is winetricks
(kill the resident Edge Update before `wineserver -w`) and/or a line in AppDB.

---

## 8. Tray icon menu — no Wine defect (measured 2026-08-14)

We investigated the complaint "right-clicking the tray icon does nothing" (pass 17
in `install-under-wine-2.9.1.0.md`). Tested on wine-11.15, Plasma 6.7.4
on Wayland, icons are relayed by `xembedsniproxy`.

**Wine's tray works.** `WINEDEBUG=+systray` shows that the synthetic click from
`xembedsniproxy` arrives and is passed to the owner in full — `WM_RBUTTONDOWN`,
`WM_RBUTTONUP`, `WM_CONTEXTMENU`; the menu window is created and positioned correctly
(157×186, flipped upward above the bottom panel). The control program
`repro/tray_min.c` (plain Win32, `Shell_NotifyIcon` + `TrackPopupMenu`) draws its menu
completely in the same tray.

The content stayed black because Razer Central's tray menu is drawn by WPF
(`Hardcodet.Wpf.TaskbarNotification`), which goes through Direct3D 9 by default.
The `Avalon.Graphics\DisableHWAcceleration` key fixes the menu.

⚠️ **The "no Wine defect" conclusion turned out to be wrong — see section 9.** The 2026-08-14
measurement showed that the black menu is caused by a real Wine defect in `winex11.drv`, and the registry
key merely steers WPF away from the broken path. The section is left as is so that
the history of the investigation stays visible.

**Side observation that needs a measurement on real Windows.**
`programs/explorer/systray.c` sends `WM_CONTEXTMENU` for any icon version greater
than zero:

```c
if (icon->version > 0)
{
    if (msg == WM_LBUTTONUP) notify_owner( icon, NIN_SELECT, lparam );
    if (msg == WM_RBUTTONUP) notify_owner( icon, WM_CONTEXTMENU, lparam );
}
```

According to Microsoft's documentation, `WM_CONTEXTMENU` belongs to `NOTIFYICON_VERSION_4`,
not to version 3. We measured the visible consequence: on a single right-click Razer Central
opens the menu **twice** — two menu windows appear one after another in the window list
(`0x2600012`, then `0x2600014`), and the first is immediately destroyed by the second. It does no
harm; the resulting menu works.

We will **not** file this: by our own rule, no report goes out without our own measurement,
and we have nothing to check real Windows behaviour on here. If a Windows machine
becomes available — measure which messages arrive with `NIM_SETVERSION` = 3, and then
decide. The reproducer is ready: `repro/tray_min.c` supports both version 3 and version 4,
and prints every message it receives.

---

## 9. Russian labels as boxes: WPF under Wine has not a single fallback font — NEW BUG (measured 2026-08-14)

Complaint: in the context menu of the Razer Central tray icon, Latin text is readable, but the Russian
items are rows of empty rectangles (screenshot `~/Pictures/Screenshots/axon-трей-меню-работает.png`).

### What renders the text

Razer Central ships **its own** font. `Razer Central.exe` contains 23 font
files: ten styles of the brand font **RazerF5** (SIL OFL, derived from Titillium)
and thirteen styles of Roboto. They are referenced in WPF resources as
`…/Fonts/#RazerF5`, `…/Fonts/#RazerF5 Light`, `…/Fonts/#Roboto` (`UICommon.dll`).

Coverage measurement (parsing the `cmap` tables of the extracted files):

| Font | Glyphs | Cyrillic |
|---|---|---|
| RazerF5 (all 10 styles) | 229-230 | **0** |
| Roboto (13 styles) | 896 | 255 |

So Roboto has Cyrillic, while RazerF5 has none at all. The menu is drawn with RazerF5 —
otherwise the Russian items would be readable.

### Where the Cyrillic gets lost

WPF uses **neither** DirectWrite text layout nor its fallback font selection
(the dwrite maintainer says the same in bug 50021). It has its own table —
`GlobalUserInterface.CompositeFont`, installed together with .NET. The table
is written in terms of Windows system font names. In the Windows 10 section, the
`U+0000-U+052F` range (Latin, Greek, **Cyrillic**) is covered by a single line:

```
<FontFamilyMap Unicode = "0000-052F, 0590-05FF, …"
               Target  = "Segoe UI, Segoe UI Symbol, Ebrima" />
```

None of these three fonts exists in a Wine prefix, nor can it — they are non-free.
In total, the Windows 10 RS5 section names **44** fallback families; Wine finds
**one** of them (Tahoma, and even it is not listed in the Cyrillic chain), and 43 are not
found. For Cyrillic the chain is entirely empty, so WPF draws nothing,
and the menu shows `.notdef`.

An ordinary WPF program does not notice the problem: its default font comes from
`SystemParametersInfo`, and Wine answers "Tahoma", which has Cyrillic.
Exactly those programs suffer that bring their own brand font — and brand fonts are almost
always Latin-only.

### Of the three hypotheses, the second is right

* **(a) substitution does not kick in** — no: the mechanism is intact, it runs into emptiness.
* **(b) there is nothing to substitute** — **yes**, but not in the way we thought in the previous pass:
  the prefix has plenty of Cyrillic fonts (DejaVu, Noto, Liberation — WPF sees 319
  families). What is missing are fonts **with exactly the names** written in
  Microsoft's table. That is why dropping in `tahoma.ttf` and `Roboto-Regular.ttf`
  in the previous pass did not help: wrong name. The conclusion "WPF takes the font from Razer's
  resources" was only half right — the font does come from there, but
  the boxes are caused not by that, but by the broken fallback chain.
* **(c) a Wine defect in font matching** — partly: the matching itself does not break, but Wine
  **provides** no font under the required names, even though it has a mechanism for that
  which is not used (see below).

### A measurement that separates the layers

`repro/wpf_fonts.cs` — a WPF probe, built with the very `csc.exe` that is already in
the prefix, no SDK needed. For each name it prints whether the family is found, whether
it covers Latin and Cyrillic, and the outline bounds actually produced by
`FormattedText.BuildGeometry`. Empty bounds = nothing was drawn.

```
family "RazerF5"   resolved=True latin=True cyrillic=False
    latin     outline=53,7x14,8
    cyrillic  outline=EMPTY (nothing drawn)
family "Tahoma"    resolved=True latin=True cyrillic=True
    cyrillic  outline=75,6x15,0
family "Segoe UI"  resolved=False
```

`repro/gdi_cyrillic.c` — the same through plain GDI, to compare the layers:

```
face "Segoe UI"  cyrillic missing_glyphs=0/9 painted=637  (GetTextFace Liberation Sans)
face "RazerF5"   cyrillic missing_glyphs=9/9 painted=653  (GetTextFace RazerF5)
```

Win32 does draw Cyrillic: asked for "Segoe UI", Wine silently substituted Liberation Sans.
This leniency lives at the font **selection** level and is invisible to whoever first
asks "does such a family exist". WPF asks exactly that, gets "no",
and its whole fallback table dies along with that answer.

Measured as a side effect: if the **requested** family is not found either, WPF under Wine does not
fall back to any default, but silently crashes the process inside text layout
(`wine wpf_fonts.exe "Segoe UI"` — the output just stops, no exception, no message).
This looks like the same root as bug 50021 (PS Remote Play, an assertion failure
in `TypefaceMap.MapUnresolvedCharacters`, "installing corefonts changes the behaviour").

### How to fix it

Wine **already has** the required mechanism, just without default entries:
`HKCU\Software\Wine\Fonts\Replacements` — it is read both by `win32u/font.c`
(`load_gdi_font_replacements`) and by `dwrite/font.c`. It exposes an existing font under
an additional name and steps aside on its own if a real font with that name appears.
`REG_MULTI_SZ` is supported and the first font found is taken, so a single entry works for
any distribution.

Measured on the prefix, `*.CompositeFont` files untouched:

```
before family "RazerF5"  cyrillic outline=EMPTY (nothing drawn)
after  family "RazerF5"  cyrillic outline=80,8x16,0   (Noto Sans metrics)
```

Screenshots `repro/wpf_fonts_before.png` and `repro/wpf_fonts_after.png`.

Cross-check: if instead of the registry an existing family is appended to every
`Target` inside `*.CompositeFont`, it is fixed too (3684 edits in 16 files). The registry is
better — we do not touch files that belong to .NET.

In `scripts/install-axon.sh` this is step 9 (`setup_fonts`): three entries for
`Segoe UI`, `Segoe UI Symbol` and `Ebrima` with the list
`Noto Sans|DejaVu Sans|Liberation Sans|Arial|Tahoma`. Tahoma at the end is a reliable floor:
it ships with Wine itself and covers both Latin and Cyrillic.

### No duplicates

We searched Bugzilla REST for `WPF font fallback`, `Segoe UI missing`, `WPF Cyrillic`,
`Segoe UI substitution`. The closest:

* **bug 50021** (NEW, 2020) — PS Remote Play crashes in `MapUnresolvedCharacters`.
  Same root, but filed as a crash of one program, and "install Arial" is the fix.
* **bug 59925** (UNCONFIRMED, 2026-06) — WPF .NET 8 draws `U+002D` as `.notdef`.
  Different symptom, different character, the analysis leads into dwrite.

There is no general report about "Wine finds not a single family from the WPF fallback table".
Text of the new bug — `~/Downloads/wine-axon/ВСТАВИТЬ-В-БРАУЗЕРЕ/7-новый-баг-WPF-шрифты-*.txt`.

---

## What is left for a human

1. File **one** new bug: Product `Wine`, Component `richedit`, Version `11.15`,
   title and body — from `01-riched20-colortbl-ctint-cshade.md`, attach
   `repro/riched_colortbl.c` and `repro/riched_colortbl.out`.
2. Paste the two comments from `02-dcomp-webview2-ДУБЛИКАТ-комментарии.md`
   into bug 58921 and bug 55432, attach `repro/dcomp_min.c` to both.
3. File a second new bug: Product `Wine`, Component `gdi32`, Version `11.15`,
   title and body — from `ВСТАВИТЬ-В-БРАУЗЕРЕ/7-новый-баг-WPF-шрифты-*.txt`, attach
   `repro/wpf_fonts.cs`, `repro/gdi_cyrillic.c`,
   `repro/wpf_fonts_before.png` and `repro/wpf_fonts_after.png`.
4. Optionally — a one-line log level patch in `shell32/shelllink.c`
   as a separate MR.

---

## 9. ⭐ Layered window + Direct3D = black rectangle (measured 2026-08-14)

Back to section 8: the question "why does WPF's hardware path under Wine produce a black window"
has been investigated to the end, and **there is a Wine defect**. It is not in WPF, not in `d3d9` and not in the tray.

**Where it breaks.** Everything WPF does works correctly:

* `Direct3DCreate9Ex`, `CreateDeviceEx`, `CreateAdditionalSwapChain`,
  `GetRenderTargetData`, `LockRect` — all return `S_OK`, there is not a single
  `E_NOTIMPL`/`D3DERR_*` in the `+d3d9,+d3d` trace;
* `RenderCapability.Tier` = `0x00020000` (tier two, hardware) —
  WPF under Wine honestly believes there is a graphics card and does not fall back by itself;
* the pixels read back are **correct**, `UpdateLayeredWindow` returns `TRUE`.

The window is black anyway, because the swap chain attaches a **client
X window** to the window — an opaque child exactly the size of the window, which covers
everything `UpdateLayeredWindow` has drawn:

```
xwininfo: Window id: 0x5c00006 "layered"
   Parent window id: 0x350 (the root window)
      1 child:
      0x5a00036 (has no name): ()  300x120+0+0  +80+80
```

**What exactly is to blame.** `dlls/winex11.drv/init.c` has a ready mechanism: when
a window needs composition, the client window is detached and output is redirected through
XComposite (`client_surface_update_offscreen`). This is decided by `needs_offscreen_rendering()`,
and its list has three cases — DPI scaling, a child window, a window with children. **A layered
window is not there**, even though its contents are exactly what gets composited.

**Verified with a fix.** One line

```c
if (NtUserGetWindowLongW( hwnd, GWL_EXSTYLE ) & WS_EX_LAYERED) return TRUE;
```

flips the measurement: the pixel at the centre of the window was `rgb(0,0,0)` and became `rgb(255,0,0)`.
On a WPF probe with four windows in one program, exactly the two transparent ones turned black
before the fix; after the fix all four are drawn.

**Reproducers (no Razer and no account needed), in `repro/` next to the reports:**

| File | What it does |
|---|---|
| `d3d9_layered.c` | ~190 lines of plain Win32 + D3D9Ex: a layered window, `Clear` to red, `GetRenderTargetData`, `UpdateLayeredWindow`; the `nod3d` and `plain` modes are controls |
| `wpf_layered.cs` | the same in WPF: normal window / layered window / opaque popup / transparent popup; built with the stock `csc.exe` from .NET 4.8 in the prefix |
| `winex11-layered-offscreen.patch` | the verified one-line fix |

**The impact is wider than Axon:** every menu, tooltip and drop-down list
of every WPF program turns black, as does every window with `AllowsTransparency="True"`. Hence
the persistence of the `DisableHWAcceleration` advice across forums.

**Verified on wine-staging 11.15** — same result (pixel `rgb(0,0,0)`).
The `winewayland.drv` driver could not be measured; the report says so.

**No duplicate in Bugzilla.** The closest is bug 49055 "Multiple .NET WPF 4.x
applications show black screen…" (NEW since 2020, active: comments from 07–11.08.2026):
it has the same symptom and the same workaround, but digs in a different direction — into `Clear()`
going past the viewport on an additional swap chain. Our cause is different, so
we file a separate bug and leave a cross-reference.

Texts to paste: `ВСТАВИТЬ-В-БРАУЗЕРЕ/8-новый-баг-слоёные-окна-*`,
`9-комментарий-в-баг-49055.txt`.

Screenshots as evidence:

* `~/Pictures/Screenshots/wine-wpf-слоёные-окна-чёрные-до.png`
* `~/Pictures/Screenshots/wine-wpf-слоёные-окна-исправлено-после.png`
* `~/Pictures/Screenshots/wine-слоёное-окно-d3d9-чёрное-до.png`
* `~/Pictures/Screenshots/wine-слоёное-окно-d3d9-красное-после.png`
* `~/Pictures/Screenshots/wine-слоёное-окно-без-d3d9-контроль.png`
