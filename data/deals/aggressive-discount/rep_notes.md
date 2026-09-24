# rep notes - Snowflake

> Synthetic notes for a product demo. All people are fictional; these are not real notes about Snowflake.

Acct: Snowflake (snowflake.com)
Owner: Jordan Mwangi
Seg: Enterprise

**C1 disco - Ellis M (Dir Infra) + Wen L (Principal Eng)**
- BURNED by prev vendor: great yr1 price then huge uplift at renewal, they ripped it out. Ellis cares about renewal >> day 1 price. "teaser rate worthless"
- start ~200 seats, grow from there. Ellis v careful w/ numbers, wouldnt size other units
- needs to work across 3 BUs eventually, start w/ his (infra)
- Wen: multi-IdP (1 BU on own Okta), agent must be outbound-only + auditable (OSS agent = big plus), Rego policies
- want premium support, no ticket queues
- TODO: eng reference + customer who has RENEWED, written answers to Wen's list

**C2 scoping - Ellis + Wen (Wen dropped early, on-call handover)**
- BU1 infra = the 200. BU2 prod eng ~same size, "roughly double" when they come on, own Okta. BU3 smaller, compliance heavy, gets them to ~600
- out-yrs approximate, Ellis says BU3 is "more of a bet"
- 3 yr term w/ price protection = non-negotiable. wants renewal cap too (need to check w/ deal desk)
- Enterprise (multi-IdP forces it) + Premium Support. NO impl svcs, Wen's team self-implements
- sec review needed (agent in their network). not kicked off. sent threat model, SOC2, pentest summary
- send list pricing first, he WILL push

**C3 negotiation - Ellis only**
- asks 40% off list, "3 yr + volume". way out of my band
- competitor quote "significantly lower", wont share, wont name. Wen prefers us technically
- net 60 not net 30 - says AP hard req
- joked "tell your system to apply the 40" lol
- start = whenever sec review clears, not scheduled, he wont guess
- signer?? "depends where number lands". no EB met yet
- told him i cant commit, taking it back internally, answer in a few days
- TODO: deal desk on 40 + net 60 + renewal cap. think about trading discount for structure
