---
name: "Meeting Notes Lab"
description: "A calm lavender notebook for local voice work."
colors:
  ink: "#292735"
  muted: "#696573"
  accent: "#6746ad"
  accent-dark: "#51358c"
  rail: "#f0edf7"
  ground: "#faf9fc"
  line: "#e8e5ec"
  tint: "#f6f3fb"
  white: "#fff"
  error: "#a33040"
  control-border: "#ddd8e5"
  control-ink: "#5d536f"
  field-border: "#c7bed5"
  nav-ink: "#655e74"
  nav-selected: "#503388"
  nav-hover: "#e8e2f2"
  recording: "#a23b58"
  recording-tint: "#fcf0f3"
typography:
  display:
    fontFamily: "Hanken, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "34px"
    fontWeight: 550
    lineHeight: 1.15
    letterSpacing: "-1.05px"
  title:
    fontFamily: "Hanken, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "21px"
    fontWeight: 550
  body:
    fontFamily: "Hanken, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.85
  support:
    fontFamily: "Hanken, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Hanken, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "13px"
    fontWeight: 600
rounded:
  field: "6px"
  writing-field: "7px"
  button: "8px"
  navigation: "9px"
  inset: "10px"
  mobile-sheet: "12px"
  sheet: "14px"
spacing:
  "8": "8px"
  "10": "10px"
  "12": "12px"
  "16": "16px"
  "18": "18px"
  "22": "22px"
  "24": "24px"
  "28": "28px"
  "36": "36px"
  "44": "44px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.white}"
    rounded: "{rounded.button}"
    padding: "11px 15px"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.accent-dark}"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.control-ink}"
    rounded: "{rounded.button}"
    padding: "11px 15px"
    typography: "{typography.label}"
  button-secondary-hover:
    backgroundColor: "{colors.rail}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.accent-dark}"
    padding: "5px"
  navigation:
    backgroundColor: "transparent"
    textColor: "{colors.nav-ink}"
    rounded: "{rounded.navigation}"
    padding: "13px 12px"
  navigation-selected:
    backgroundColor: "{colors.white}"
    textColor: "{colors.nav-selected}"
  availability:
    backgroundColor: "{colors.white}"
    textColor: "#58436f"
    rounded: "5px"
    padding: "6px 8px"
  notebook:
    backgroundColor: "{colors.white}"
    rounded: "{rounded.sheet}"
    padding: "25px 28px 0"
  writing-field:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.writing-field}"
    padding: "16px"
  capture:
    backgroundColor: "{colors.tint}"
    rounded: "{rounded.inset}"
    padding: "18px"
  import-zone:
    backgroundColor: "{colors.tint}"
    rounded: "{rounded.inset}"
    padding: "37px 18px"
  download:
    backgroundColor: "{colors.tint}"
    textColor: "{colors.accent-dark}"
    rounded: "{rounded.field}"
    padding: "9px 11px"
---

# Design System: Meeting Notes Lab

## Overview

**Creative North Star: "The meeting notebook"**

A polished, Wispr-like notebook with a cool lavender rail, white writing surfaces, graphite text and deep violet actions. The user chose this familiar notebook persona; retain its quiet, compact controls and generous writing area.

Speech creation shares the same paper, controls and supporting explanations as transcription. Typography and tonal separation supply the hierarchy; decoration stays subordinate to the words.

**Key Characteristics:**
- Lavender navigation surrounding a white writing surface.
- Compact controls, generous transcript line spacing and restrained separators.
- One shared visual vocabulary for recording, importing and creating speech.

## Colors

### Primary
Deep violet (`accent`) identifies primary actions and the microphone. Its darker companion (`accent-dark`) handles hover and quiet links. Rose recording states and the error color are semantic exceptions.

### Neutral
Graphite (`ink`) carries reading text; `muted` carries explanations, status and file extensions. The cool lavender `rail`, near-white `ground`, white sheets and pale `tint` create depth. `line` separates content without boxing every item. The frontmatter retains the actual CSS values; small control-specific variants remain available for faithful reuse.

**The Violet Action Rule.** Use deep violet for actions, selection and focus; reserve rose for recording and error states.

## Typography

Locally served Hanken Grotesk (CSS family `Hanken`) leads the shared sans-serif stack. Medium weights, compact headings and open transcript leading create the notebook's quiet character.

- **Display:** the page heading uses the display token; it reduces to 30px at 1180px and 29px at 680px.
- **Title:** editable notebook names use the title token, reducing to 19px on mobile. Capability headings use 20px/1.3 at weight 550.
- **Body:** transcripts use the body token, a 70ch maximum and preserved line breaks; mobile text is 15px. Speech input uses 16px/1.75.
- **Label:** buttons and speech form labels share the label token. Support copy is generally 12px with 1.6–1.8 leading; timers and character counts use tabular numerals.

**The Writing Space Rule.** Give transcripts room to breathe; keep supporting labels compact and muted.

## Layout

The desktop shell pairs a sticky, viewport-height 220px rail with the workspace. Main content is capped at 1420px, padded 45px 44px 28px; the work area pairs flexible paper with a 250px explanation column and a 28px gap. Shared spacing values are extracted recurring measurements, not a newly imposed arithmetic scale.

- **1500px and above:** the aside grows to 280px, gap to 40px, and notebook padding to 32px 36px 0.
- **1180px and below:** the rail is 194px, main padding 35px 28px, aside 210px and gap 22px.
- **960px and below:** the work area becomes one column and the contextual aside is hidden.
- **680px and below:** the rail becomes a static header; all four navigation items occupy a two-column grid. Main padding is 27px 18px 24px; paper padding is 21px 18px 0. Speech paper retains its later 28px top-padding override. Explore content collapses to one column.

## Elevation & Depth

Tone and single-pixel borders do most of the work. Selected desktop navigation uses `0 3px 10px rgba(48, 33, 78, 0.04)`; the microphone uses `0 4px 9px rgba(74, 49, 122, 0.12)`. Mobile navigation drops its shadow. Notebook sheets have no shadow.

**The Quiet Depth Rule.** Separate sheets with tone and thin borders; reserve soft shadows for selected navigation and the microphone.

## Shapes

Rounded rectangles distinguish nested controls from the larger sheet. Use the frontmatter's field, button, navigation, inset and sheet radii; sheets reduce to the mobile-sheet radius on narrow screens. The microphone is circular (52px desktop, 44px mobile). Line icons use inline SVG, normally 20px with a 1.7px rounded stroke; button icons reduce to 17px.

## Components

- **Buttons:** violet primary and white bordered secondary controls share their size and weight. Primary hover deepens the violet; secondary hover takes the rail tone. Quiet actions use transparent backgrounds and a pale hover fill. Disabled buttons use 0.45 opacity and a not-allowed cursor.
- **Focus and motion:** interactive controls carry a 2px violet focus outline with 4px offset; speech textarea/select use 3px offset. Buttons transition background and color over 0.18s ease. Reduced-motion preference removes transitions.
- **Navigation:** muted icon-and-text rows become white with deep violet text when selected. Desktop items use 14px/550 type; mobile items use 12px, 6px corners and a two-column layout.
- **Availability tags:** small rectangular status labels use white on the lavender Explore panel. Neutral labels use a pale gray-lavender fill. They communicate actual availability, not ornamental category labels.
- **Notebook:** white, thin-bordered paper encloses a working area and a pale footer separated by a rule. The footer reaches the sheet edges; the transcript is plain flowing text rather than nested cards.
- **Fields:** the notebook title is borderless. Speech textarea and voice select share a visible field-border stroke, white fill and graphite text; the textarea is vertically resizable and at least 240px tall (220px mobile). Voice selection is at least 44px tall. Vocabulary uses a smaller 12px input inside a disclosure.
- **Capture bar:** a pale inset holds the round microphone, compact instructions and tabular timer. Recording turns the action rose and the inset pale rose, swaps the microphone for a stop square and reveals actual amplitude. Narrow screens remove subordinate capture copy during recording.
- **Import zone:** a pale inset with a dashed border and an inline upload icon. Hover and drag highlight the border violet and deepen the fill; a busy zone uses 0.55 opacity and a wait cursor.
- **Results and exports:** short status text precedes the transcript or native audio player. Error status uses rose text on a pale rose inset. Downloads are small bordered lavender links that wrap; generation uses a 5px violet progress track. Native audio controls remain browser-provided.

## Do's and Don'ts

### Do:
- Do reuse the lavender rail, white notebook and violet action pairing.
- Do retain explicit focus outlines, reduced-motion support and real status labels.
- Do use the existing muted color for secondary text, including format extensions.
- Do let mobile navigation form a two-column grid and keep the writing surface full width.

### Don't:
- Don't add a separate visual identity for speech creation.
- Don't imply fabricated live activity, summaries or unavailable capabilities.
- Don't turn the writing surface into a stack of heavily shadowed cards.
