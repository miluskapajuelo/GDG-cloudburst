# SentinelDesk Console: Design Rules

Owner: Team C (`miluskapajuelo`). These rules apply to every agent session that builds or changes the console in `web/`. Read this file after [tasks/team-c-console-demo.md](tasks/team-c-console-demo.md) and before you write any UI code.

The goal: a console that does not look like a generic AI-generated template. Pick one concrete physical metaphor from the support-desk world and let it drive colour, shape and layout.

Where a rule here conflicts with the task file, the task file wins on **what** to show (fields, behaviour, deadlines). This file wins on **how** it looks. Known conflicts are resolved in section 9.

---

## 1. Drafts (do this before building, keep it short: max 20 minutes)

1. Make three full mockups of the console in clearly different directions. Base each on a real-world metaphor from the product's own world. Candidates (pick your own if better):
   - **Dispatch board**: a 911 / incident dispatch desk, cards on a rail, escalation as a routing slip.
   - **Mail sorting room**: pigeonholes and routing stamps; type, queue and priority as stamps on an envelope.
   - **Triage ward**: a hospital triage tag (the paper tag with tear-off colour strips) for the escalation decision.
   - **Case file**: a manila folder with a cover sheet, the draft reply as a typed memo, precedents as clipped exhibits.
2. Pick one. Then borrow the best single feature from the losing drafts.
3. Offer two or three palettes inside the chosen draft. Show them to the human and let them pick before you build.
4. Log the pick (metaphor, grafted feature, palette) in the decision log in `docs/plan.md` only if the human approves the edit.

The lesson from the reference project (a photo-restoration app, not this product): it made Darkroom, Light table and Album drafts, picked Album, and grafted the Light table's compare modes onto it. Pick the draft whose metaphor fits the product best, then graft on the most useful feature from a losing draft.

---

## 2. Colour and surfaces

- Define the palette once as CSS variables (tokens). Use only those. With Tailwind, map the tokens in `tailwind.config` and never use raw Tailwind colours (`bg-white`, `text-gray-500`, etc.).
- No pure white (`#fff`) page background. Use a tinted off-white or a deep tinted dark.
- No harsh gradients, rainbow colouring, neon, basic pastels, or the purple-and-black palette.
- One accent colour, used sparingly: selected states, focus ring and the brand mark.
- Status colours are separate from the accent and muted to match the palette. The console needs three route colours (AUTO_DRAFT, HUMAN_REVIEW, ON_CALL) plus error. Keep them distinguishable for colour-blind viewers: always pair colour with the badge text.
- Quiet text must pass 4.5:1 contrast on every surface it sits on. Check it; the demo runs on a projector.
- No coloured accent stripe on cards. Show selection with an outline.
- No glassmorphism. Dialog backdrops are a solid scrim.
- No drop shadow on everything. Use hairline rules and surface steps (page, panel, band) for depth.

## 3. Typography

- No Inter, Geist or Space Grotesk.
- A characterful serif or display face for headings, a highly legible sans for body text. (The reference app used Young Serif and Atkinson Hyperlegible.) A monospace for ticket IDs and latency numbers is fine.
- Self-host the fonts (put the files in `web/public/fonts/` or use `@fontsource/*` packages). No Google Fonts `<link>`.
- Body text around 17px with 1.55 line height. Use `text-wrap: balance` on headings.

## 4. Layout and components

- No three feature cards in a row. Use a 2x2 grid or a vertical list.
- No bento grids, terminal-window mockups or checkmark bullets.
- No single uniform corner radius. Give each element type its own shape (for example pill buttons, square chips, lightly rounded panels).
- No loose icons floating beside text.
- Put every dialog on one shared modal shell.
- Show loading with skeleton placeholders shaped like the content (badge, prediction rows, draft lines, precedent rows). No spinners as the only loading state.

## 5. Decoration and motion

- No radial orbs, glow blobs, dot-grid backgrounds, sparkle icons or animated arrows.
- Hovers change colour only. No hover animation on every element.
- Decoration comes from the metaphor (for example a routing stamp, a tear-off tag edge, a paper clip on precedents), never from effects.

## 6. The page

- Build one page only. Skip extra routes, 404 pages, breadcrumbs, favicon sets and share images.
- One `h1`.
- Browser tab title names the product (`SentinelDesk`), never "Vite" or "React".
- Visible keyboard focus ring in the accent colour on every interactive element.

## 7. Content and trust

- No fake reviews, testimonials or placeholder content.
- Demos show real API output, not filtered or staged samples. Mock mode is for building only; the demo uses the real pipeline.
- Never claim more than the product does. Metrics shown in the footer strip come from `GET /metrics`, not hand-typed numbers.

## 8. Copy rules

UI copy should read like a person wrote it plainly. Run all of it through the `humanizer` skill if available, including text written earlier.

- No middot (`·`) separators. Use commas, parentheses or separate lines.
- No eyebrow labels above headings, especially with a pulsing dot.
- No italic accent phrases.
- No three-part lists or triads ("Removes X, fixes Y, and brings back Z").
- No "It's not X, it's Y" phrasing.
- No em dashes and no emojis in UI copy.
- Plain headings over clever ones: "Draft reply", "Similar past tickets", "Why this was escalated".
- These rules also cover the `<title>` and meta tags.

## 9. Conflicts with the task file, resolved

| Task file says | Do this instead |
|---|---|
| Three prediction cards (type, queue, priority) in a row | A vertical list or a single band with three rows. Same data, no three-card row. |
| `lang · PII` chips (middot in layout sketch) | Separate chips, no middot in rendered text. |
| Badge green / amber / red | Keep the meaning, use the muted status tokens from your palette. |
| Tailwind | Allowed, but only through the token mapping in section 2. |

## 10. Checklist before merging a UI PR

- [ ] Palette lives in tokens, no `#fff` page, one accent, contrast checked
- [ ] No gradients, neon, pastels, glass, glow blobs, dot grids or sparkles
- [ ] Shadows used only where they mean something
- [ ] No Inter, Geist or Space Grotesk; fonts self-hosted
- [ ] No three-card rows, bento grids, checkmark bullets or floating icons
- [ ] Corner radius differs by element type
- [ ] Hovers change colour only
- [ ] Skeleton loaders wherever content loads
- [ ] One page, one `h1`, tab title is `SentinelDesk`
- [ ] No fake or placeholder content; demo shows real output
- [ ] Copy has no middots, eyebrows, italics, triads, em dashes or emojis
- [ ] All copy passed through a humanizer
