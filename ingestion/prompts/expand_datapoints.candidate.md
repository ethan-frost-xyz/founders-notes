<<<SYSTEM>>>
Expand Founders timestamped notes into retrieval-friendly markdown for a personal vault.

Per bullet in "## Raw datapoints":
- Match timestamp to TRANSCRIPT (MM:SS or H:MM:SS).
- One `###` heading per bullet (timestamp + original bullet text).
- TRANSCRIPT is lookup only — never output the full transcript or a transcript summary.
- Verbatim quotes; no invented facts.
- Missing/ambiguous timestamp: still emit `### — …` and flag uncertainty briefly in Context or Key takeaway.
<<<USER>>>
Expand each bullet in NOTES. Blank line between Context, Quote, and Key takeaway.

## Expanded datapoints

### MM:SS — [bullet text from NOTES]

Context: 1–2 sentences (story position at this moment).

Quote: Short verbatim excerpt; **bold** the most important phrase. (MM:SS)

Key takeaway: 2–3 sentences (bigger picture).

Checklist per bullet: `###` heading · Context · Quote with **bold** · timestamp on Quote line · Key takeaway · blank lines between fields.

---

## NOTES

{notes}

---

## TRANSCRIPT (reference only — do not output)

{transcript}
