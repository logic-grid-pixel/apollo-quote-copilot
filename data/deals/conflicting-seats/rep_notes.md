# rep notes - Postman

> Synthetic notes for a product demo. All people are fictional; these are not real notes about Postman.

Acct: Postman (postman.com)
Owner: Alex Chen
Seg: Mid-Market

**7/29 disco - Priya R (VP Eng)**
- met at PlatformCon (DX panel!). tacos > rooftop
- trigger = config incident, postmortem action item "eval change mgmt tooling" owner Priya
- guardrails first, then self-serve
- ~50 eng need access, she said "roughly", has to check internally
- eval'ing 2 other vendors, wont name. one has nice UI, other flexible/heavy setup
- Oct 1 start = top of their fiscal qtr
- prob Pro
- Okta
- she said "need to check" like 6x. budget = tooling line (she thinks), sign threshold tbd
- TODO sso + api docs to Tom before tech call

**8/14 tech eval - Priya + Tom A (Staff Eng)**
- SSO hard req, SAML/Okta, SSO-only incl admins. break glass optional
- SCIM ok, nested grps flattened - "fine"
- data residency US ok (legal signed off)
- Tom: RATE LIMITS. per-tenant limit is a dealbreaker risk, needs raised ceiling on Pro in writing
- webhooks, GH Action, rules-as-code all landed well
- Priya: 2yr term, finance wants predictability
- todo: rate limit answer (sent), sandbox for Tom (sent), SOC2 (sent)

**9/4 commercial - Priya**
- Tom likes sandbox, ranked us #1 of 3
- net 30 fine
- asking 15% -> above my band, take to mgr
- start still Oct 1
- rollout: Tom wants 3 training waves, some ppl in Europe, morning PT sessions
- no impl svcs (self serve), no prem support
- Priya can sign, finance wants to see OF first
- legal next: MSA + DPA, liability cap will be a fight. offer counsel-to-counsel call
- TODO: mgr approval on 15, send MSA/DPA today
