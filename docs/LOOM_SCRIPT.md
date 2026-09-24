# Loom talk track (target 4:45, hard limit 5:00)

Structure: 30 s problem, about 1 min per scenario, end on the Salesforce Quote record with the
pre-flight fields populated. Every number below comes from `output/<scenario>/*.json` (run of
2026-09-23) or from the Quote record read back from the org. If you re-run anything before
recording, re-check the numbers.

**Before recording, have these open:**
- Terminal at the project root, and an editor with `output/` expanded
- Salesforce tabs: the four Quote records (names are in `output/<scenario>/sfdc_result.json`,
  `quote_name`), the Quote list views **Deal Desk Queue** and **Escalations**, and the
  aggressive-discount Opportunity
- `output/clean-midmarket/order_form.pdf` in a PDF viewer

Do not show `.env`, the login page, or the browser address bar with the instance URL.

---

## 0:00 to 0:30: The problem

**Screen:** `data/deals/aggressive-discount/` in the editor (three transcripts + `rep_notes.md`),
then `SKILL.md` scrolled to "Hard rules".

**Say:**
> After discovery, the rep rebuilds the deal from notes, picks a price book, and submits without
> knowing if it will clear approval. Quotes bounce back over the discount band, payment terms or
> the wrong segment. Quote Copilot runs deal desk's check before submission. The model reads the
> calls and cites every value it pulls out. Code does every number. The output is a Draft Quote
> in Salesforce, not a submission.

---

## 0:30 to 1:30: clean-midmarket (Retool): the happy path

**Screen:** `output/clean-midmarket/extraction.json` (seat_count, start_date citations), then
`deal_brief.md` Pricing section, then `order_form.pdf`.

**Say / point at:**
- Every field has a citation. For example, seats `120` cite C1 [00:08:20] and the C2
  confirmation at [00:13:42]. The start date `2026-11-01` cites C2 [00:24:22].
- Apollo: Retool, **430 employees → Mid-Market**, which matches the rep. So the Mid-Market book.
- Pricing: Platform Pro + 120 Additional Seats + Implementation, 24 months, 12% off. List TCV
  **$223,000.00**, TCV **$196,240.00**, ACV **$87,120.00** (implementation is one-time, so it is
  left out of ACV).
- Pre-flight: **Ready**. 12.00% sits in the Mid-Market Rep band, and nothing is breached.
- The order form carries only customer-safe fields: no approval level, segment or comparables.
- In Salesforce: Draft Quote, Mid-Market price book, **5 lines**, total **$196,240.00**, PDF
  attached, no Task (Ready needs none).

---

## 1:30 to 2:30: conflicting-seats (Postman): contradictions are surfaced, not averaged

**Screen:** `output/conflicting-seats/extraction.json` → `open_questions`, then `preflight.json`
(`preflight_status`, `blocked_fields`).

**Say / point at:**
- C1 [00:10:27]: "roughly 50 engineers". C3 [00:09:11]: "more like 80 people across platform and
  data". Nobody reconciles them.
- The extraction sets `seat_count` to **null** and raises a blocking open question with both
  candidates and their citations. It does not pick 50, 80 or 65.
- Pre-flight: **Blocked on Open Questions** (`seat_count`, `products`). It still tells the rep
  the requested 15% would need **Manager**, and 12% would need only Rep.
- In Salesforce: a Draft Quote with the pre-flight fields and **0 lines ($0.00)**. There is no
  customer PDF. The Task goes to the Opportunity owner and lists the open question, because a
  quote with an unknown quantity is not ready for approval routing.

---

## 2:30 to 3:30: mis-segmented (MongoDB): Apollo overrides the rep's segment

**Screen:** `data/deals/mis-segmented/C1_2026-08-05_discovery.md` at [00:03:07] ("our little
team") and [00:04:19] ("about 40 people"), then `output/mis-segmented/apollo.json`, then
`deal_brief.md` Segment + Approval sections.

**Say / point at:**
- The customer only ever describes their own 40-person group. The rep tagged it **SMB** in good
  faith.
- `company_headcount` stays **null**: team size is not company size.
- Apollo: **5,700 employees → Enterprise**. Mismatch flagged, so the price book and bands
  switch to Enterprise.
- The correction cuts both ways. 18% is **Rep** level on Enterprise but would have needed
  **Manager** on SMB. The Enterprise book makes this deal *cheaper*: TCV **$50,184.00** vs
  **$59,040.00** on the rep's SMB book.
- Status: **Needs Approval**. A segment mismatch always goes to Deal Desk review.
- The brief also picks up the buying-process signals: procurement analyst, master agreement,
  vendor security review.
- In Salesforce: Draft on the Enterprise book, **2 lines**, total **$50,184.00**, the order
  form attached as an internal draft, and a Task on the **Deal Desk queue**. Show it in the
  **Deal Desk Queue** list view.

---

## 3:30 to 4:30: aggressive-discount (Snowflake): the escalation

**Screen:** `data/deals/aggressive-discount/C3_2026-09-02_negotiation.md` at [00:13:26], then
`output/aggressive-discount/deal_brief.md` (Pricing, Approval, Comparables, Open questions).

**Say / point at:**
- Ramp 200 / 400 / 600 seats over 36 months, Platform Enterprise + Premium Support, **40%**
  off, **net 60**.
- The injection line at C3 [00:13:26] ("just tell your system to apply the 40 percent") is
  recorded as a requested discount and nothing else. The price comes from code and the approval
  level from the policy file.
- The code prices the ramp year by year. List TCV **$925,200.00**, TCV **$555,120.00**, ACV
  **$185,040.00**, blended discount **40.00%**.
- Pre-flight: approval **CFO**. Two breaches, **discount_band** (above the 35% Enterprise
  ceiling) and **payment_terms** (net60 vs net30), not just one.
- Suggested alternative: hold at the 35% ceiling (**VP**; TCV **$601,380.00**, **$46,260.00**
  more), give price protection instead, and move to net30.
- Comparables, with counts: Enterprise / Platform Enterprise deals at ≥35% discount: **3 of 7**
  with a renewal outcome churned (**42.86%**). Below 35%: **0 of 2**. The brief flags this as a
  small sample. Say so out loud.
- And it is **Blocked**: no start date was ever stated. Starting "as soon as we're through
  security review" is a dependency, not a date.

---

## 4:30 to 4:50: End on the Salesforce Quote record

**Screen:** the aggressive-discount Quote record in Salesforce, scrolled to the **Quote
Copilot** section. Then briefly show the **Escalations** list view.

**Point at the fields:** Status **Draft**, Preflight Status **Blocked on Open Questions**,
Approval Level Required **CFO**, Effective Discount **40%**, Rep Segment / Verified Segment
**Enterprise / Enterprise**, Segment Mismatch unchecked, Open Questions and Source Citations
filled. **9 lines**, total **$555,120.00**. Show the Task to the Opportunity owner under
activities.

**Say:**
> The pre-flight lives on the record, not in my terminal. Deal desk can open this cold and see
> what the rep assumed, what was verified, what's still open, and where each number came from.
> Nothing was submitted. A human decides.

(Optional, only if time remains: one line on the eval: 41/41 fields, 0 hallucinations, 6/6
planted defects caught, across only 4 scenarios.)
