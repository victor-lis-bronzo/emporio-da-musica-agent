# Empório da Música — Customer Service Agent

Prototype of a text-based customer service agent for **Empório da Música**, a fictional musical instrument store in Campo Grande/MS (Brazil). The agent talks to customers in Portuguese (pt-BR) and decides on its own when to query store data (products, prices, stock, promotions, orders) and when to consult the store's policy manual (returns, hours, payment, shipping, warranty).

> Technical case for the AI Engineer role at Artefact. Code and docs are in English; the agent speaks Portuguese.

## How to run

Requirements: [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 and the dependencies) and a free [Groq](https://console.groq.com) API key.

```bash
uv sync
cp .env.example .env        # then put your key in GROQ_API_KEY
uv run emporio-da-musica-agent
uv run pytest               # tests for the tools (no API key needed)
uv run python evals/run_scenarios.py   # optional: 41 scripted scenarios against the real model (needs the API key)
```

Inside the chat: `/nova` starts a new conversation, `/salvar` saves it to `examples/` as markdown, `/sair` quits. Every tool the agent decides to call is printed as `[consultando ...]`.

`.env` variables: `GROQ_API_KEY`, `BASE_URL` (default Groq), `MODEL` (default `openai/gpt-oss-120b`). Any OpenAI-compatible provider works by changing these.

## Architecture

```
cli.py → agent.py (function-calling loop) → LLM (OpenAI SDK, Groq endpoint)
              │ model requests a tool
              ▼
         tools.py ── db.py (in-memory SQLite loaded from the CSVs)
                  └─ data/policies/NN_*.md (one file per policy section)
         prompts.py: persona, rules, assumptions, current date/time
```

## Technical decisions

| Decision | Choice | Why |
|---|---|---|
| Agent approach | Plain function calling, hand-written loop (max 5 iterations per message) | The core of the case is "decide when to query what". The loop is ~40 lines and fully visible. A framework (LangGraph) would add abstractions without adding behaviour at this size. |
| Model / provider | Groq free tier through the `openai` SDK (`openai/gpt-oss-120b`) | Free for whoever runs it, supports tool calling, and switching provider is a `.env` change. HTTP 429 is retried by the SDK (`max_retries=5`). |
| Store data | CSVs loaded into in-memory SQLite; each need is a tool with a **fixed, parameterised SQL query** | The model never writes SQL: no injection, it cannot read other customers' data, results are predictable and testable. |
| Policies | Manual extracted once from the PDF (`scripts/extract_policies.py`) into one file per section; a `get_policy(section)` tool returns only the requested section | The whole manual would cost ~3K tokens on every call (the free tier is ~8K tokens/min). Embeddings are overkill for 10 sections. Each consultation is visible in the log. |
| Business rules in code | Only sellable products are suggested (active and in stock); PIX 5% is only offered when there is no active promotion; order lookup needs order number + matching e-mail/phone | Rules that must never fail live in code (and tests), not in the prompt. |
| Privacy (LGPD) | `get_order` returns the same neutral error for an unknown order and a wrong contact | Does not reveal whether an order exists. |
| Prompt | In Portuguese; persona from policy §7.1 ("informal but professional, like a friend who knows music"), service flow from §7.2, hard rules, documented assumptions | Same language as the conversation avoids translated-sounding answers. |
| Current date | Injected in the system prompt (America/Campo_Grande) | Needed for opening hours, late orders and return deadlines; a tool could be forgotten by the model. |
| Interface | CLI | The focus is the agent, and it runs with one command. |
| History | In memory during the session; saving to disk is explicit (`/salvar`) | Conversations may contain personal data. |

## Assumptions

The provided data has inconsistencies (some on purpose, I believe). How the agent handles them:

| Issue | Assumption |
|---|---|
| Two WhatsApp numbers: (67) 3341-4444 (§1.2) and (67) 3321-4500 (§7) | Use (67) 3341-4444, from the company data section |
| Instalments: table says min. R$100 per instalment; §3.1 has tiered minimums | §3.1, the detailed rule, prevails |
| 7-day return window counts from receipt, but orders only have `estimated_delivery` | Use the estimate as an approximation and tell the customer it is an estimate |
| PIX 5% vs promotions | Not cumulative (§6.2); the tools never return a PIX price for a promoted product |
| Product 96 (stock 0), 113 and 136 (discontinued), 130 (coming soon) | Never suggested; the agent says so when asked and offers similar products |
| Many promotions are inactive (only 4 of 25 are active) | Only active ones are used; an expired promotion is acknowledged and the current price given |
| Order totals that do not match their items (orders 3 and 20) | The stored `total_brl` is shown, never recalculated |
| Order 3 was delivered with a `coming_soon` product | Left as is (data quality issue) |
| Customers with similar names | No lookup by name; order number + e-mail or phone required |
| "Today" for late orders and opening hours | Real current date/time in America/Campo_Grande |
| No wind, orchestral string or accessory products in the catalog | The agent says it is not in the catalog / the store does not sell accessories |

## Example conversations

In [`examples/`](examples/), generated with the CLI's `/salvar` (tool consultations appear as quotes):

1. `01-catalogo-violoes.md` — catalog search with price filter
2. `02-horario-e-endereco.md` — policy lookup + current time (store closed on Sunday)
3. `03-preco-pix-e-promocao.md` — **non-trivial:** PIX discount applied, then refused for a promoted product
4. `04-devolucao-com-verificacao.md` — **non-trivial:** identity check (wrong e-mail, then right one) and return/warranty deadlines applied to the order date
5. `05-fora-do-escopo.md` — accessory request, unrelated topic, and a sold-out product with alternatives

## Known limitations and next steps

- Product search by name is a simple `LIKE`; typos or nicknames ("GD20" works, "violão da Takamine" may not).
- The model sometimes answers from the prompt instead of calling a tool when the rule is written there (e.g. return deadlines). Moving those rules out of the prompt into `get_policy` only would be safer.
- The current time is fixed when the conversation starts.
- Long conversations may hit the free tier's tokens-per-minute limit; next step is summarising old turns.
- Evaluation is semi-automatic: `evals/run_scenarios.py` runs 41 scripted scenarios against the real model, and the transcripts were judged by an LLM (not a human) against the data, see `evals/report.md`. First run: 33 PASS / 7 PARTIAL / 1 FAIL; after the fixes, the 8 non-passing scenarios were re-run: 37 PASS / 4 PARTIAL. Still open: alternatives for a discontinued 7-string guitar are not 7-strings, Black Friday is stated as fact without saying nothing is active now, the defect-exchange answer invents a return procedure, and a late order is not always flagged as late. The other 33 results were not repeated after the fixes. With more time: automatic assertions on tool calls and a human review of the judgments.
- Answers vary between runs (LLM); the examples are real runs, not curated outputs.
- Next steps: LangGraph once the tool set grows, embedding retrieval if the policies grow, a web UI, persistent history with consent, handoff to a human agent.

## Use of AI coding assistants

I used **Claude Code** (CLI) throughout, as a pair programmer, with this workflow:

1. **Analysis first:** Claude read the case statement and audited the CSVs and the policy PDF to list the traps (stock 0, inactive promotions, PIX not stacking, contradictory phone numbers and instalments, orders with wrong totals, LGPD).
2. **Decisions before code:** each technical choice was discussed and recorded as a short decision record before implementing.
3. **Step-by-step implementation:** one small step per commit (database, tools, tests, prompt, agent loop, CLI). Claude drafted the code, explained it, and I reviewed and ran it.
4. **Test-driven checks:** the business rules are covered by `pytest`. Then I ran 10 manual questions against the real model; the problems found (invented services, tables in a chat context, wrong name taken from an e-mail, deadlines not compared to today's date) were fixed in the prompt in separate commits. After that, I had Claude write 41 scripted scenarios (`evals/scenarios.json`, runner `evals/run_scenarios.py`) and judge the transcripts into `evals/report.md`; the failures found (a schema error with no recovery, silent truncation at 10 results, invented reservation service, skipped order lookup) were fixed in three more commits.

## Data

The `data/` folder contains the material provided by the store:

| File | Content |
|---|---|
| `products.csv` | Catalog: price, category, stock, status, specs |
| `categories.csv` | Product categories |
| `promotions.csv` | Promotions per product (active or inactive) |
| `customers.csv` | Customer contact data |
| `orders.csv` / `order_items.csv` | Orders, status, tracking and items |
| `politicas_da_loja.pdf` | Internal customer service policy manual |
| `policies/` | The manual extracted to markdown, one file per section (`scripts/extract_policies.py`) |
