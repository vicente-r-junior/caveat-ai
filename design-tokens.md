# Caveat AI — Design Tokens

These are the visual primitives extracted from the prototype (`docs/caveat-prototype-v3.html`). When generating any UI component, use these tokens. Do not invent new colors, fonts, or radius values without adding them here first.

## Color palette

```css
/* Backgrounds */
--bg:        #ffffff;   /* primary background */
--bg-soft:   #fafaf9;   /* secondary surface (sidebar, cards in resting state) */
--bg-tint:   #f5f3ee;   /* tertiary, document icons, faint emphasis */

/* Text */
--ink:       #18181b;   /* primary text, headlines */
--ink-soft:  #3f3f46;   /* body copy */
--ink-muted: #71717a;   /* metadata, captions, disabled */

/* Lines and dividers */
--line:      #e4e4e7;   /* primary borders */
--line-soft: #f4f4f5;   /* internal separators */

/* Accent — used sparingly */
--burgundy:      #7a1f2b;   /* THE accent color. Use for primary CTA, citations, key emphasis */
--burgundy-soft: #faf2f3;   /* tinted backgrounds for citations and "AI" pill */

/* Semantic */
--danger:      #b91c1c;
--danger-soft: #fef2f2;
--warn:        #c2410c;
--warn-soft:   #fff7ed;
--safe:        #15803d;
--safe-soft:   #f0fdf4;
--gold:        #a16207;   /* for low-severity badges only */
```

**Usage rules:**

- Burgundy is THE accent. One color does the heavy lifting. Do not introduce blue, purple, or teal.
- Backgrounds tier from `bg` (most prominent surface) → `bg-soft` (sidebars, cards) → `bg-tint` (recessed items)
- Semantic colors (danger/warn/safe/gold) appear ONLY in severity badges, redline diffs, status pills. Never in body text or layout chrome.
- Soft variants (`*-soft`) are for tinted backgrounds, never for text.

## Typography

```css
/* Three families, each with a single role */
--serif: 'Fraunces', Georgia, serif;     /* titles, finding-title, citations, document content */
--sans:  'Geist', -apple-system, sans-serif;  /* body, UI, buttons, navigation */
--mono:  'Geist Mono', monospace;        /* metadata, labels, status pills, code-like elements */
```

**Type scale (used in prototype):**

| Use | Family | Size | Weight | Letter spacing |
|---|---|---|---|---|
| Hero title | serif | 64px | 600 | -0.03em |
| Pane title | serif | 36-44px | 600 | -0.02em |
| Section heading | serif | 18px | 600 | -0.01em |
| Body | sans | 15px | 400 | 0 |
| Body small | sans | 13-14px | 400-500 | 0 |
| Eyebrow / label | mono | 10px | 500-600 | 0.18em UPPERCASE |
| Status pill | mono | 10px | 500 | 0.10em UPPERCASE |
| Code / metadata | mono | 11-12px | 500 | 0 |
| Citation / quote | serif italic | 12-14px | 400 | 0 |

**Italics:** the serif italic is decorative — used in titles for emphasis (e.g., "Read the contract. *Keep the secret.*"), and in citation blocks for the quoted text. Never use italic for entire paragraphs.

## Spacing

Tailwind defaults work fine. Common values from the prototype:

- Card padding: `20px` (`p-5`)
- Section gap: `32px` (`gap-8`)
- Inline gap (icons + text): `8-12px` (`gap-2` to `gap-3`)
- Page padding: `32px` (`px-8`)

## Border radius

- Cards and inputs: `8px` (`rounded-lg`)
- Pills and chips: `4-6px` (`rounded` to `rounded-md`)
- Status indicators (round dots): `50%`
- Severity badges and small chips: `3px` (`rounded-sm`)

Avoid `rounded-2xl` and `rounded-3xl` — they make things look like a SaaS landing page.

## Shadows

Used very sparingly. Only:

- Cards in elevated state: `0 1px 3px rgba(0,0,0,0.04)` (very subtle, for active document card)
- Modal/preview document: `0 20px 60px -30px rgba(0,0,0,0.25)` (the export preview)

Never apply shadow to buttons, inputs, or layout containers.

## Status pills

The pattern in the topbar:

```
┌──────────────────────────────┐
│ [●] Local · Gemma 4 31B      │
└──────────────────────────────┘
```

- Family: mono
- Size: 10px
- Letter-spacing: 0.10em
- Background: `bg-soft`
- Border: 1px `line`
- Padding: 5px 10px
- Border-radius: 4px
- Dot: 6×6px, `safe` color, optionally pulsing when "working"

## Citation blocks

Two variants, both using the serif italic:

**Source citation (from a contract):**
- Border-left: 3px `burgundy`
- Background: `burgundy-soft`
- Italic serif text
- Source label in mono uppercase, burgundy color, above the quote

**Proposed redline (from the model):**
- Same structure but border-left and source label in `safe` color
- Bold text inside for the new language

## Severity badges

Mono uppercase, 9px, padding 4px 8px, radius 3px, white text on solid bg:

- High → `danger` background
- Medium → `warn` background
- Low → `gold` background
- Missing → `ink` (black) background

## Layout principles

1. **One screen, one focus.** The Review tab uses a 4-tab structure precisely so each pane has the whole canvas to breathe.
2. **Sidebar on the left, content right.** The 260px document sidebar is fixed; content flows in the main area.
3. **Generous whitespace.** Spec calls for serif headlines that need room. Don't crowd them.
4. **Information density when needed (chat, findings list), spaciousness when not (hero, pane headers).**
5. **No decorative imagery.** No illustrations, no abstract gradients, no stock photos. The product is a tool for serious people.
