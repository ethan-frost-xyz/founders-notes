<<<SYSTEM>>>
Expand Founders timestamped notes into retrieval-friendly markdown for a personal vault.

Your entire reply must be markdown only. The first line must be exactly:

## Expanded datapoints

No preamble, title, or “Here is…”. Do not output NOTES, TRANSCRIPT, or a recap of these instructions.

Per bullet in "## Raw datapoints":
- Match timestamp to TRANSCRIPT (MM:SS or H:MM:SS).
- One `### {timestamp} — {bullet}` heading per bullet, in order.
- TRANSCRIPT is lookup only — never output the full transcript or a transcript summary.
- Verbatim quotes; no invented facts.
- Missing/ambiguous timestamp: still emit `###` and flag uncertainty briefly in Context or Key takeaway.
- Within each bullet: Context, then Quote, then Key takeaway, with a blank line between each field.
<<<USER>>>
Expand each bullet in NOTES using TRANSCRIPT for grounding.

Begin your reply with `## Expanded datapoints` on line 1.

Example (format only — use real NOTES/TRANSCRIPT content):

## Expanded datapoints

### MM:SS — [bullet text from NOTES]

Context: 1–3 sentences (story position at this moment).

Quote: Full quote exherpt; **bold** the most important phrase and include at minimum the full sentence before and AFTER the bolded phrase. (MM:SS)

Key takeaway: 2–3 sentences (bigger picture).

Checklist per bullet: `###` heading · Context · Quote with **bold** · timestamp on Quote line · Key takeaway · blank lines between fields.

---

## NOTES

{notes}

---

## TRANSCRIPT (reference only — do not output)

{transcript}
