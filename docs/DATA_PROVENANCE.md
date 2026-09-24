# Data provenance

Where every seeded field in the Salesforce demo org comes from. Seed data is
written by three scripts, run in this order:

1. `scripts/seed_accounts.py`: 15 Accounts
2. `scripts/seed_contacts.py`: 55 Contacts (3-4 per Account)
3. `scripts/seed_opportunities.py`: 80 closed Opportunities

Every seeded record carries `Seed_Key__c` starting with `SEED-`, so seed data can
always be told apart from real or sample records and removed cleanly.

## Source types

| Source | Meaning |
|---|---|
| **Apollo** | Copied as-is from Apollo organization enrichment for the account's domain. |
| **Derived** | Calculated from Apollo data by a documented rule. |
| **Curated** | Chosen by hand to be realistic; not from any external source. |
| **Synthetic** | Generated with `random` (seeded, so reproducible) to model deal history. |
| **Generated** | Keys, names and dates produced by the script itself. |

## Account (`seed_accounts.py`)

| Field | Source | How |
|---|---|---|
| `Seed_Key__c` | Generated | `SEED-ACC-{domain}` |
| `Name` | Apollo | `name` |
| `Website` | Apollo | `website_url` |
| `NumberOfEmployees` | Apollo | `estimated_num_employees` |
| `Industry` | Apollo | `industry` (currently the same value for all 15) |
| `AnnualRevenue` | Apollo | `annual_revenue` |
| `BillingCity` | Apollo | `city` |
| `BillingState` | Apollo | `state`; left blank if the org's State picklist rejects it |
| `BillingCountry` | Apollo | `country`; left blank if the org's Country picklist rejects it |
| `Description` | Apollo | `short_description` |
| `Tech_Stack__c` | Derived | Up to 10 names from `current_technologies`: up to 3 monitoring tools first, then one per category (cloud, database, data, CRM, BI, security, ...) round-robin |
| `Employee_Band__c` | Derived | `<200`, `200-2000`, `>2000` from `estimated_num_employees` |
| `Apollo_Enriched_Date__c` | Generated | Date the script ran |

Fields Apollo returns as null are never written; they stay blank rather than
getting a placeholder. Known gaps: Plausible Analytics has no `AnnualRevenue`, and
its `BillingState` (`Tartu County`) was rejected by the picklist.

## Contact (`seed_contacts.py`)

| Field | Source | How |
|---|---|---|
| `Seed_Key__c` | Generated | `SEED-CON-{domain}-{n}` |
| `AccountId` | Generated | The seeded Account for the domain |
| `Title` | **Curated** | Typical title for the account's employee band. See note below. |
| `FirstName`, `LastName` | Synthetic | From a fixed list of made-up names, stable per seed key |
| `Buying_Role__c` | Derived | Keyword rules on `Title` (e.g. procurement/sourcing → Procurement; CFO/finance/CEO → Economic Buyer; engineering/IT/CTO → Technical Evaluator; operations/COO → Champion) |
| `Email`, `Phone` | Not set | Never written |

**Titles are not from Apollo yet.** The script calls Apollo People Search first,
but the current Apollo key is on the Free plan, which blocks that endpoint (403
`API_INACCESSIBLE`). It then falls back to the curated list. Each
`data/cache/titles_{domain}.json` records which source it used (`apollo` or
`curated`). After an Apollo upgrade, run `python scripts/seed_contacts.py --refresh`
to switch to real titles.

**Privacy:** only job titles are ever taken from Apollo People Search. The client
function (`apollo_client.search_people_titles`) drops names, emails and every
other personal field before returning, so none reach Salesforce, the cache, logs
or git.

## Opportunity (`seed_opportunities.py`)

| Field | Source | How |
|---|---|---|
| `Seed_Key__c` | Generated | `SEED-OPP-{domain}-{n}` |
| `Name` | Generated | `{Account} - {platform tier} ({close month})` |
| `AccountId` | Generated | Seeded Account; ~5 deals per account |
| `Segment__c` | Derived | From Account `NumberOfEmployees`: <200 SMB, 200-2000 Mid-Market, >2000 Enterprise |
| `Employee_Band__c` | Derived | Matches `Segment__c` |
| `Amount` | Derived | 0.05%-0.3% of Account `AnnualRevenue`, kept inside the segment range (SMB 15k-60k, Mid-Market 60k-250k, Enterprise 250k-1.2M). Drawn from the segment range when revenue is blank. |
| `Product_Mix__c` | Synthetic, Apollo-biased | Platform tier weighted by segment, shifted one tier up when `Tech_Stack__c` contains observability tools; add-ons by segment odds. A regulated-industry bias exists but doesn't trigger (all Industry values are the same). |
| `StageName` | Synthetic | 70% Closed Won / 30% Closed Lost within each segment |
| `CloseDate` | Synthetic | Within the last 24 months, relative to the run date |
| `Effective_Discount__c` | Synthetic | SMB 5-20%, Mid-Market 10-28%, Enterprise 18-40%, plus 4 Enterprise outliers at 42-48%. Closed Lost skews toward the low end. |
| `Approver_Level__c` | Derived | From discount and `Segment__c`, using the per-segment bands in `reference/approval_policy.yaml` |
| `Renewal_Outcome__c` | Synthetic | Closed Won only. `Too Early` if closed under 12 months ago; otherwise weighted by discount: <30% about 80% renewed/expanded, 30-40% about 60%, >40% about 50% churned. Blank on Closed Lost. |

Reproducible with `random.seed(42)`, but close dates are relative to today, so
some deals leave `Too Early` as time passes.

## Reference data (not from any external source)

| File | Contents | Status |
|---|---|---|
| `reference/approval_policy.yaml` | Per-segment discount bands, payment terms, pricing-critical fields | **Placeholder** bands: SMB Rep ≤10 / Manager ≤20 / VP ≤25; Mid-Market ≤12 / ≤20 / ≤30; Enterprise ≤20 / ≤28 / ≤35; CFO above the ceiling. Standard terms net30. |
| `reference/price_books.yaml` | Products, billing type (annual / one-time) and per-segment list prices; platform tiers include no seats | **Placeholder** prices |

## Caches

| File | Contents | In git? |
|---|---|---|
| `data/cache/org_{domain}.json` | Raw Apollo organization enrichment (company data only) | No |
| `data/cache/titles_{domain}.json` | Title list and its source; no personal data | No |

Enrichment costs 1 Apollo credit per domain, so reruns read the cache. Use
`--refresh` to re-fetch.
