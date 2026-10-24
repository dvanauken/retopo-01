# Ghidra Workbench

## Overview
A reporting and control surface for binary analysis. Every page is a dense
readout: hundreds of operations, addresses, status transitions and evidence
links, scanned rather than read. The aesthetic is a technical instrument —
neutral chrome, colour reserved for status, and no ornament competing with the
data. Rows are compact, headings are quiet, and the accent appears only where
something is clickable or currently selected. Pages are static HTML with a
`<style>` block and no build step; they must render correctly opened straight
off disk.

## Colors
Every colour is a CSS custom property on `:root`, redefined for dark. Never
hard-code a hex in a rule — if a value is missing, add a token.

**Core**
- **Background** (`--bg` #FFFFFF / #171717): Page background
- **Panel** (`--panel` #F2F2F2 / #212121): Tiles, legend, table headers, inset surfaces
- **Border** (`--border` #D8D8D8 / #343434): Dividers, cell rules, container outlines
- **Text** (`--text` #1A1A1A / #E8E8E8): Body copy, values, headings
- **Muted** (`--muted` #6E6E6E / #9A9A9A): Labels, captions, counts, secondary metadata
- **Link** (`--link` #1A5FB4 / #79B0F5): Inline anchors
- **Accent** (`--accent` #1A5FB4 / #3B82F6): Primary buttons, checkboxes, current selection
- **Accent foreground** (`--accent-fg` #FFFFFF): Text on accent fill

**Status families.** Five triplets — background, foreground, border — always
used together so a chip reads correctly on either theme. The meaning is fixed;
do not repurpose a family for a different state.

| Family | `-bg` light / dark | `-fg` light / dark | `-br` light / dark | Means |
|---|---|---|---|---|
| `--green-*` | #E7F5EC / #14301F | #1A6B39 / #7FD6A0 | #B7DFC6 / #245C3A | Explained, complete, pass |
| `--blue-*` | #EAF1FB / #14243C | #1A4E8F / #8FBDF5 | #BED4EF / #24456F | Located, selected, current |
| `--red-*` | #FDECEB / #351816 | #A12A20 / #F0A49C | #F2C4C0 / #5F2B26 | Blocked, failed, destructive |
| `--grey-*` | #EDEDED / #272727 | #6E6E6E / #9A9A9A | #D4D4D4 / #3B3B3B | Out of scope, inert, disabled |
| `--amber-*` | #FDF4E3 / #2C2413 | #8A5D0B / #E0B95F | #EDDCB4 / #544520 | Running, pending, offline warning |

**Table chrome.** Group rows carry real weight because they are the primary
navigation of a long table.
- `--grouprow` #B5B5B5 / #4D4D4D, `--grouphover` #A8A8A8 / #585858, `--groupbr` #969696 / #666666
- `--childrow` #FCFCFC / #1A1A1A — expanded detail rows
- `--thead` #DCDCDC / #2E2E2E — sticky column headers

## Theming
Both themes are mandatory. Declare tokens three times: `:root` for light,
`@media (prefers-color-scheme: dark)` for the system default, then
`:root[data-theme="dark"]` and `:root[data-theme="light"]` so an explicit
toggle overrides the OS in both directions. Test every new component in both
before considering it done.

## Typography
- **UI font**: `-apple-system, "Segoe UI", Roboto, sans-serif` — system stack, no webfonts. Pages open offline and must never wait on a network request for text.
- **Mono font**: `"Cascadia Mono", Consolas, monospace`

Body is 15px/1.55. Sizes below that are expressed in `rem` or `em`; the scale
is deliberately compressed so a table row stays short.

| Role | Size | Weight | Notes |
|---|---|---|---|
| Page title (h1) | 1.6rem | normal | `letter-spacing:-.01em` |
| Tile figure | 1.75rem | 600 | `letter-spacing:-.02em`, `line-height:1.1` |
| Section heading (h2) | 1.05rem | normal | `margin:2.5rem 0 .5rem` |
| Body | 15px | normal | `line-height:1.55` |
| Filename / row title | .95rem | 600 | |
| Table cell | .9rem | normal | |
| Subtitle, note | .9rem / .875rem | normal | muted, `max-width:76ch` |
| Metadata, list item | .82–.85rem | normal | muted |
| Overline | .72–.74rem | 600 | uppercase, `letter-spacing:.06–.07em`, muted |
| Badge, pill | .72rem | 600 | |
| Mono inline | .84em | normal | |
| Mono small | .78rem | normal | ids, addresses, step indices |

Use mono for anything the machine owns — addresses, run ids, operation ids,
symbol names, file paths, CLI commands. Use the UI font for everything a person
wrote. Numeric columns that are compared down the page get
`font-variant-numeric: tabular-nums`.

## Elevation
There are no shadows anywhere. Depth comes from a 1px border and a panel fill,
nothing else. A sticky bar separates from content with `border-bottom`, not a
shadow. If something needs to feel raised, give it `--panel` and a border.

## Components
- **Control bar**: Sticky at `top:0`, `z-index:50`, page background, 1px bottom border. Inner row is flex, `.7rem 1.5rem` padding, `1rem` gap, `flex-wrap:wrap`, with a `.grow` spacer pushing status right. Controls left, state right.
- **Buttons**: `.88rem`, weight 600, `.5rem 1.1rem` padding, 6px radius, accent fill with a matching 1px border. Destructive (`.stop`) is transparent with red foreground and red border. Compact (`.qbtn`) drops to `.28rem .8rem` and `.8rem`. Disabled is `opacity:.4` plus `not-allowed` — never hidden.
- **Selects and inputs**: `font:inherit` at `.9rem`, `.42rem .6rem` padding, 6px radius, 1px border, `--panel` background. Inputs match selects exactly. Focus shows the native ring; do not remove it without replacing it.
- **Checkboxes**: Native `<input type=checkbox>` at 15px with `accent-color: var(--accent)`. No custom-drawn box.
- **Tiles**: Summary figures in a `repeat(auto-fit, minmax(150px, 1fr))` grid with `.75rem` gap. Panel fill, 1px border, 8px radius, `.85rem 1rem` padding. Big number above a `.78rem` muted label. Recolour the figure only — `.good` green, `.warn` blue.
- **Badges**: Inline status labels. `.13rem .5rem` padding, 4px radius, `.72rem`/600, `white-space:nowrap`, and all three tokens of one status family. One badge states one fact.
- **Pills**: Same shape as badges, used for live mode/connection state rather than row status. Neutral grey by default, green when on, amber when off.
- **Tables**: Wrapped in `.scroll` — `overflow-x:auto`, 1px border, 8px radius — because these tables are wider than a laptop. `min-width:980px`, `.9rem`. Headers are sticky-styled overlines on `--thead`. Cells are `.7rem .9rem`, `vertical-align:top`. Two-level: `tr.group` is clickable, filled `--grouprow`, with a `.caret` that rotates 90° when open; `tr.child` is `display:none` until `.show`, filled `--childrow`, and marks its second cell with `box-shadow:inset 3px 0 0 var(--groupbr)`. The current child row takes `--blue-bg`.
- **Definition lists**: The pattern for glossaries and legends. `display:grid`, `grid-template-columns:max-content 1fr`, `.7rem 1rem` gap, `align-items:baseline`. Terms are badges or short labels, definitions are `.85rem` muted capped at `78ch`, collapsing to one column under 620px.
- **Progress bars**: 5–6px tall, `--grey-bg` track, `--green-fg` fill, 3px radius on inline bars and square when spanning a panel edge. Width transitions at `.35s ease`.
- **Legend / panel block**: Panel fill, 1px border, 8px radius, `1rem 1.25rem` padding, opened by an overline heading. Use it for anything explanatory sitting beside the data.
- **Empty state**: 1px *dashed* border, 8px radius, `2rem 1.5rem` padding, muted `.9rem`. Say what to do next and put the command in `<code>`.
- **Offline banner**: Full-bleed amber strip above the control bar, hidden until `.show`. States what is unreachable and the command that fixes it.
- **Footer**: `3.5rem` top margin, `1.25rem` top padding, 1px top border, muted `.8rem`.

## Spacing
- Rhythm is in `rem`; the recurring steps are .3, .5, .7, .85, 1, 1.25, 1.5, 2, 2.5, 3.5
- Page gutter: `1.5rem`, container `max-width:1240px`
- Body has `padding-bottom:5rem` so the last row clears the viewport edge
- Table cells `.7rem .9rem`; compact rows `.5rem 1rem`
- Grid gaps: tiles `.75rem`, definition lists `.7rem 1rem`
- Prose caps at `76ch`, definition text at `78ch`

## Border Radius
- 3px: Progress bar fills
- 4px: Badges, pills, inline code
- 6px: Buttons, selects, inputs
- 8px: Tiles, panels, legends, table containers, empty states

## Writing
The interface explains itself in plain English; this is part of the design, not
separate from it. Mission Control's legend defines *Explained* as "someone read
the decompiled code and wrote down how the operation actually works" rather
than restating the label. Follow that.

- Expand jargon on first use in the UI, and gloss recovered symbol names in words
- A note under a heading says what to do with the thing below it, not what it is
- Say what a control does, not what it is called
- Distinguish what was read from the binary, what was inferred, and what is assumed — hedge in the copy, not in a footnote nobody reads
- Sentence case for headings and buttons

## Do's and Don'ts
- Do define every colour as a token in all four theme blocks before using it
- Do use a status family's `-bg`, `-fg` and `-br` together — a background without its border reads as a different component
- Do keep the accent for interactive and selected states only; status colour carries meaning, accent carries affordance
- Do put wide tables in a `.scroll` container — never let the page itself scroll sideways
- Do use mono for machine-owned strings and the UI font for human-written prose
- Do keep pages self-contained: one inline `<style>`, no webfonts, no CDN, no build step
- Don't add shadows, gradients, or decorative illustration — a border and a panel fill are the only elevation
- Don't introduce a sixth status colour; map the new state onto an existing family or argue for changing the set
- Don't use red for anything but blocked, failed, or destructive
- Don't grow the type scale — if something needs emphasis, use weight 600 or the accent, not a larger size
- Don't ship a component tested in only one theme

## Extending
Colours, type, badges, tables, tiles and legends above are transcribed from
`results/index.html` and `targets/*/results/index.html`, which are the
reference implementations. Inputs, tabular numerics, and the writing rules are
extrapolated from adjacent patterns to fill gaps those pages never needed. When
a page needs something genuinely new, build it from the existing tokens, then
add it here.


## Retopo1 application additions

The neutral UI tokens above are preserved in this independent local app. Its layout is a source/result modeling workspace with a persistent Generate action and a scrollable controls region. The canvas uses real shaded geometry; no decorative page gradients or shadows are added.

Canvas-only material tokens: `--model` #C4C8CF in both themes; `--wire` #4F657C light / #4F718C dark; `--crease` #303943 both; `--guide` matches link blue #1A5FB4 light / #79B0F5 dark; `--grid` matches the border token. Neutral white hemisphere/key/fill lights shade model surfaces; these are scene lights rather than UI status colors. Curves indicate current editable constraints. Status families keep their original pass/current/error/pending meanings.

The project retains its own copy of DESIGN.md; it does not change the research workbench reference pages or their sealed evidence epoch. Both themes and a narrow viewport are checked with an actual browser.
