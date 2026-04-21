# Serai
 
**More signal. Less noise. For people who aren't looking — yet.**
 
---
 
Last week I told seven employed people at a meetup I was building a job search tool for people who aren't looking. All seven were the target user. Two asked to see it. Here it is.
 
I spent 14 years at Atlassian. Six of them stuck at the same level, comfortable, not looking. I told myself the grass wasn't greener. I was wrong — I just never looked.
 
When I finally did look, I found every job tool was built for volume: more alerts, more applications, faster. That's fine if you need any job. It's the wrong tool if you're looking for the right one.
 
Serai discovers companies automatically — scanning Greenhouse, Ashby, Workday, and Y Combinator job boards for companies that match your archetype, then scoring each one against weighted dimensions you define. You don't hardcode a list of companies to watch. Serai finds them, evaluates them, and promotes the ones worth tracking. Roles at those companies are scored against your resume. The ones that pass both thresholds land in your Notion board. The rest are filtered out. Most weeks, you see nothing. That's the point.
 
---
 
## How it works
 
Serai runs two loops:
 
**Company discovery** (`run_company_discovery.py`) finds new companies you've never seen:
 
1. **Discovers** companies across Greenhouse, Ashby, Workday, and YC job boards using configurable search patterns
2. **Scores each company** against your candidate profile on six dimensions with your chosen weights
3. **Promotes** companies scoring above threshold into your active registry — no manual curation needed
4. **Evaluates roles** at discovered companies, filtering by title, location, and compensation
5. **Routes** each role: Apply / Network / Review / Skip — based on weighted fit + company score
6. **Writes** passing roles to your Notion board
**Recurring scan** (`eval_llm_scoring.py`) monitors your active companies every 3 hours:
 
1. **Scans** ATS boards for new postings at companies in your registry
2. **Scores role fit** — strength overlap, role interest, level fit, title match
3. **Grounds scores in recent signals** — Brave Search pulls the last 12 months of news, funding rounds, and leadership changes so scores reflect reality, not stale training data
4. **Routes and writes** passing roles to Notion with alert priority
Companies flow from discovery → evaluation → your board. You define what "good" looks like. Serai finds it.
 
## Who Serai is for
 
- Senior operators (PM, engineering, design, growth) with 5-15 years of experience
- People employed and not actively looking, but who don't want to miss the rare role worth moving for
- People between roles who refuse to apply to 300 postings for one offer
- Anyone who thinks job search signal-to-noise is broken
## Who Serai is not for
 
- Need a paycheck in 90 days? Use Simplify, Teal, or LinkedIn alerts. Serai is built for selectivity, not speed.
- Want a polished UI? Serai is a Python pipeline writing to Notion. v1 is for people who can read the code. v2 is for everyone else.
---
 
## Architecture
 
Serai separates what's universal from what's personal:
 
```
┌─────────────────────────────────────────────────────┐
│  Company Discovery                                  │
│  Pattern-based ATS + YC scanning, automatic         │
│  promotion of high-scoring companies                │
├─────────────────────────────────────────────────────┤
│  Generic Prompt (same for all users)                │
│  Evaluation discipline, confidence rules,           │
│  anti-bias clauses, scoring bands                   │
├─────────────────────────────────────────────────────┤
│  Candidate Profile (yours)                          │
│  Role, dimensions, weights, anchor companies,       │
│  disqualifiers, hard constraints                    │
├─────────────────────────────────────────────────────┤
│  Routing Logic (code)                               │
│  LLM scores dimensions → Python computes weighted   │
│  sums, enforces anchors, checks disqualifiers,      │
│  assigns routes                                     │
└─────────────────────────────────────────────────────┘
```
 
**The key design decision:** the LLM evaluates each dimension independently and returns six scores. It never computes the final score — Python does the math. This eliminates a class of errors where the model rounds toward prestige-friendly numbers or lets one dimension bleed into another.
 
Your candidate profile defines everything personal: which dimensions matter, how much each one weighs, what "good" looks like (anchor companies at every band), and what's an automatic skip (disqualifiers). A PM weights product culture at 0.20. A sales leader drops it and adds sales_motion. Same prompt, different profile.
 
### Per-dimension scoring
 
Serai evaluates companies on six dimensions by default. You can add, remove, or reweight dimensions by editing your candidate profile — no code changes needed.
 
| Dimension | What it measures | Default weight |
|---|---|---|
| Moat durability | Distribution, network effects, data, switching costs | 0.25 |
| Growth trajectory | Revenue growth, funding, market momentum | 0.20 |
| Product culture | PM ownership, product-led decision making, CPO presence | 0.20 |
| AI leverage | How effectively the company uses AI in its product | 0.15 |
| Leadership quality | Executive credibility, stability, track record | 0.10 |
| Market category | Category growth, tailwinds, TAM trajectory | 0.10 |
 
Each dimension is scored 1-10, calibrated against anchor companies you place at each band. A 9 means the company's evidence matches your named 9-10 anchors. A 4 means it looks like your named 3-4 anchors. The anchors define the scale — not abstract criteria.
 
### Anchor calibration
 
Anchors are the core calibration mechanism. In your candidate profile, you place real companies at score bands for each dimension:
 
```
moat_durability (weight: 0.25)
  9-10: elite distribution + data moat (Atlassian, Stripe)
  7-8:  strong product-led distribution (Ramp, Linear)
  5-6:  moderate moat, contestable position (Anthropic, OpenAI)
  3-4:  weak or eroding moat (ZoomInfo, Jasper)
  1-2:  no meaningful moat (Jasper)
```
 
The LLM uses these anchors to calibrate every score. Code-side enforcement clamps scores to anchor bands as a backstop, so even when the model drifts, named companies always land in the right range.
 
### Signal grounding
 
Company scores are supplemented by real-time web signals via Brave Search. This prevents stale training data from producing wrong scores — a company that did layoffs last month shouldn't score the same as it did a year ago.
 
Signal routing rules control which dimensions signals can inform. Funding news updates growth trajectory. It does not update moat durability or product culture, which require structural evidence. This prevents positive press from inflating all dimensions uniformly.
 
### Company discovery
 
You don't maintain a hardcoded list of companies. Serai discovers them automatically by scanning ATS boards (Greenhouse, Ashby, Workday) and Y Combinator's job board using configurable search patterns. Each discovered company is scored against your candidate profile. Companies that score above the promotion threshold (default 7.0) and have matching roles are automatically added to your active registry for recurring monitoring. Companies below the watchlist threshold (default 6.0) are rejected. Everything in between sits on a watchlist until stronger signal arrives.
 
The discovery loop also handles YC jobs end-to-end: fetch, filter by title/location/comp, score the company, score the role, route, and write to Notion — all in one pass.
 
### Disqualifiers
 
Candidate-specific disqualifiers (e.g., "consumer social / gaming", "legacy enterprise sales org") let you skip entire company categories regardless of score. The LLM flags potential matches, and code-side detection provides a backstop using known company sets and keyword matching. Disqualifiers don't affect dimensional scores — a consumer gaming company can still score well on moat and growth. The disqualifier overrides routing, not evaluation.
 
---
 
## Setup
 
1. Clone this repo
2. `pip install -r requirements.txt` (Python 3.10+)
3. Copy `.env.example` → `.env`, fill in API keys (OpenAI, Brave Search, Notion)
4. Copy `config.example.yaml` → `config.yaml`, customize filters (locations, salary, levels)
5. Edit `candidate_data/candidate_profile.txt` with your role, dimensions, weights, and anchor companies (see `examples/` for templates). Optional profile blocks: `=== COMPANY DISCOVERY CONFIG ===` … (`adjacent_title_keywords`, `broad_sweep_titles`) for ATS discovery — see `discovery_patterns.py` defaults if omitted; `=== EVAL UNKNOWN-BUCKET TITLE SUBSTRINGS ===` … (JSON array) for substring gates when `title_bucket` is unknown in eval/YC flows — see `role_title_gates.py` defaults if omitted; `=== JOB FILTER CONFIG ===` … (JSON object: title/geo/comp lists and `min_acceptable_max_comp`) for pre-LLM filtering — see `job_filter_config.py` defaults if omitted.
6. Create your Notion database (see below)
7. `python run_company_discovery.py` to discover and score companies automatically
8. `python eval_llm_scoring.py` to scan for roles at your active companies
9. Set up recurring runs — on macOS use the launchd plist files in `deploy/`, on Linux use `deploy/crontab.example`. macOS cron is deprecated and may not run reliably. If using launchd, make the shell scripts executable first: `chmod +x deploy/run_discovery.sh deploy/run_eval.sh`
### Notion database setup
 
Create a new Notion database with these properties. Names and types must match exactly — the system writes to these fields directly.
 
| Property | Type | Purpose |
|---|---|---|
| Final Recommendation | Select | Route: Apply / Network / Review / Skip |
| Title | Text | Role title |
| Company | Text | Company name |
| URL | URL | Link to the job posting |
| First Seen | Date | When Serai first discovered this role |
| Location | Text | Role location |
| Comp Min | Number | Minimum base compensation |
| Comp Max | Number | Maximum base compensation |
| Apply Score | Number | Weighted fit score (computed by Serai) |
| Why Strong | Text | Top reasons this role scored well |
| Main Reservation | Text | Primary concern or risk |
 
After creating the database, copy its ID into your `.env` file as `NOTION_DATABASE_ID`. You'll also need a [Notion integration](https://www.notion.so/my-integrations) with write access to the database — add the integration's API key as `NOTION_API_KEY` and make sure the integration is connected to your database in Notion. 
 
Setup time: ~30 minutes with API keys ready. Writing good anchors takes another 30-60 minutes but dramatically improves calibration.
 
### API keys you'll need
 
| Service | Purpose | Cost |
|---|---|---|
| OpenAI | LLM scoring (gpt-4o-mini) | ~$0.01-0.02 per company eval |
| Brave Search | Real-time signal grounding | Free tier covers typical usage |
| Notion | Results dashboard | Free plan works |
 
---
 
## How Serai is different from other AI job tools
 
Serai is not an application tool. It's a company evaluation tool.
 
Tools like AiApply, Sonara, and Jobright are built for volume — they help you apply to hundreds of roles faster with auto-apply, resume tailoring, and cover letter generation. They answer the question "does this role match my resume?" and they're good at it.
 
Serai answers a different question: "is this company the kind of place where I'd actually want to spend the next 3-5 years?" It evaluates companies on weighted dimensions, calibrated against anchor companies you define, grounded in real-time signals. No other job search tool does per-dimension company scoring with anchor calibration and signal routing.
 
The tools are complementary. Use Serai to find the right companies. Use whatever application tool you prefer to optimize your applications to them.
 
---
 
## Known limitations
 
- **Signal quality varies.** Brave Search grounding works well for well-known companies but can miss niche startups. Confidence ratings flag where evidence is thin.
- **Token usage.** Per-dimension scoring asks the LLM for six scores per company — more tokens than a single gestalt score. The tradeoff is much better calibration.
- **Profile investment.** The candidate profile requires thought. Writing good anchors is the difference between useful scores and noise. Templates in `examples/` help you get started.
- **No UI.** Serai is a Python pipeline. You interact with results through Notion and configure it through text files. This is intentional for v1.
## Roadmap
 
- **v1.2:** `bin/generate_profile.py` — upload your resume + describe what you want, get a draft candidate profile to review and edit
- **v1.3:** Alternative alerting (Slack, email) beyond Notion
- **v1.3:** Historical accuracy tracking — did companies scored 8+ actually break out?
- **v2.0:** Hosted version with resume-to-profile onboarding (if demand warrants)
---
 
## Credits
 
Built by [Alex Kassab](https://linkedin.com/in/alexandrakassab) during a job search. If Serai surfaces something interesting for you, I'd love to know.
 
## License
 
MIT







































