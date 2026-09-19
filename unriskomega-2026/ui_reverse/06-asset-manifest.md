# URO Advisor Pro — Asset Manifest

> All visual assets needed, where they come from, and how to use them.

---

## 1. Logos (from `../assets/logos/`)

| File | Format | Size | Usage | Notes |
|------|--------|------|-------|-------|
| `uro-dark.svg` | SVG | 8.9 KB | **Header bar (blue bg).** Wordmark `#F4F2EF` off-white + ring mark `#FF6B00`/`#FFA463` | **Primary logo for the mock.** Copy to `public/logos/uro-dark.svg` |
| `uro-light.svg` | SVG | 8.9 KB | Light/white backgrounds only. Wordmark `#12100E` near-black + same orange mark | Backup variant — do NOT put on the blue header |
| `partners-light.png` | PNG | 58.3 KB | Title slide / partner section | Not needed for the 3 core screens |
| `partners-dark.png` | PNG | 74.3 KB | Dark bg variant | Not needed |
| `swiss-ai-weeks-light.png` | PNG | 21.0 KB | Title slide | Not needed |
| `swiss-ai-weeks-dark.png` | PNG | 20.9 KB | Dark variant | Not needed |
| `start-hack-tour-light.png` | PNG | 20.7 KB | Title slide | Not needed |
| `start-hack-tour-dark.png` | PNG | 21.7 KB | Dark variant | Not needed |

### How to use the URO logo
```tsx
// In Header.tsx (blue bar) — dark variant = off-white wordmark
<img src="/logos/uro-dark.svg" alt="UNRISKOMEGA" height="28" />
```
The logo = circular ring mark (orange `#FF6B00` + peach `#FFA463` segments) + "UNRISKOMEGA" wordmark.
On the blue header bar use `uro-dark.svg` (off-white `#F4F2EF` wordmark). `uro-light.svg` has a near-black
wordmark (`#12100E`) and is only for light backgrounds.

---

## 2. Icons (from `lucide-react`)

Install: `npm install lucide-react`

| Icon Name | Import | Used In | Size |
|-----------|--------|---------|------|
| `Search` | `import { Search } from "lucide-react"` | Header, table toolbars | 16px |
| `User` | `import { User } from "lucide-react"` | Header user area, portfolio cards | 16px |
| `ChevronDown` | `import { ChevronDown } from "lucide-react"` | User dropdown, sort indicators | 12px |
| `Menu` | `import { Menu } from "lucide-react"` | Far right of secondary nav | 18px |
| `Briefcase` | `import { Briefcase } from "lucide-react"` | Beratermappe nav item | 14px |
| `CircleUser` | `import { CircleUser } from "lucide-react"` | Kundenliste (S1) + Kundeninformation nav items | 14px |
| `Ban` | `import { Ban } from "lucide-react"` | Regelverletzungen nav item (circle with bar) | 14px |
| `AlertTriangle` | `import { AlertTriangle } from "lucide-react"` | Warnungen nav item | 14px |
| `Pencil` | `import { Pencil } from "lucide-react"` | Beratung table toolbar (blue button) | 14px |
| `Trash2` | `import { Trash2 } from "lucide-react"` | Beratung table row delete | 14px |
| `Settings` | `import { Settings } from "lucide-react"` | SAA section header | 16px |
| `Maximize2` | `import { Maximize2 } from "lucide-react"` | SAA section fullscreen | 16px |
| `ChevronRight` | `import { ChevronRight } from "lucide-react"` | Card carousel next button | 20px |
| `ChevronLeft` | `import { ChevronLeft } from "lucide-react"` | Card carousel prev (if needed) | 20px |
| `Plus` | `import { Plus } from "lucide-react"` | Add new filter tab button | 14px |
| `Globe` | `import { Globe } from "lucide-react"` | Länder widget | 24px |
| `BarChart3` | `import { BarChart3 } from "lucide-react"` | Szenarien, Fälligkeiten widgets | 24px |
| `TrendingUp` | `import { TrendingUp } from "lucide-react"` | Zielerreichung widget | 24px |
| `Grid3x3` | `import { Grid3x3 } from "lucide-react"` | Positionsliste widget | 24px |
| `Phone` | `import { Phone } from "lucide-react"` | Telefonberatung nav item | 14px |
| `StickyNote` | `import { StickyNote } from "lucide-react"` | Notizen nav item | 14px |
| `PieChart` | `import { PieChart } from "lucide-react"` | Vermögen (S2) + Analyse (S3) nav items | 14px |
| `Info` | `import { Info } from "lucide-react"` | Portfolio nav item (S3) | 14px |
| `ArrowLeft` | `import { ArrowLeft } from "lucide-react"` | Back arrow in nav (screens 2, 3) | 16px |
| `Landmark` | `import { Landmark } from "lucide-react"` | External portfolio card icon (ZKB) | 16px |
| `SquareMinus` | `import { SquareMinus } from "lucide-react"` | Positions group collapse icon | 14px |
| `Target` | `import { Target } from "lucide-react"` | Zielerreichung widget | 24px |
| `ChevronsUpDown` | `import { ChevronsUpDown } from "lucide-react"` | Table sort indicator (inactive) | 12px |
| `ChevronUp` | `import { ChevronUp } from "lucide-react"` | Table sort active ascending | 12px |
| `ChevronDown` | `import { ChevronDown } from "lucide-react"` | Table sort active descending | 12px |

---

## 3. Custom SVG Elements (build these, no external assets)

### Red ×-Circle Indicator (rule violation)
```svg
<svg width="12" height="12" viewBox="0 0 12 12">
  <circle cx="6" cy="6" r="6" fill="#E8564A" />
  <path d="M3.8 3.8 8.2 8.2 M8.2 3.8 3.8 8.2" stroke="#fff" stroke-width="1.4" />
</svg>
```

### Yellow !-Triangle Warning
```svg
<svg width="12" height="11" viewBox="0 0 12 11">
  <polygon points="6,0 12,11 0,11" fill="#F5C33B" />
  <rect x="5.4" y="3" width="1.2" height="4" fill="#fff" />
  <rect x="5.4" y="8" width="1.2" height="1.2" fill="#fff" />
</svg>
```

### Carousel Dot (inactive)
```svg
<svg width="8" height="8" viewBox="0 0 8 8">
  <circle cx="4" cy="4" r="3" fill="#D0D0D0" />
</svg>
```

### Carousel Dot (active)
```svg
<svg width="8" height="8" viewBox="0 0 8 8">
  <circle cx="4" cy="4" r="3" fill="#4A90D9" />
</svg>
```

---

## 4. Fonts

No custom font files needed. Use system font stack:
```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
```

This renders identically on Windows (Segoe UI), macOS (SF Pro), and Linux (Roboto/DejaVu).

---

## 5. File Copy Checklist

Before building, copy these files into the mock project:

```bash
# From unriskomega-2026/assets/logos/
cp unriskomega-2026/assets/logos/uro-light.svg  uro-advisor-mock/public/logos/
cp unriskomega-2026/assets/logos/uro-dark.svg   uro-advisor-mock/public/logos/
```

That's it. No other assets from the logos folder are needed for the 3 core screens.

---

## 6. Screenshot Reference

Keep the original screenshots for visual comparison during build:
```
unriskomega-2026/core-case/GUI-screenshots/
├── Client_Advisor_DB.png   # Screen 1 reference
├── Client_DB.png           # Screen 2 reference
└── Portfolio_DB.png        # Screen 3 reference
```

Open these side-by-side with the browser during development for pixel comparison.
