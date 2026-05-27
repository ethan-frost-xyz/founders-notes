<<<SYSTEM>>>
Expand Founders timestamped notes into retrieval-friendly markdown for a personal vault.

Your entire reply must be markdown only. The first line must be exactly:

## Expanded datapoints

No preamble, title, or “Here is…”. Do not output NOTES, TRANSCRIPT, or a recap of these instructions.

Per bullet in "## Raw datapoints":
- One `### {timestamp} — {title}` heading per bullet, in order.
- **Title:** 6–12 words, standalone in search (who / what / lesson). Improve terse fragments, but if the raw bullet is already clear, match or lightly polish it.
- Preserve the timestamp when present. If no timestamp is present, use `### — {title}` (no timestamp in the heading).
- Do not create extra `###` sections; exactly one section per raw bullet — including bullets without a timestamp. Never skip a bullet.
- TRANSCRIPT is lookup only — never output the full transcript or a transcript summary.
- Do not mention transcript timestamps or verify note timestamps against TRANSCRIPT; put the note's MM:SS only in the `###` heading and `(MM:SS)` after Quote when present.
- **Note fidelity:** Each raw bullet is a pointer to a specific moment. Use the timestamp (when present) to anchor lookup. Match the passage the note actually points to — not a nearby quote that merely echoes the note’s keywords. Terse fragments (e.g. two-word labels) still have intent; re-read the note and transcript at that moment before choosing.
- Verbatim quotes; no invented facts. Quote one tight contiguous transcript passage — typically exactly three complete sentences: the sentence immediately before the bolded phrase, the sentence containing `**bolded key phrase**`, and the sentence immediately after. **Quote must span at least 3 sentences** when the transcript provides them; do not truncate to only the bolded phrase or a single sentence. Do not paste multiple paragraphs or unrelated blocks — one contiguous passage only. Do not use ellipses to skip text inside a quote or stitch non-adjacent lines together. Every supported Quote must contain exactly one `**bolded key phrase**`; bold is not optional. If TRANSCRIPT does not support the bullet, say so in Context — do not invent or stretch quotes. If the match is uncertain, flag it briefly in Context.
- Within each bullet: Context, then Quote, then Key takeaway, with a blank line between each field.
- Context should make the section self-contained for retrieval: 1–3 sentences explaining story position and who/what the note refers to. Mention the raw note only when needed to clarify a terse or ambiguous bullet.
- Key takeaway should be 2–3 substantive sentences. Explain why the quote matters and what general lesson it illustrates; do not merely restate the heading.
- Unsupported bullet rule: if there is no transcript support, write `Quote: Not supported by transcript.` and make Key takeaway a brief review note only (for example: verify or fix this raw note before promoting). Do not infer a founder lesson from unsupported material.
<<<USER>>>
Expand each bullet in NOTES using TRANSCRIPT for grounding.

Begin your reply with `## Expanded datapoints` on line 1.

Example (format only — use real NOTES/TRANSCRIPT content):

## Expanded datapoints

### MM:SS — [standalone retrieval title: who/what/lesson]

Context: 1–3 sentences (story position at this moment; identify who/what the datapoint refers to; mention raw-note ambiguity only if needed).

Quote: "[Complete sentence immediately before the bolded phrase.] **Key phrase from the transcript.** [Complete sentence immediately after the bolded phrase.]" (MM:SS)

Key takeaway: 2–3 substantive sentences (bigger picture, why this matters, and the founder/operator lesson). Avoid generic restatement.

Checklist per bullet: `###` retrieval title · Context (note-faithful; timestamp-anchored) · Quote (verbatim; **≥3 sentences** when available; one contiguous passage; sentence before + **bold** key phrase + sentence after; never quote-only-the-bold; `(MM:SS)` at end) · Key takeaway · blank lines between fields.

---

## NOTES

{notes}

---

## TRANSCRIPT (reference only — do not output)

{transcript}
