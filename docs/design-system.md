# Razer Axon Design System - CSS Specification Extract

Extracted from: `2c05d5e95eb0ce13_0.css` (v2.6.2.0)
All classes use the `sequoia-` prefix (Sequoia = internal codename for Axon).

---

## Design Tokens

### Color Palette

```
Primary Green:       #44d62c   (Razer Green)
Primary Green Hover: #7ce26b
Primary Green Dark:  #30961f / #359b24
Primary Green Deep:  #226916   (slider rail)
Primary Green Alt:   #107100   (nav inactive text)

Background Level 0:  #1a1a1a  (body, main content)
Background Level 1:  #222     (sidebar, cards bg, playlist bar, header)
Background Level 2:  #111     (inputs, scrollbar track, modal deep bg)
Background Level 3:  #161616  (search input, select)
Background Level 4:  #000     (borders, dropdown bg, context menu)
Background Hover:    rgba(0,0,0,.3)   (icon hover overlay)
Background Hover 2:  #191919  (menu item hover)
Background Hover 3:  #282828  (select item hover)
Background Hover 4:  #2e2e2e  (settings menu hover)

Text Primary:        #fff
Text Secondary:      #ccc / #c8c8c8
Text Tertiary:       #bbb / #bdbdbd
Text Muted:          #909090
Text Dim:            #767676
Text Disabled:       #666

Border Primary:      #000
Border Secondary:    #555 / #5d5d5d
Border Input:        #0c0c0c
Border Hover:        #666

Error/Danger:        #ba0404  (delete button hover)
Error Red:           #e72424  (download error)
Error Red Dark:      #820303
Error Red Bright:    #f53333  (close button hover)
Error Orange:        #f30

Warning/Pending:     #ffb94f  (download pending)
Warning Badge:       #ba0404  (notification badge)
Warning Icon:        #FFA900

Gold:                #ffa800
Blue:                #30d5ff

Skeleton:            #555     (loading placeholder)
Scrollbar Thumb:     #585858
Switch Off:          #787878
```

### Typography

```css
/* Font Families */
font-family: roboto_regular, razerf5_mdmedium;  /* base */
font-family: roboto_regular;    /* body text, inputs */
font-family: roboto_bold;       /* bold text, primary button */
font-family: roboto_medium;     /* card creator text */
font-family: roboto_light;      /* light weight */
font-family: razerf5_mdmedium;  /* headings, nav items */
font-family: razerf5_bold;      /* card titles, accent text */
font-family: razerf5_light;     /* large headings, prize names */
font-family: razerf5_thin;      /* extra light */

/* @font-face sources */
/* All served from https://axon-assets-cdn.razerzone.com/static/prod/2.6.2.0/assets/ */
/* RazerF5.{eot,woff,ttf,svg} - razerf5_mdmedium */
/* razerf5-bold-webfont.ttf    - razerf5_bold */
/* razerf5-light.otf           - razerf5_light */
/* razerf5-thin.otf            - razerf5_thin */
/* Roboto-Bold.ttf             - roboto_bold */
/* Roboto-Medium.ttf           - roboto_medium */
/* Roboto-Regular.ttf          - roboto_regular */
/* Roboto-Light.ttf            - roboto_light */

/* Font Sizes */
Base:       14px
Small:      12px / 13px
Large:      16px
XLarge:     18px
XXLarge:    21px  (nav items)
Heading:    24px  (cards title)
Hero:       36px  (win modal heading)
Tiny:       10px  (beta badge, notification count)
Micro:      8px   (notice badge)
```

### Spacing Scale

```
2px, 4px, 8px, 12px, 16px, 20px, 24px, 28px, 32px, 48px
Most common: 8px (small gap), 16px (standard), 24px (large)
```

### Border Radius

```
Micro:   2px  (most elements: buttons, cards, inputs, borders)
Small:   4px  (context menu, tags, search input border-radius)
Round:   100% (avatars, radio, badges)
Pill:    8px  (switch track)
Full:    13px (pill buttons, account menu items)
```

### Shadows

```css
box-shadow: -3px 0 6px 0 rgba(0,0,0,.12);  /* modal / side panel */
```

### Opacity Scale

```
0.3  - disabled hover icons
0.4  - disabled buttons
0.5  - unfocused action icons
0.6  - sidebar icons default, playlist controls
0.65 - search close button
0.7  - share/more icons
0.75 - action icons, status icons
0.8  - disabled checkbox, madal close
1.0  - hover state
```

---

## 1. Global Styles

```css
::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}
::-webkit-scrollbar-track {
  border-radius: 10px;
  width: 10px;
  background: #111;
}
::-webkit-scrollbar-thumb {
  border-radius: 5px;
  background: #585858;
}
::-webkit-scrollbar-thumb:hover {
  background: #44d62c;
}
::-webkit-scrollbar-thumb:active {
  background: #359b24;
}

::placeholder {
  font-style: normal !important;
}

body, div, html, p {
  margin: 0;
  padding: 0;
}

body, html {
  height: 100%;
  font-size: 14px;
  font-family: roboto_regular, razerf5_mdmedium;
  cursor: default;
  background: #1a1a1a;
}

#root {
  height: 100%;
  box-sizing: border-box;
}

input, textarea {
  font-family: roboto_regular;
}

input {
  border: 1px solid #0c0c0c;
  background: #111;
  border-radius: 2px;
}
input:active, input:focus {
  outline: none;
  border-color: #44d62c;
}
input:hover {
  border-color: #666;
}
input::placeholder, textarea::placeholder {
  font-style: italic;
}
```

---

## 2. Layout

```css
.sequoia-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sequoia-main {
  position: relative;
  flex: 1;
  display: none;            /* hidden by default */
  flex-direction: row;
  overflow-y: auto;
}
.sequoia-main.show {
  display: flex;
}

.sequoia-content {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: #1a1a1a;
}
.sequoia-content.hide {
  display: none;
}
```

**Layout hierarchy:**
```
.sequoia-container (column flex, full height)
  .sequoia-header-title-bar (32px)
  .sequoia-nav-bar (48px, green)
  .sequoia-main (row flex, flex:1)
    .sequoia-left-container (260px sidebar)
    .sequoia-content (flex:1)
      .sequoia-wallpaper-list (wallpaper grid area)
    [right-madal-mask] (400px detail panel, slides in)
  .sequoia-playlist-panel (fixed bottom, 153px)
```

---

## 3. Header / Nav

### Title Bar (Window Chrome)

```css
.sequoia-header-title-bar {
  background: #222;
  height: 32px;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
}

.sequoia-header-title-bar .sequoia-header-logo {
  margin-left: 28px;
  line-height: 32px;
  display: flex;
  align-items: center;
  color: #fff;
  vertical-align: middle;
}
.sequoia-header-title-bar .sequoia-header-logo img {
  width: 24px;
  height: 24px;
  margin-right: 28px;
}

.sequoia-header-title-bar .sequoia-header-beta {
  font-size: 10px;
  background: #44d62c;
  line-height: 14px;
  padding: 0 2px;
  margin-left: 8px;
  color: #000;
  border-radius: 2px;
  font-family: roboto_regular;
}

/* Window controls */
.sequoia-header-title-bar .sequoia-bar-op {
  display: inline-block;
  width: 48px;
  height: 32px;
  opacity: 0.6;
}
.sequoia-header-title-bar .sequoia-bar-op:hover {
  opacity: 1;
}
.sequoia-header-title-bar .sequoia-bar-op.close:hover {
  background: #f53333 url(...) no-repeat 50%;
}

/* Monitor selector in title bar */
.sequoia-header-title-bar .sequoia-bar-monitor {
  display: inline-block;
  line-height: 32px;
  padding: 0 16px;
  background: #000;
  color: #fff;
  font-size: 12px;
  margin-right: 4px;
}
```

### Nav Bar (Primary Navigation)

```css
.sequoia-nav-bar {
  height: 48px;
  line-height: 48px;
  background: #44d62c;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
}

.sequoia-nav-bar .sequoia-nav-list {
  line-height: 48px;
  font-size: 21px;
  color: #107100;           /* inactive nav text */
  font-family: razerf5_mdmedium;
}
.sequoia-nav-bar .sequoia-nav-list .cur {
  color: #000;              /* active nav text */
}
.sequoia-nav-bar .sequoia-nav-list > span:nth-child(n+3) {
  padding: 0 20px;
}
.sequoia-nav-bar .sequoia-nav-list > span:hover {
  background: rgba(0,0,0,.1);
  color: #000;
}

/* Nav-1 items in title bar */
.sequoia-header-title-bar .sequoia-nav-1 {
  position: relative;
  padding: 0 20px;
  color: #909090;
  display: flex;
  align-items: center;
}
.sequoia-header-title-bar .sequoia-nav-1.current,
.sequoia-header-title-bar .sequoia-nav-1:hover {
  color: #fff;
}

/* Notification badge */
.sequoia-header-title-bar .sequoia-nav-newnum {
  position: absolute;
  top: 1px;
  right: 0;
  min-width: 8px;
  height: 14px;
  border-radius: 7px;
  background: #ba0404;
  color: #fff;
  font-size: 10px;
  text-align: center;
  line-height: 14px;
  padding: 0 4px;
}

/* Nav operation icons */
.sequoia-nav-bar .sequoia-nav-op {
  display: inline-block;
  height: 48px;
  width: 48px;
  border-radius: 100%;
  margin-right: 16px;
}

/* Avatar in nav */
.sequoia-nav-bar .sequoia-nav-op.avatar > span {
  display: inline-block;
  margin-top: 8px;
  margin-left: 14px;
  width: 32px;
  height: 32px;
  background-size: cover;
  border-radius: 100%;
}

/* Account dropdown */
.sequoia-nav-bar .sequoia-nav-account {
  color: #ccc;
}
.sequoia-nav-bar .sequoia-nav-account > div.sequoia-nav-account-name {
  color: #44d62c;
}
.sequoia-nav-bar .sequoia-nav-account > div {
  line-height: 16px;
  padding: 5px 0 5px 16px;
}
.sequoia-nav-bar .sequoia-nav-account .menu {
  border-radius: 13px;
  margin-bottom: 4px;
}
.sequoia-nav-bar .sequoia-nav-account .menu:hover {
  background: #191919;
}

/* History back/forward */
.sequoia-nav-bar .sequoia-nav-history {
  width: 40px;
  height: 48px;
  opacity: 0.3;
}
.sequoia-nav-bar .sequoia-nav-history:hover {
  background: rgba(0,0,0,.1) url(...) no-repeat 50%;
  opacity: 1;
}
.sequoia-nav-bar .sequoia-nav-history.next {
  transform: rotate(180deg);
}
```

---

## 4. Sidebar

```css
.sequoia-left-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 260px;
  padding-left: 8px;
  padding-right: 4px;
  transition: width 0.3s ease-out;
  background-color: #222;
  color: #fff;
  border-right: 1px solid #111;
  box-sizing: border-box;
}

.sequoia-left-container .sequoia-left-content {
  flex: 1;
  overflow-y: auto;
}

/* Sidebar top bar */
.sequoia-left-container .sequoia-left-bar {
  height: 48px;
  line-height: 48px;
}
.sequoia-left-container .sequoia-left-bar > span:nth-child(2) {
  width: 171px;
  color: #eee;
}

/* Collapse arrow */
.sequoia-left-container .sequoia-left-arrow {
  width: 32px;
  height: 32px;
  transform: rotate(0deg);
  transform-origin: center;
  transition: transform 0.3s ease;
  opacity: 0.6;
  margin-right: 8px;
}
.sequoia-left-container .sequoia-left-arrow.hide {
  transform: rotate(180deg);
}
.sequoia-left-container .sequoia-left-arrow:hover {
  background: rgba(0,0,0,.3) url(...) 50% no-repeat;
  border-radius: 2px;
  opacity: 1;
}

/* Menu items */
.sequoia-left-container .sequoia-left-menu {
  display: flex;
  height: 36px;
  line-height: 36px;
  margin-bottom: 4px;
  border-radius: 2px;
  font-size: 13px;
  opacity: 0.6;
  min-width: 230px;
  cursor: default;
}
.sequoia-left-container .sequoia-left-menu > span:first-child {
  width: 32px;
  height: 36px;
  margin-right: 8px;
  background-position: 50%;
  background-repeat: no-repeat;
  background-size: 24px 24px;
}
.sequoia-left-container .sequoia-left-menu > span:nth-child(2) {
  width: 156px;
  text-transform: uppercase;
  overflow: hidden;
}
.sequoia-left-container .sequoia-left-menu > span:nth-child(3) {
  width: 38px;
  padding-right: 8px;
  text-align: right;
}
.sequoia-left-container .sequoia-left-menu.cur,
.sequoia-left-container .sequoia-left-menu:hover {
  background: rgba(0,0,0,.3);
  opacity: 1;
}

/* Follow list in sidebar */
.sequoia-left-container.followed .sequoia-left-followlist {
  position: relative;
  height: 0;
  overflow: hidden;
  padding-right: 8px;
  transition: height 0.3s ease-in-out;
}
.sequoia-left-container.followed .sequoia-left-followlist.show {
  height: calc(100% - 50px);
  overflow-y: auto;
}

/* Sidebar scrollbar */
.sequoia-left-content::-webkit-scrollbar-thumb,
.sequoia-left-content::-webkit-scrollbar-track {
  border-radius: 4px;
  width: 8px;
  background: transparent;
}
.sequoia-left-content:hover::-webkit-scrollbar-thumb {
  background: #585858;
}
.sequoia-left-content:hover::-webkit-scrollbar-thumb:hover {
  background: #44d62c;
}
.sequoia-left-content:hover::-webkit-scrollbar-track {
  background: #111;
}

/* Refresh button with animation */
.sequoia-left-container .sequoia-left-reload.loading {
  animation: refreshing 1s linear infinite;
  transform-origin: center;
  opacity: 1;
}
```

---

## 5. Wallpaper Cards (Grid)

### Grid Container

```css
.sequoia-wallpaper-list {
  flex: 1;
  overflow-y: auto;
  padding-left: 16px;
  flex-direction: column;
  padding-bottom: 153px;       /* space for playlist panel */
  transition: padding 0.4s ease-out;
}
.sequoia-wallpaper-list.playlist-hide {
  padding-bottom: 16px;
}

.sequoia-wallpaper-list-con {
  display: flex;
  flex-wrap: wrap;
  overflow-y: auto;
  padding-right: 16px;
  padding-top: 16px;
  margin-left: -16px;
  align-content: flex-start;
}
```

### Individual Card

```css
.sequoia-wallpaper {
  position: relative;
  padding-left: 16px;
  margin-bottom: 24px;
  max-width: 266px;
  min-width: 240px;
  box-sizing: border-box;
  color: #909090;
}

/* Card thumbnail */
.sequoia-wallpaper .sequoia-wallpaper-content {
  position: relative;
  font-size: 0;
}
.sequoia-wallpaper .sequoia-wallpaper-content > img {
  height: auto;
  max-height: 140px;
  min-height: 124px;
  background-size: cover;
  outline: 2px solid transparent;
  outline-offset: -2px;
}
.sequoia-wallpaper .sequoia-wallpaper-content > img,
.sequoia-wallpaper .sequoia-wallpaper-content video {
  width: 100%;
  border-radius: 2px;
  aspect-ratio: 16/9;    /* 1.77777778 */
}

/* Hover: green outline on thumbnail */
.sequoia-wallpaper .sequoia-wallpaper-content:hover .prev-pannel img,
.sequoia-wallpaper .sequoia-wallpaper-content:hover > img,
.sequoia-wallpaper .sequoia-wallpaper-content:hover video {
  outline: 2px solid #44d62c;
  outline-offset: -2px;
}

/* Card title */
.sequoia-wallpaper .sequoia-wallpaper-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 14px;
  font-family: roboto_regular;
  color: #c8c8c8;
  line-height: 16px;
  margin-bottom: 2px;
}

/* Card creator */
.sequoia-wallpaper .sequoia-wallpaper-creator {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  font-family: roboto_medium;
  color: #909090;
  line-height: 14px;
}

/* Card name row (icons + title) */
.sequoia-wallpaper .sequoia-wallpaper-name {
  position: relative;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: flex-start;
  line-height: 32px;
  margin-top: 2px;
  font-size: 14px;
  color: #c8c8c8;
}

/* Hover: name turns white */
.sequoia-wallpaper:hover .sequoia-wallpaper-name > div:first-child {
  color: #fff;
}
/* Hover: downloading name stays green */
.sequoia-wallpaper:hover .sequoia-wallpaper-name > div:first-child.wallpaper-name-downloading {
  color: #44d62c;
}
/* Hover: pending name stays orange */
.sequoia-wallpaper:hover .sequoia-wallpaper-name > div:first-child.wallpaper-name-pending {
  color: #ffb94f;
}
/* Hover: error name stays red */
.sequoia-wallpaper:hover .sequoia-wallpaper-name > div:first-child.wallpaper-name-err {
  color: #e72424;
}

/* Preview panel fade-in on hover */
.sequoia-wallpaper .prev-pannel {
  position: absolute;
  opacity: 0;
  transition: opacity 0.4s linear;
  left: 0;
  top: 0;
  width: 100%;
}
.sequoia-wallpaper:hover .prev-pannel {
  opacity: 1;
}

/* Type icons (Dynamic, Static, Interactive, etc.) */
.sequoia-wallpaper .sequoia-wallpaper-name .sequoia-wallpaper-icon {
  background-size: 16px 16px;
  flex-shrink: 0;
  line-height: 32px;
  height: 32px;
  width: 32px;
  opacity: 0.75;
}
/* Icon hover pattern: rgba(0,0,0,.3) overlay */

/* Download progress bar */
.sequoia-wallpaper .download-progress {
  position: absolute;
  width: 100%;
  left: 0;
  top: -6px;
  height: 4px;
  background: #fff;
  border-radius: 0 0 2px 2px;
}
.sequoia-wallpaper .download-progress > div {
  border-radius: 0 2px 2px 2px;
  height: 4px;
  background: #44d62c;
}
.sequoia-wallpaper .download-progress.paused > div {
  background: #ffb94f;
}
.sequoia-wallpaper .download-progress.downloadErr > div {
  background: #e72424;
}

/* "New" badge on card */
.sequoia-wallpaper .wallpaper-new {
  position: absolute;
  width: 42px;
  height: 20px;
  left: -4px;
  top: 8px;
  background: #44d62c;
  color: #000;
  text-align: center;
  line-height: 20px;
  font-size: 12px;
}
.sequoia-wallpaper .wallpaper-new:hover {
  background-color: #78e166;
}

/* Silver price */
.sequoia-wallpaper .sequoia-wallpaper-silver {
  display: flex;
  color: #fff;
  padding-left: 21px;
  background-size: 16px 16px;
  line-height: 20px;
  height: 20px;
  font-size: 14px;
  margin-top: 6px;
}
```

---

## 6. Wallpaper Detail (Side Panel)

The detail view appears inside a `right-madal-mask` slide-in panel (400px) or inside a `sequoia-wallpaper-newmodal` modal.

```css
/* In new modal context */
.sequoia-wallpaper-newmodal .sequoia-wallpaper-detail {
  display: flex;
  flex-direction: row;
  flex-shrink: 0;
  height: 100%;
  position: relative;
}

/* Preview image */
.sequoia-wallpaper-detail .sequoia-wallpaper-preview img {
  width: 100%;
  max-height: 250px;
  margin-bottom: 4px;
}

/* Detail name */
.sequoia-wallpaper-detail .sequoia-wallpaper-name {
  position: relative;
  display: flex;
  flex-direction: row;
  line-height: 24px;
  height: 32px;
  font-size: 14px;
  justify-content: space-between;
  align-items: flex-start;
}
.sequoia-wallpaper-detail .sequoia-wallpaper-name > div:first-child {
  color: #44d62c;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  line-height: 32px;
}

/* Description + Copyright */
.sequoia-wallpaper-detail .sequoia-wallpaper-copyright,
.sequoia-wallpaper-detail .sequoia-wallpaper-desc {
  white-space: nowrap;
  font-size: 12px;
  color: #909090;
  height: 18px;
  overflow: hidden;
}
.sequoia-wallpaper-detail .sequoia-wallpaper-desc a {
  color: #44d62c;
}
.sequoia-wallpaper-detail .sequoia-wallpaper-desc a:hover {
  color: #7ce26b;
}

/* Creator info */
.sequoia-wallpaper-detail .wallpaper-info-creator {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 270px;
  height: 24px;
  color: #fff;
}
/* Marquee animation for long creator names */
.sequoia-wallpaper-detail .wallpaper-info-creator > div span {
  animation: marquee 3s linear 3s infinite alternate both;
}

/* Info two-column layout */
.sequoia-wallpaper-detail .sequoia-wallpaper-info {
  display: flex;
  flex-direction: row;
  margin-bottom: 8px;
}
.sequoia-wallpaper-detail .sequoia-wallpaper-info > div:first-child {
  color: #767676;
  margin-right: 24px;
}
.sequoia-wallpaper-detail .sequoia-wallpaper-info > div:last-child {
  color: #fff;
}
.sequoia-wallpaper-detail .sequoia-wallpaper-info > div > div {
  line-height: 24px;
  margin-bottom: 8px;
}

/* Tags */
.sequoia-wallpaper-detail .sequoia-wallpaper-tag {
  display: inline-block;
  padding: 4px 16px;
  color: #909090;
  border: 1px solid #909090;
  margin-right: 16px;
  margin-bottom: 8px;
  border-radius: 4px;
  line-height: 14px;
  background: #000;
}
.sequoia-wallpaper-detail .sequoia-wallpaper-tag.spe {
  color: #44d62c;
  border-color: #44d62c;
}

/* Action bar (like/wish/share/export/add-to-playlist) */
.sequoia-wallpaper-detail .sequoia-wallpaper-like {
  position: relative;
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  height: 32px;
  z-index: 1;
  margin-top: 6px;
}

/* Action icon pattern: 32x32, opacity .5-.7, hover -> opacity 1 + rgba(0,0,0,.3) bg */
.sequoia-wallpaper-detail .sequoia-wallpaper-wish {
  width: 32px; height: 32px;
  border-radius: 2px;
  margin-right: 24px;
  opacity: .5;
}
.sequoia-wallpaper-detail .sequoia-wallpaper-wish:hover {
  opacity: 1;
  background: #000 url(...) no-repeat 50%;
}
```

---

## 7. Playlist Bar (Bottom Panel)

```css
.sequoia-playlist-panel {
  position: fixed;
  box-sizing: border-box;
  bottom: 0;
  left: 0;
  width: calc(100% - 8px);
  transition: left 0.3s ease-out;
  z-index: 1000;
}

.sequoia-playlist {
  height: 153px;
  border-radius: 2px;
  overflow: hidden;
  transition: height 0.3s ease-in;
}
.sequoia-playlist.hide {
  height: 34px;              /* collapsed state */
}

/* Top bar of playlist */
.sequoia-playlist .sequoia-playlist-bar {
  height: 32px;
  border: 1px solid #000;
  border-bottom: none;
  display: inline-block;
  color: #909090;
  white-space: nowrap;
  background: #222;
  border-radius: 2px 2px 2px 0;
}

/* Thumbnail area */
.sequoia-playlist .sequoia-playlist-con {
  box-sizing: border-box;
  height: 120px;
  display: flex;
  flex-direction: row;
  padding: 8px 8px 6px 0;
  border: 1px solid #000;
  background: #1a1a1a;
  border-radius: 0 2px 2px 2px;
}

/* Scrollable thumbnail list */
.sequoia-playlist .sequoia-playlist-scroll {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  height: 110px;
}

/* Individual thumbnail */
.sequoia-playlist .sequoia-playlist-paper {
  position: absolute;
  width: 104px;
  height: 104px;
  background: #ccc;
  background-position: 50%;
  background-size: cover;
}

/* Current wallpaper indicator */
.sequoia-playlist .sequoia-playlist-cur-mask {
  position: absolute;
  box-sizing: border-box;
  width: 104px;
  height: 104px;
  border: 2px solid #fff;
  z-index: 10;
  transition: left 0.3s ease-in;
}

/* Drag position indicator */
.sequoia-playlist .sequoia-playlist-dragPos:before,
.sequoia-playlist .sequoia-playlist-dragPos:after {
  border: 2px solid #44d62c;
}

/* Monitor tabs */
.sequoia-playlist .sequoia-playlist-monitor {
  line-height: 32px;
  display: inline-block;
  min-width: 60px;
  margin-left: 8px;
}
.sequoia-playlist .sequoia-playlist-monitor.cur {
  color: #fff;
  border-bottom: 2px solid #44d62c;
}

/* Playlist controls (play/stop/delete/save/mute) - 32x32 icons */
.sequoia-playlist .sequoia-playlist-op {
  display: inline-block;
  width: 32px;
  height: 32px;
  opacity: 0.6;
}
.sequoia-playlist .sequoia-playlist-op:hover {
  opacity: 1;
  background: rgba(0,0,0,.3) url(...) no-repeat 50%;
}
.sequoia-playlist .sequoia-playlist-op.play.disabled {
  opacity: 0.2;
  cursor: not-allowed;
}

/* Playlist info sidebar */
.sequoia-playlist .sequoia-playlist-info {
  height: 104px;
  padding: 0 8px;
  white-space: nowrap;
}
.sequoia-playlist .sequoia-playlist-info > div:first-child {
  color: #44d62c;
  line-height: 24px;
}
.sequoia-playlist .sequoia-playlist-info > div:nth-child(2) {
  color: #909090;
  font-size: 13px;
  line-height: 20px;
}
```

---

## 8. Buttons

```css
.sequoia-button {
  display: inline-block;
  vertical-align: middle;
  height: 32px;
  padding-left: 24px;
  line-height: 32px;
  padding-right: 24px;
  background: #707070;
  color: #fff;
  border-radius: 2px;
  text-transform: uppercase;
  white-space: nowrap;
  cursor: default;
}
.sequoia-button:hover {
  background-color: #9b9b9b;
}
.sequoia-button:active {
  background-color: #4e4e4e;
}
.sequoia-button.small-btn {
  height: 26px;
  line-height: 26px;
}
.sequoia-button.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Primary (green) button */
.sequoia-button.sequoia-primary-button {
  background: #44d62c;
  color: #000;
  font-family: roboto_bold;
  border-color: #44d62c;
  opacity: 1;
}
.sequoia-button.sequoia-primary-button:hover {
  background-color: #7ce26b;
}
.sequoia-button.sequoia-primary-button:active {
  background-color: #30961f;
}
.sequoia-button.sequoia-primary-button.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Delete (red) button */
.sequoia-button.sequoia-delete-button:hover {
  background-color: #ba0404;
}
.sequoia-button.sequoia-delete-button:active {
  background-color: #820303;
}

/* Line (outline) button */
.sequoia-button.sequoia-line-button {
  background-color: transparent;
  line-height: 24px;
  height: 24px;
  border: 1px solid #bdbdbd;
  color: #bdbdbd;
  padding-left: 20px;
  padding-right: 20px;
}
.sequoia-button.sequoia-line-button:hover {
  border-color: #fff;
  color: #fff;
}

/* Text link (green text button) */
.sequoia-text-link {
  padding: 4px 8px;
  color: #44d62c;
  border-radius: 2px;
}
.sequoia-text-link:hover {
  background-color: rgba(0,0,0,.3);
}
.sequoia-text-link.btn-like {
  display: inline-block;
  line-height: 26px;
  padding: 0 16px;
  border-radius: 13px;
  border: 1px solid #44d62c;
  color: #44d62c;
  font-size: 12px;
}
.sequoia-text-link.btn-like:hover {
  color: #7ce26b;
  border-color: #7ce26b;
}
```

---

## 9. Modals (note: `madal` typo in original)

### Center Modal

```css
.sequoia-madal-mask {
  position: fixed;
  width: 100%;
  height: 100%;
  left: 0;
  bottom: 0;
  display: none;
  z-index: 1001;
  background: rgba(0,0,0,.7);
}
.sequoia-madal-mask.show {
  display: block;
}

.sequoia-madal-content {
  position: absolute;
  left: 50%;
  top: 50%;
  margin-left: -436px;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  color: #909090;
  width: 872px;
  height: 560px;
  background: #222;
  box-sizing: border-box;
  border: 1px solid #000;
  box-shadow: -3px 0 6px 0 rgba(0,0,0,.12);
}

.sequoia-madal-close {
  position: absolute;
  top: -32px;
  right: -32px;
  width: 32px;
  height: 32px;
  cursor: pointer;
  opacity: 0.5;
}
.sequoia-madal-close:hover {
  opacity: 0.8;
}

.sequoia-madal-body {
  flex: auto;
  overflow-y: auto;
}
```

### Right Slide-in Modal (Wallpaper Detail Panel)

```css
.right-madal-mask {
  position: fixed;
  width: 400px;
  height: calc(100% - 80px);
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: none;
  cursor: not-allowed;
}
.right-madal-mask.show {
  display: block;
}

.right-madal-container {
  position: absolute;
  right: -100%;
  top: 0;
  height: 100%;
}
.show .right-madal-container {
  animation: rightShow 0.3s ease-in;
  animation-fill-mode: forwards;
}
.hide .right-madal-container {
  animation: rightHide 0.3s ease-in;
  animation-fill-mode: forwards;
}

.right-madal-content {
  display: flex;
  flex-direction: column;
  color: #909090;
  height: 100%;
  background: #1a1a1a;
  width: 400px;
  box-sizing: border-box;
  border: 1px solid #000;
  box-shadow: -3px 0 6px 0 rgba(0,0,0,.12);
}

.right-madal-close {
  position: absolute;
  top: 6px;
  width: 32px;
  height: 32px;
  right: 8px;
  z-index: 1;
  cursor: pointer;
  opacity: 0.6;
}
.right-madal-close:hover {
  opacity: 1;
  background: rgba(0,0,0,.3) url(...) no-repeat 50%;
}

.right-madal-title {
  padding-left: 16px;
  line-height: 46px;
  font-size: 14px;
  font-family: roboto_bold;
  color: #fff;
}

.right-madal-body {
  flex: auto;
  overflow-y: auto;
  padding: 46px 8px 8px 16px;
}
```

### Win Modal (Contest)

```css
.sequoia-win-modal.sequoia-madal-content {
  width: 1064px;
  height: 602px;
  margin-left: -532px;
}
```

### Special Modal

```css
.sequoia-spe-modal.sequoia-madal-mask {
  z-index: 1011;
}
```

### Wallpaper New Modal (Large Detail View)

```css
.sequoia-wallpaper-newmodal.sequoia-madal-content {
  width: 1066px;
  height: 602px;
  margin-left: -533px;
}
.sequoia-wallpaper-newmodal.sequoia-madal-mask {
  background: rgba(0,0,0,.85);
}

/* Close confirm modal */
.sequoia-close-confirm.sequoia-madal-content {
  border-color: #44d62c;
  border-radius: 4px;
  background-color: #000;
}
```

---

## 10. Search

```css
/* Consistent pattern across contexts */
.sequoia-search-input-con {
  position: relative;
  display: inline-block;
  vertical-align: middle;
}

.sequoia-search-input {
  height: 32px;
  box-sizing: border-box;
  background: #161616 url(/* search icon SVG */) no-repeat 0;
  background-position: 8px 9px;
  display: inline-block;
  vertical-align: middle;
  padding-left: 27px;
  width: 169px;
  padding-right: 32px;
  /* inherits input base styles: border, color, etc. */
}
.sequoia-search-input:hover {
  /* search icon changes from #888 to #fff fill */
  background: #161616 url(/* white search icon */) no-repeat 0;
  background-position: 8px 9px;
}
.sequoia-search-input:hover::-webkit-input-placeholder {
  color: #fff;
}
.sequoia-search-input:focus {
  border-color: #44d62c;
}

.sequoia-search-close {
  position: absolute;
  height: 30px;
  width: 30px;
  top: 0;
  right: 0;
  opacity: 0.65;
  /* X icon SVG */
}
```

---

## 11. Settings

```css
.sequoia-setting-content {
  display: flex;
  flex-direction: row;
  cursor: default;
  height: 100%;
}
.sequoia-setting-content > div:first-child {
  border-right: 1px solid #000;
}
.sequoia-setting-content > div:last-child {
  flex: 1;
  overflow-y: auto;
  padding: 12px 28px 0 32px;
  margin: 8px 4px 8px 0;
}

/* Setting title */
.sequoia-setting-content .sequoia-setting-title {
  padding: 30px 0 30px 30px;
  font-size: 16px;
  line-height: 18px;
  color: #fff;
}

/* Setting menu items */
.sequoia-setting-content .sequoia-setting-menu {
  height: 38px;
  line-height: 38px;
  padding-left: 30px;
  color: #bbb;
  min-width: 158px;
}
.sequoia-setting-content .sequoia-setting-menu:hover {
  color: #fff;
  background: #2e2e2e;
}
.sequoia-setting-content .sequoia-setting-menu.cur {
  color: #44d62c;
}

/* About page */
.sequoia-setting-about {
  padding-top: 90px;
  text-align: center;
}
.sequoia-setting-about p {
  line-height: 24px;
  color: #999;
}

/* Performance settings */
.sequoia-setting-performance > div {
  line-height: 32px;
  color: #ccc;
}
.sequoia-setting-performance > div:first-child {
  color: #bbb;
  margin-bottom: 24px;
}

/* Display settings - screen list */
.sequoia-setting-display .sequoia-setting-screenlist {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  margin: 16px 0;
  padding-top: 32px;
}
.sequoia-setting-display .sequoia-setting-screenlist > div {
  width: 160px;
  border: 1px solid #909090;
  height: 90px;
  position: relative;
  background-size: cover;
}
.sequoia-setting-display .sequoia-setting-screenlist > div.checked {
  border-color: #44d62c;
}

/* General settings */
.sequoia-setting-general {
  color: #bbb;
}
.sequoia-setting-general > div {
  line-height: 32px;
  margin-bottom: 22px;
}

/* Slider control for general settings */
.sequoia-setting-general .control-wrap .control-wrap-val {
  position: absolute;
  color: #000;
  top: -26px;
  line-height: 20px;
  width: 28px;
  text-align: center;
  background: #44d62c;
  margin-left: -14px;
  font-size: 12px;
  border-radius: 2px;
}

/* Social buttons on about page */
.sequoia-setting-about .setting-social-btn.razer {
  background-color: #44d62c;
  color: #000;
  border-color: #30961f;
}
.sequoia-setting-about .setting-social-btn.razer:hover {
  background-color: #6ade57;
}
```

---

## 12. Discover Cards (Featured/Banner Grid)

```css
.discover-cards .discover-cards-info {
  box-sizing: border-box;
  background: #222;
  border-radius: 0 0 2px 2px;
  padding: 12px;
  text-align: left;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.discover-cards .cards-info-title {
  width: 220px;
  font-size: 24px;
  line-height: 23px;
  text-transform: uppercase;
  color: #44d62c;
  font-family: razerf5_bold;
  margin-bottom: 12px;
  max-height: 69px;
  overflow: hidden;
}

.discover-cards .cards-info-author {
  font-size: 13px;
  color: #909090;
}
.discover-cards .cards-info-author img {
  width: 24px;
  height: 24px;
  border-radius: 100%;
  margin-right: 8px;
}

.discover-cards .cards-info-desc {
  font-size: 14px;
  line-height: 16px;
  margin-top: 8px;
  color: #fff;
  max-height: 48px;
  overflow: hidden;
}
```

---

## 13. Form Controls

### Checkbox

```css
.sequoia-checkbox {
  display: flex;
  align-items: center;
  line-height: 32px;
  height: 32px;
  color: #ccc;
  cursor: default;
  border-radius: 2px;
  font-size: 12px;
}
.sequoia-checkbox > span:first-child {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 1px solid #555;
  background: #1a1a1a;
  margin-right: 8px;
}
.sequoia-checkbox.checked > span:first-child {
  background: #44d62c url(/* checkmark SVG */) no-repeat 50%;
  border-color: #44d62c;
}
.sequoia-checkbox:hover > span:first-child {
  border-color: #44d62c;
}
.sequoia-checkbox.disabled {
  opacity: 0.8;
  cursor: not-allowed;
}
```

### Radio

```css
.sequoia-radio {
  display: inline-block;
  color: #bbb;
  cursor: default;
  font-size: 12px;
}
.sequoia-radio > span:first-child {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 100%;
  border: 1px solid #555;
  background: #1a1a1a;
  margin-right: 8px;
}
.sequoia-radio.checked > span:first-child {
  background: #44d62c url(/* checkmark SVG */) no-repeat 50%;
  border: 1px solid #44d62c;
}
.sequoia-radio:hover > span:first-child {
  border: 1px solid #44d62c;
}
```

### Switch (Toggle)

```css
.sequoia-switch {
  display: inline-block;
  cursor: default;
  width: 32px;
  height: 32px;
  position: relative;
}
.sequoia-switch:before {           /* track */
  position: absolute;
  content: "";
  width: 28px;
  height: 16px;
  background-color: #787878;
  left: 2px;
  top: 8px;
  border-radius: 8px;
  transition: background 0.2s linear;
}
.sequoia-switch:hover:before {
  outline: 1px solid #44d62c;
}
.sequoia-switch:after {            /* thumb */
  position: absolute;
  content: "";
  width: 12px;
  height: 12px;
  background: #000;
  left: 4px;
  top: 10px;
  border-radius: 6px;
  transition: left 0.2s linear;
}
.sequoia-switch.open:before {
  background-color: #44d62c;
}
.sequoia-switch.open:after {
  left: 16px;
}
```

### Slider

```css
.sequoia-slider {
  position: relative;
  width: 100%;
  height: 12px;
  padding: 5px 0;
  border-radius: 2px;
  touch-action: none;
}
.sequoia-slider .rc-slider-rail {
  position: absolute;
  width: 100%;
  height: 2px;
  background-color: #226916;
  border-radius: 2px;
}
.sequoia-slider .rc-slider-track {
  position: absolute;
  height: 2px;
  background-color: #44d62c;
  border-radius: 2px;
}
.sequoia-slider .rc-slider-handle {
  position: absolute;
  width: 10px;
  height: 10px;
  margin-top: -4px;
  background-color: #222;
  border: 2px solid #44d62c;
  border-radius: 50%;
  cursor: default;
}
.sequoia-slider .rc-slider-handle:focus {
  outline: none;
  box-shadow: none;
}
.sequoia-slider .rc-slider-handle-dragging,
.sequoia-slider .rc-slider-handle:focus-visible {
  margin-top: -5px;
  width: 12px;
  height: 12px;
}
```

### Select (Dropdown)

```css
.sequoia-select-rel {
  display: inline-flex;
  height: 32px;
  min-width: 160px;
  background: #161616;
  border: 1px solid #000;
  border-radius: 2px;
  padding-left: 8px;
  padding-right: 8px;
  box-sizing: border-box;
  line-height: 30px;
  color: #bbb;
}
.sequoia-select-rel.open,
.sequoia-select-rel:hover {
  border-color: #44d62c;
}
.sequoia-select-rel .icon {
  margin-right: 0;
  margin-left: auto;
  opacity: 0.5;
  transition: transform 0.2s ease-out;
}
.sequoia-select-rel.open .icon {
  transform: rotate(180deg);
}

.sequoia-select-drop {
  background-color: #222;
  border: 1px solid #000;
  border-radius: 2px;
  padding: 8px 0;
}
.sequoia-select-drop .sequoia-select-item {
  height: 32px;
  padding: 0 8px;
  color: #bbb;
  line-height: 32px;
}
.sequoia-select-drop .sequoia-select-item:hover {
  background-color: #282828;
}
.sequoia-select-drop .sequoia-select-item.selected {
  color: #44d62c;
}
```

### Input

```css
.sequoia-input input {
  height: 32px;
  padding-left: 8px;
  padding-right: 8px;
  color: #bbb;
  border-radius: 4px;
  width: 100%;
  box-sizing: border-box;
}
```

---

## 14. Additional Components

### Dropdown

```css
.sequoia-dropdown {
  position: relative;
  display: inline-block;
  vertical-align: middle;
  height: 32px;
}
.sequoia-dropdown.show {
  background: #000;
}
.sequoia-dropdown .sequoia-dropdown-content {
  position: absolute;
  display: none;
  box-sizing: border-box;
  padding: 8px 16px;
  left: 0;
  top: 100%;
  background: #222;
  border: 1px solid #000;
  z-index: 1001;
  border-radius: 2px;
}
.sequoia-dropdown .sequoia-dropdown-content.show {
  display: block;
}
```

### Context Menu

```css
.sequoia-contex-menu {
  position: fixed;
  padding: 8px 0;
  border-radius: 4px;
  background: #000;
  min-width: 200px;
  border: 1px solid #555;
  z-index: 1001;
}
.sequoia-contex-menu .sequoia-contex-menu-item {
  line-height: 30px;
  color: #ccc;
  padding: 0 8px 0 16px;
  margin: 0 8px;
  border-radius: 15px;
  cursor: default;
}
.sequoia-contex-menu .sequoia-contex-menu-item:hover {
  color: #fff;
  background: #191919;
}
.sequoia-contex-menu .sequoia-contex-menu-item.disabled {
  color: #666;
  cursor: not-allowed;
}
.sequoia-contex-menu .sequoia-contex-menu-separate {
  background: #666;
  height: 1px;
  margin: 8px;
}
```

### Pagination

```css
.sequoia-pagination {
  height: 32px;
  text-align: right;
  line-height: 32px;
}
.sequoia-pagination > span {
  display: inline-block;
  margin-left: 4px;
  width: 32px;
  height: 32px;
  line-height: 32px;
  color: #909090;
  text-align: center;
}
.sequoia-pagination > span:hover {
  background: rgba(0,0,0,.3);
}
.sequoia-pagination > span.cur {
  color: #fff;
}
.sequoia-pagination > span.disabled {
  opacity: 0.5;
}
```

### Go To Top Button

```css
.sequoia-go-top {
  position: fixed;
  right: 24px;
  bottom: 152px;
  width: 60px;
  height: 50px;
  background: #44d62c url(/* chevron-up SVG */) no-repeat 50%;
  opacity: 0.7;
}
.sequoia-go-top:hover {
  opacity: 1;
}
```

---

## 15. Animations / Transitions

### @keyframes

```css
@keyframes refreshing {
  0%   { transform: rotate(0deg); }
  100% { transform: rotate(180deg); }
}

@keyframes marquee {
  0%   { transform: translateX(0); }
  100% { transform: translateX(-100%); }
}

@keyframes blinkVote {
  0%   { opacity: 0; }
  15%  { opacity: 1; }
  55%  { opacity: 1; }
  65%  { opacity: 0; }
  100% { opacity: 0; }
}

@keyframes showCompare {
  0%   { opacity: 0.3; }
  100% { opacity: 1; }
}

@keyframes processErr {
  0%   { left: 0; }
  50%  { left: 50%; }
  100% { left: 100%; }
}

@keyframes buttonFade {
  0%   { color: #000; }
  10%  { color: #000; }
  20%  { color: transparent; }
  75%  { color: transparent; }
  85%  { color: transparent; }
  100% { color: #000; }
}

@keyframes buttonFade2 {
  0%   { opacity: 0; }
  10%  { opacity: 0; }
  20%  { opacity: 1; }
  75%  { opacity: 1; }
  85%  { opacity: 1; }
  100% { opacity: 0; }
}

@keyframes rightShow {
  0%   { right: -100%; }
  100% { right: 0; }
}

@keyframes rightHide {
  0%   { right: 0; }
  100% { right: -100%; }
}

@keyframes refreshAnim {
  0%   { transform: rotate(0deg); }
  100% { transform: rotate(180deg); }
}

@keyframes scrollAnim {
  0%   { transform: translateX(0); }
  100% { transform: translateX(100%); }
}

@keyframes rotate-rainbow {
  0%   { transform: rotate(0deg); }
  100% { transform: rotate(1turn); }
}
```

### Common Transitions

```css
/* Sidebar width */
transition: width 0.3s ease-out;

/* Sidebar collapse arrow rotation */
transition: transform 0.3s ease;

/* Sidebar follow list height */
transition: height 0.3s ease-in-out;

/* Playlist panel position */
transition: left 0.3s ease-out;

/* Playlist height collapse */
transition: height 0.3s ease-in;

/* Playlist current thumbnail */
transition: left 0.3s ease-in;

/* Wallpaper preview fade-in */
transition: opacity 0.4s linear;

/* Switch track color */
transition: background 0.2s linear;

/* Switch thumb position */
transition: left 0.2s linear;

/* Select icon rotation */
transition: transform 0.2s ease-out;

/* Wallpaper list padding (playlist show/hide) */
transition: padding 0.4s ease-out;
```

---

## GTK4/Adwaita Mapping Notes

| Axon Component | GTK4 Equivalent |
|---|---|
| `.sequoia-container` | `GtkBox` (vertical) |
| `.sequoia-main` | `GtkBox` (horizontal) |
| `.sequoia-left-container` | `GtkStackSidebar` or custom `GtkBox` |
| `.sequoia-left-menu` | `GtkListBoxRow` |
| `.sequoia-wallpaper-list-con` | `GtkFlowBox` (wrapping grid) |
| `.sequoia-wallpaper` | `GtkFlowBoxChild` with custom card widget |
| `.sequoia-button` | `GtkButton` with CSS classes |
| `.sequoia-primary-button` | `GtkButton.suggested-action` |
| `.sequoia-delete-button` | `GtkButton.destructive-action` |
| `.sequoia-line-button` | `GtkButton.flat` with border |
| `.sequoia-checkbox` | `GtkCheckButton` |
| `.sequoia-radio` | `GtkCheckButton` (in radio mode) |
| `.sequoia-switch` | `GtkSwitch` |
| `.sequoia-slider` | `GtkScale` |
| `.sequoia-select-rel` | `GtkDropDown` |
| `.sequoia-madal-mask` | `GtkDialog` / `AdwDialog` |
| `.right-madal-mask` | `AdwFlap` or `GtkRevealer` (slide-in) |
| `.sequoia-dropdown` | `GtkPopover` |
| `.sequoia-contex-menu` | `GtkPopoverMenu` |
| `.sequoia-playlist-panel` | `GtkRevealer` at bottom |
| `.sequoia-pagination` | Custom widget with `GtkButton` row |
| `.sequoia-search-input` | `GtkSearchEntry` |
| `.sequoia-nav-bar` | `AdwHeaderBar` or `GtkHeaderBar` |
| `.sequoia-setting-content` | `AdwPreferencesPage` / `AdwPreferencesGroup` |

### Key Design Tokens for GTK CSS

```css
/* Rexon GTK4 theme variables (derived from Axon) */
@define-color accent_bg_color #44d62c;
@define-color accent_fg_color #000;
@define-color accent_color #44d62c;
@define-color accent_hover #7ce26b;
@define-color accent_active #30961f;

@define-color window_bg_color #1a1a1a;
@define-color view_bg_color #1a1a1a;
@define-color headerbar_bg_color #222;
@define-color sidebar_bg_color #222;
@define-color card_bg_color #222;

@define-color dialog_bg_color #222;
@define-color popover_bg_color #000;

@define-color window_fg_color #fff;
@define-color view_fg_color #ccc;
@define-color dim_label_color #909090;
@define-color insensitive_fg_color #666;

@define-color borders #000;
@define-color unfocused_borders #555;

@define-color error_color #e72424;
@define-color error_bg_color #ba0404;
@define-color warning_color #ffb94f;
@define-color success_color #44d62c;

@define-color scrollbar_color #585858;
@define-color slider_track_color #226916;

@define-color entry_bg #111;
@define-color entry_border #0c0c0c;
```
