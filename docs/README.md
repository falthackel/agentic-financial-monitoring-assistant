# Project Details

This page has the full background of the Currency & Asset Price Agent. For setup and running, see the [main README](../README.md).

## Problem statement

Currency and asset data comes from sources with different shapes:

| Data | Source | How often it updates |
|---|---|---|
| Exchange rates (USD, SGD, TWD, EUR, ...) | Frankfurter API v2 | Once per working day |
| Gold and silver (XAU, XAG) | Frankfurter API v2 | Once per working day |
| IHSG (Jakarta stock index) | yfinance (`^JKSE`) | Every minute during market hours |
| Crypto, news, "why did it move?" | DuckDuckGo search | Unstructured text |

A fixed script would need one hard-coded path per question. Here, an LLM agent reads the question and decides which tool to call, whether it needs one call or several, and when to fall back to web search. The same pattern applies outside finance, for example combining clinical or sensor data that updates at different speeds.

## User stories

- As someone paid in TWD who sends money home in IDR, I want a one-line market summary, so I can decide when to transfer.
- As a saver who buys small amounts of gold, I want the gold price per gram in rupiah, so I don't have to convert from USD per ounce myself.
- As a user comparing periods, I want the average rate for Q1 vs Q2, so I can see the trend without a spreadsheet.
- As a curious user, I want to ask "why did TWD go up?" and get an answer based on real news, not a made-up reason.

## Scope

**In scope**
- Latest rates for fiat currency pairs and precious metals
- Average, min and max rates over a date range
- A multi-asset price table in IDR, with % change vs the previous day
- Web search fallback for anything the structured tools can't answer
- Follow-up questions within one session (conversation memory)

**Out of scope**
- Trading or investment advice
- Real-time (per-second) exchange rates. Frankfurter is daily only
- Crypto through structured data. Crypto only goes through web search
- Long-term memory across sessions

## Architecture

```mermaid
flowchart TD
    A["User question (terminal)"] --> B["Agent (Gemini via LangChain create_agent)"]
    B --> C{"Needs a tool?"}
    C -- No --> H["Final answer"]
    C -- Yes --> D["Tool call"]
    D --> E1["get_price_table"]
    D --> E2["get_exchange_rate"]
    D --> E3["get_average_exchange_rate"]
    D --> E4["web_search (fallback)"]
    E1 --> F["Frankfurter API (FX, daily) / yfinance (IHSG, per minute)"]
    E2 --> F
    E3 --> F
    E4 --> G["DuckDuckGo"]
    F --> B
    G --> B
    H --> I["Saved to conversation history (context for the next turn)"]
    H --> J["Tool-call trace written to agent_log.txt"]
    H --> K["Answer printed"]
```

The agent repeats the loop (think, call a tool, read the result) until it has enough information to answer.

Each step is shown live in the terminal, so you can see the agent's choices:

```
You: compare USD and XYZ to IDR
  🔧 get_exchange_rate(from_currency='USD', to_currency='IDR')
  🔧 get_exchange_rate(from_currency='XYZ', to_currency='IDR')
  ✅ get_exchange_rate → 1 USD = ... IDR (as of ...)
  ❌ get_exchange_rate → ERROR: no rate found for XYZ to IDR. ...
```

`✅` / `❌` comes from the `ERROR:` prefix of the tool result. Multi-line results (tables, search results) show the first line plus `(+N lines)`. This uses `agent.stream(..., stream_mode="values")` in `agent.py`, which reports each step through an `on_step` callback; `cli.py` only does the printing.

### Code layout

| File | Role |
|---|---|
| `currency_agent.py` | Entry point. Fixes Windows console encoding, then starts the chat |
| `cli.py` | Terminal loop: reads input, handles `reset` / `exit` / ESC, prints answers |
| `agent.py` | Creates the Gemini model and the LangChain agent, keeps the conversation history, runs one turn (`run_request`) |
| `tools.py` | The 4 tools and their data helpers |
| `prompts.py` | System prompt versions, kept side by side for comparison |
| `trace_log.py` | Writes `agent_log.txt` |

`agent.py` does not print anything itself, so the terminal, the evaluation script and a future UI can all reuse it.

### How the tools work

- **EUR pivot.** Frankfurter publishes rates against EUR. To get USD to TWD, the code fetches EUR to USD and EUR to TWD, then divides them.
- **Gold.** Frankfurter gives gold in ounces. The table shows USD per troy ounce (the usual reference) plus Rp per gram and Rp per 0.01 gram (1 troy oz = 31.1035 g).
- **"Last update" time.** For daily data the table shows the rate date plus the time we checked, because there is no real market time. For IHSG it shows the real market time of the last 1-minute price.
- **Tool errors.** Every tool catches its own errors and returns text that starts with `ERROR:`. The agent can then try another tool instead of crashing. In the price table, one failed asset shows `FAILED` in its row and the rest of the table still works.

### Error handling

| Problem | What happens |
|---|---|
| `GOOGLE_API_KEY` missing or still the placeholder | The program stops at startup with a one-line message |
| Gemini quota / rate limit (429) | "Quota reached, wait a minute" message, chat keeps running |
| Gemini timeout (30 s per request, max 2 retries) | "Took too long, try again" message, chat keeps running |
| Invalid API key | "Check GOOGLE_API_KEY" message |
| Any other failure, or no final answer | Short reason shown, chat keeps running |
| Answer with no text | A fallback message instead of an empty line |
| Ctrl+C while the agent works | Cancels only that question |

In every failure case, the question is **not** saved to the conversation, so the next question starts clean. The full reason is written to `agent_log.txt` as `[AGENT ERROR] <kind>: <reason>`.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| LLM and agent loop | Google Gemini (`gemini-3.5-flash-lite`) via `langchain.agents.create_agent` | Free tier, built-in tool calling |
| FX and metals data | Frankfurter API v2 | Free, no key. EUR-based and daily only, so it needs the pivot logic |
| Stock index data | yfinance (`^JKSE`) | Has per-minute data |
| Fallback search | DuckDuckGo (`ddgs`) | Covers what the other sources don't |
| Config | `.env` + `python-dotenv` | Keeps the API key out of git |

Python 3.10. All package versions are pinned in `requirements.txt`.

## Sample session

*To be added: a real captured session (no made-up numbers).*

## Evaluation

13 test questions in [eval/eval_cases.yaml](../eval/eval_cases.yaml), each with the tools (and arguments) the agent should use. They cover every tool, a follow-up question, an unknown currency code, an off-topic question, a relative date, and a question in Indonesian.

Three separate scores per case:
- **Tool choice + arguments:** the right tool, with the right inputs (e.g. Q1 2026 → `2026-01-01` to `2026-03-31`)
- **Required words:** for "why" questions, the answer must point to the search results
- **Number grounding:** every number in the answer appears in a tool output, or is a difference / % change of two tool numbers

| Prompt | Tool choice pass | Numbers grounded | Main failure |
|---|---|---|---|
| v1 | 12/13 | 13/13 | `causal_why`: causes stated as facts, not attributed to the search |
| v2 | 13/13 | 13/13 | none failed; `causal_why` names sources only loosely ("market reports") |

Full table: [eval/results.md](../eval/results.md). Raw runs (every tool call and answer): [eval/runs/](../eval/runs/).

Run it (uses about 30–45 Gemini requests, so mind the free-tier quota):

```
python eval/run_eval.py                 # run missing cases for v1, then write results.md
python eval/run_eval.py --only crypto   # re-run one case
python eval/run_eval.py --report-only   # rescore saved runs, no Gemini calls
```

The model ignores temperature, so a case can pass on one run and fail on the next. One run per case is a sample, not a guarantee.

## Prompt iteration log

[docs/prompt_iterations.md](prompt_iterations.md) records each prompt change: the failure that caused it (with evidence from the eval), the exact change, and the result after re-running the eval.

In short: v1 stated causes for a currency move as facts, including one that wasn't in any search result. v2 adds a rule to only give reasons found in the search and to say so when the search doesn't explain the move. On the same question v2 found no supporting news, said so, and corrected the question's false premise. Tool choice went from 12/13 to 13/13.

Choose a prompt for the chat with `PROMPT_VERSION` (default `v1`), e.g. PowerShell: `$env:PROMPT_VERSION="v2"; python currency_agent.py`.

## Known limitations

- Exchange rates are daily, not live. On weekends and holidays the latest rate is from the last working day.
- yfinance has no explicit timeout setting. A slow response can make the IHSG row slow.
- `agent_log.txt` is recreated every time the program starts, so it only holds the current session.
- The free Gemini tier has per-minute and per-day limits. When they are hit, the agent shows a "quota reached" message and you have to wait.
