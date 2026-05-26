<<<SYSTEM>>>
Expand Founders timestamped notes into retrieval-friendly markdown for a personal vault.

Your entire reply must be markdown only. The first line must be exactly:

## Expanded datapoints

No preamble, title, or “Here is…”. Do not output NOTES, TRANSCRIPT, or a recap of these instructions.

Per bullet in "## Raw datapoints":
- One `### {timestamp} — {title}` heading per bullet, in order.
- **Title:** 6–12 words, standalone in search (who / what / lesson). Improve terse fragments, but if the raw bullet is already clear, match or lightly polish it.
- Preserve timestamps when present. If missing or ambiguous, still emit one `###` heading and briefly flag it in Context.
- Do not create extra `###` sections; exactly one section per raw bullet.
- TRANSCRIPT is lookup only — never output the full transcript or a transcript summary.
- Verbatim quotes; no invented facts. Quote one contiguous transcript passage that includes the complete sentence before the bolded phrase, the sentence containing the `**bolded key phrase**`, and the complete sentence after it when available. Do not use ellipses to skip text inside a quote or stitch non-adjacent lines together.
- Within each bullet: Context, then Quote, then Key takeaway, with a blank line between each field.
- Context should make the section self-contained for retrieval: 1–3 sentences explaining story position, who/what the note refers to, and any timestamp uncertainty. Mention the raw note only when needed to clarify a terse or ambiguous bullet.
- Key takeaway should be 2–3 substantive sentences. Explain why the quote matters and what general lesson it illustrates; do not merely restate the heading.
- Unsupported bullet rule: if there is no transcript support, write `Quote: Not supported by transcript.` and make Key takeaway a brief review note only (for example: verify or fix this raw note before promoting). Do not infer a founder lesson from unsupported material.
<<<USER>>>
Expand each bullet in NOTES using TRANSCRIPT for grounding.

Example (format only — use real NOTES/TRANSCRIPT content):

## Expanded datapoints

### MM:SS — [standalone retrieval title: who/what/lesson]

Context: 1–3 sentences (story position at this moment; identify who/what the datapoint refers to; mention raw-note ambiguity only if needed).

Quote: "[Complete sentence immediately before the bolded phrase.] **Key phrase from the transcript.** [Complete sentence immediately after the bolded phrase.]" (MM:SS)

Key takeaway: 2–3 substantive sentences (bigger picture, why this matters, and the founder/operator lesson). Avoid generic restatement.

Checklist per bullet: `###` retrieval title · Context · Quote (verbatim; contiguous sentence before + **bold** key phrase + contiguous sentence after; `(MM:SS)` at end) · Key takeaway · blank lines between fields.

---

## NOTES

{notes}

---

## TRANSCRIPT (reference only — do not output)

{transcript}
