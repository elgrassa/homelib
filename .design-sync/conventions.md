# MagicLib — HomeLib's magic-library look

HomeLib is a Python/Streamlit product; this design system is **tokens + two reference rooms + inspiration stills**, not a component library. Build UI with plain HTML/CSS (or Streamlit widgets) styled through the tokens below. There is no JS bundle and no provider to wrap in.

## Setup
Load `styles.css` (it `@import`s `tokens/magiclib.css`) and put `class="magiclib"` on the root element you style. The room fragments scope their own CSS under an id (`#hl-rotunda`, `#homelib-magic-library`) and can be dropped inline; nothing else is required.

## Styling idiom: CSS custom properties, serif reading surfaces
Colours only through `var(--hl-*)` — never hex in new code:

| Token | Light | Role |
|---|---|---|
| `--hl-shell` | `#f7f0e3` | page / parchment background |
| `--hl-panel`, `--hl-panel-2` | `#fffaf0`, `#eee0c7` | cards, drawers, secondary panels |
| `--hl-ink` | `#241c16` | text |
| `--hl-muted` | `#756758` | captions, secondary text |
| `--hl-line` | `#cab995` | borders, dividers |
| `--hl-gold`, `--hl-gold-soft` | `#8a5b13`, `#ead8ac` | accent, active state, primary button |
| `--hl-green` | `#315c4b` | success / evaluation accent |

Fonts: `--hl-font-serif` (Georgia) for headings and reading text, `--hl-font-ui` (system-ui) for controls and captions. Radii `--hl-radius` 12px, `--hl-radius-lg` 20px. Light theme is canonical (`color-scheme: light`); dark values exist as `light-dark()` pairs but no dark room ships. Helper classes in `tokens/magiclib.css`: `.hl-panel`, `.hl-chip`, `.hl-button`, `.hl-button--primary`, `.hl-gold`, `.hl-muted`, `.hl-ui`.

## Where the truth lives
`styles.css` → `tokens/magiclib.css` (tokens + helpers), `tokens/tokens.json` (same values plus the Streamlit theme), `components/Rooms/Rotunda/Rotunda.prompt.md` (the shipped room and its `?door=` contract), `components/Rooms/MagicLibraryPrototype/` (discovery mockup), `guidelines/inspiration/README.md` (the seven stills and what each shows).

## Snippet
```html
<link rel="stylesheet" href="styles.css">
<section class="magiclib hl-panel" style="padding:20px">
  <h2 style="font-weight:500;margin:0 0 6px">Evaluation wing</h2>
  <p class="hl-muted hl-ui">Measure what actually counts.</p>
  <span class="hl-chip">Metrics</span> <span class="hl-chip">Human eval</span>
  <p><button class="hl-button hl-button--primary">Enter the wing</button></p>
</section>
```
