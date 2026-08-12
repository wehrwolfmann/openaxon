# Дефекты Wine — кандидаты в апстрим, разбор по каждому

Замеры сделаны 2026-08-12 на **wine-11.15** (ванильный, пакет `wine 11.15-1.1`,
без staging, без DXVK) в отдельном чистом префиксе `~/.wine-axon-bugs`.
Свежесть апстрима проверена по `master` на gitlab.winehq.org, наличие дубликатов —
по Bugzilla REST (`https://bugs.winehq.org/rest/bug?quicksearch=…`).

Готовые к вставке тексты лежат в `~/Загрузки/Rexon-исследования/wine-axon/`,
воспроизведения — в подпапке `repro/` там же.

Правила: правки для Windows-программ подаются **в Wine, не в Proton**; репорт без
собственного замера не подаётся.

## Сводка

| Кандидат | Вердикт | Куда |
|---|---|---|
| `DCompositionCreateDevice` → `E_NOTIMPL` (WebView2) | **дубликат** bug 58921 + bug 55432 | комментарий + вложение в оба |
| `riched20`: `\ctint`/`\cshade` в `\colortbl` | **подтверждён, дубликата нет** | новый баг, Product Wine / Component richedit |
| `shell32`: `IShellLinkW::QueryInterface` → `E_NOINTERFACE` | **отпал** — поведение верное | максимум однострочный патч ERR→WARN |
| `riched20`: `ReadStyleSheet skipping optional destination` | **отложен** — видимой поломки не измерено | — |
| `combase`: нет WinRT-класса телеметрии | **отпал** — вреда нет, класс не нужен | — |
| Стабы (`WerRegisterCustomMetadata`, `clusapi`, `DecryptFileW`, …) | **отпали** — шум `fixme` | — |
| `wineserver -w` и резидентный `MicrosoftEdgeUpdate.exe` | **не дефект Wine** | заметка в winetricks / AppDB |

---

## 1. DirectComposition / WebView2 — дубликат, но комментарий ценный

Самый весомый кандидат оказался уже заведён, причём дважды:

* **bug 58921** «WebView2 does not work with Windows version setting 8.1 or newer»
  (UNCONFIRMED, заведён 2025-11-04, к нему приклеены дубликаты 59370 и 59431).
  В нулевом комментарии — тот же обход, что нашли мы: per-app `Version=win8`
  для `msedgewebview2.exe`.
* **bug 55432** «PlanetSide 2 launcher is completely white (needs
  dcomp.dll.DCompositionCreateDevice implementation)» (NEW с 2023-08, компонент `dcomp`).

**В апстриме не починено.** `dlls/dcomp/device.c` в master — 47 строк: все три точки
входа печатают FIXME и возвращают `E_NOTIMPL`; в `dcomp.spec` реализованы только они,
остальные 14 экспортов — `stub`. В wine-staging есть отдельный патчсет
`dcomp-DCompositionCreateDevice2` (он же дал регрессию — bug 59918), в апстриме идёт
MR 10567; ванильный Wine остаётся стабом.

Замер на 11.15 своим воспроизведением `repro/dcomp_min.c` (~90 строк, никакого
WebView2 и Razer не нужно — программа делает ровно тот вызов, что делает Chromium
при заявленной Windows ≥ 8.1):

```
reported Windows version: 10.0 build 19045
D3D11CreateDevice hr=0x00000000 feature_level=0xb000
QI IDXGIDevice hr=0x00000000
DCompositionCreateDevice(IDCompositionDevice)         hr=0x80004001
DCompositionCreateDevice2(IDCompositionDevice2)       hr=0x80004001
DCompositionCreateDevice3(IDCompositionDesktopDevice) hr=0x80004001
```

D3D11-устройство и его `IDXGIDevice` создаются нормально — падает только создание
DirectComposition-устройства. Это и есть та единственная точка, из-за которой
viz-процесс Chromium бьёт CHECK и кадр не доходит до окна.

Ценность нашего вклада: подтверждение на 11.15, третье затронутое приложение
(Razer Axon 2.9.1.0 — весь интерфейс на WebView2, рантайм 151.0.4129.78), и главное —
воспроизведение без 120-мегабайтного установщика, без Steam и без DXVK (прошлые
замеры в 55432 были с DXVK, за что репортёра отчитали).

Текст двух комментариев: `02-dcomp-webview2-ДУБЛИКАТ-комментарии.md`.

---

## 2. `riched20`: `\ctint`/`\cshade` разваливают таблицу цветов — НОВЫЙ БАГ

Это единственный кандидат, который идёт наверх как самостоятельный баг.

Причина найдена в `dlls/riched20/reader.c`. Таблица ключевых слов знает ровно три
слова таблицы цветов:

```c
{ rtfColorName, rtfRed,   "red",   0 },
{ rtfColorName, rtfGreen, "green", 0 },
{ rtfColorName, rtfBlue,  "blue",  0 },
```

`\ctint`, `\cshade` и слова тем оформления (`\cmaindarkone`, `\caccentone` …) —
законные по спецификации RTF внутри `\colortbl` — не опознаются. `ReadColorTbl()`
на них обрывает запись, печатает `err:richedit:ReadColorTbl malformed entry` и
начинает **новую** запись цвета со следующего токена. Одна исходная запись
превращается в три, все последующие `\cfN` уезжают по индексу, а поддельные записи
создаются со значением «цвет по умолчанию», из-за чего текст получает `CFE_AUTOCOLOR`
вместо своего цвета.

Замер (`repro/riched_colortbl.c` — три документа, по спецификации одинаковых,
читаем `EM_GETCHARFORMAT` после `EM_STREAMIN`):

```
expected for every line: crTextColor=0x0000ff (R=255 G=0 B=0)

A plain colortbl      crTextColor=0x0000ff (R=255 G=0 B=0)
B \ctint\cshade       crTextColor=0x007fff (R=255 G=127 B=0)  [CFE_AUTOCOLOR]
C Word theme colour   crTextColor=0x007fff (R=255 G=127 B=0)  [CFE_AUTOCOLOR]
```

Это не экзотика: так пишет Word 2007 и новее для любого документа с цветами темы,
и именно такой RTF кладут в лицензию установщики на Inno Setup — отсюда наши
шесть `malformed entry` при показе лицензии Razer.

Дубликата нет. Ближайшие соседи: **bug 20482** (2009, компонент richedit) — там тот же
`ReadColorTbl malformed entry`, но заведён на симптом конкретной программы
(«слишком высокий диалог Tunnelier») и причина за 17 лет не разобрана; **bug 44966** —
про `ReadStyleSheet`, другое место. Наш репорт даёт причину, минимальный пример и
готовый юнит-тест.

Текст: `01-riched20-colortbl-ctint-cshade.md`.

---

## 3. `shell32`: `IShellLinkW::QueryInterface` → `E_NOINTERFACE` — отпал

Прогон `RazerAxon.exe` с `WINEDEBUG=+shell` в своём префиксе показал, какие именно
IID запрашиваются и остаются без ответа:

| IID | Что это |
|---|---|
| `{ecc8691b-c1db-4dc0-855e-65f6c551af49}` | `INoMarshal` |
| `{94ea2b94-e9cc-49e0-c0ff-ee64ca8f5b90}` | `IAgileObject` |
| `{00000003-0000-0000-c000-000000000046}` | `IMarshal` |
| `{5c13e51c-4f32-4726-a3fd-f3edd63da3a0}` | недокументированный интерфейс, который среда COM опрашивает сразу после `CoCreateInstance` |

Все четыре — стандартные «прощупывания» среды COM сразу после создания объекта,
и `E_NOINTERFACE` на них — **правильный** ответ: объект ярлыка не является agile и
маршалится стандартным способом. Дефекта поведения нет; сразу после этих четырёх
запросов `IShellLinkW` и `IPersistFile` отдаются нормально, и `SetPath` отрабатывает.

Остаётся косметика: Wine печатает неудачный `QueryInterface` уровнем `ERR`
(`dlls/shell32/shelllink.c`, конец `IShellLinkW_fnQueryInterface`), хотя по общей
практике Wine неудачный QI — это `WARN`/`TRACE`. Из-за этого в логе любой программы
висят четыре красные строки на ровном месте. Годится как однострочный патч в MR,
но не как баг-репорт — репорт про уровень логирования закроют.

---

## 4. `riched20`: `ReadStyleSheet skipping optional destination` — отложен

Сообщение печатается, когда запись таблицы стилей начинается с `\*` (`{\*\cs10 …}`) —
Wine пропускает такую запись целиком. Bug 44966 (REOPENED, richedit) уже висит на
этом же месте. Видимой поломки на нашем сценарии измерить не удалось: текст лицензии
показывается, стили в реализации Wine почти не используются. Без измеренного
пользовательского симптома не подаём — иначе получится второй 44966.

---

## 5. `combase`: нет WinRT-класса телеметрии — отпал

`RoGetActivationFactory` не находит
`Windows.System.Diagnostics.Telemetry.PlatformTelemetryClient` (запрашивает Edge
Update изнутри). Класс телеметрии Microsoft — реализовывать его в Wine незачем,
отказ и есть правильное поведение, установка от этого не страдает. Подавать нечего.
Похожие «нет WinRT-класса» баги в Bugzilla есть (например 56914 про
`Windows.Data.Json.JsonObject`), но там класс реально нужен приложению.

## 6. Стабы по дороге — отпали

`WerRegisterCustomMetadata`, `clusapi:ClusterEnum`, `advapi:DecryptFileW`,
`nls:get_dummy_preferred_ui_language`, `msi:internal_ui_handler` — все `fixme`,
ни один ничего не сломал. Это штатные метки незавершённых мест, а не дефекты;
репорт «видел fixme» закроют.

## 7. `wineserver -w` и резидентный `MicrosoftEdgeUpdate.exe` — не в Wine

Установка WebView2 оставляет в префиксе вечный `MicrosoftEdgeUpdate.exe /c`, после
чего любой verb winetricks встаёт на `wineserver -w` (замер: процесс жив 1010 с,
снятие ровно этого PID разблокировало установку немедленно). Wine ведёт себя
правильно — он честно ждёт последний процесс префикса. Место для правки — winetricks
(снимать резидент Edge Update перед `wineserver -w`) и/или строка в AppDB.

---

## Что осталось от человека

1. Завести **один** новый баг: Product `Wine`, Component `richedit`, Version `11.15`,
   заголовок и тело — из `01-riched20-colortbl-ctint-cshade.md`, вложить
   `repro/riched_colortbl.c` и `repro/riched_colortbl.out`.
2. Вставить два комментария из `02-dcomp-webview2-ДУБЛИКАТ-комментарии.md`
   в bug 58921 и bug 55432, к обоим приложить `repro/dcomp_min.c`.
3. По желанию — однострочный патч уровня логирования в `shell32/shelllink.c`
   отдельным MR.
