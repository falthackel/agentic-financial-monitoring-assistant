# Prompt Iteration Log

Each prompt change is listed with the failure that caused it, the evidence, the change, and the measured result. Prompts live in [prompts.py](../prompts.py). Eval results are in [eval/results.md](../eval/results.md), and the raw runs (every tool call, result, and answer) are in [eval/runs/](../eval/runs/).

**Rule for this log:** a rule is only added when the eval or the log shows a failure it fixes. Candidate rules with no observed failure are listed at the end, not added.

---

## Summary

| Version | Date | Change | Tool choice | Numbers grounded |
|---|---|---|---|---|
| v1 | 2026-11-11 | Original prompt, translated to English | 12/13 | 13/13 |
| v2 | 2026-11-11 | + Rule A (cite search for "why" questions), + Rule B (past-date tool) | **13/13** | 13/13 |
| v2 (re-run) | 2026-11-11 | No prompt change. Tool fix: IHSG history; 2 new cases | **15/15** | 15/15 |

Model: `gemini-3.5-flash-lite`. One run per case per version. The model ignores temperature, so results vary between runs (see [Limits](#limits-of-this-evidence)).

---

## Failure 0 (before the eval): a fake reason in the log (K3)

**Observed.** The original `web_search` tool wrote this line to the log *every time* it ran:

> `↳ [KENAPA] tool data terstruktur sebelumnya tidak bisa menjawab, agent memutuskan mencoba mencari di internet`
> ("[WHY] the previous structured data tool could not answer, so the agent decided to search the internet")

It was hard-coded, not taken from the agent. In a Sep 16 session the agent went straight to web search for a "why" question after a *successful* rate lookup, so the log claimed a reason that wasn't true.

**Evidence.** Baseline commit `8a68834`, `currency_agent.py` lines 371–372. (The Sep 16 log file itself was overwritten by a test script on Nov 11, see the dev log.)

**Fix.** Code, not prompt: the line was deleted (`7628b4e`). The terminal and the log now show only the agent's real actions: which tool, which arguments, which result (M2).

**Why it matters.** It is the same problem as Failure 1 below, a reason that sounds right but isn't grounded. The log and the agent's answers should both only claim what actually happened.

---

## v1 → v2

### v1 prompt

```
Today is {TODAY}. You are an assistant that helps answer questions about currency
exchange rates and asset prices. ALWAYS use the available tools to get numbers.
Never guess or use data from your memory.

Use get_price_table when the user asks for a 'price update', a 'market summary', or
a list of several assets at once. Use get_exchange_rate only for one specific
currency pair. Use get_average_exchange_rate for averages or comparing periods.

IMPORTANT: if a structured data tool fails, do NOT give up right away. Try the
web_search tool as an alternative.

If the question has nothing to do with exchange rates or asset prices, answer
normally without calling a tool.
```

### Failure 1: causes stated as facts, not tied to the search (`causal_why`)

**Question:** "Why did the TWD get stronger recently?"

**v1 behavior.** Three searches. Only one result was on topic (Taiwan's central bank denying US pressure on the currency); the others were currency-converter pages and a 2008 article. The answer still listed three causes as plain facts:

> "The recent sharp appreciation of the New Taiwan Dollar (TWD) ... has been driven by several key factors: 1. **Market Speculation and Tariff Talks** ... 2. **Capital Inflows and Trade Surpluses:** ... powerhouse technology and semiconductor sector (such as giants like TSMC supplying global AI and tech demand) ... 3. **External Pressure** ..."

- No claim says where it came from.
- Cause 2 (TSMC, AI demand) is in **none** of the search results. It came from the model's memory, which the prompt says never to use.
- The eval check (answer must mention search / according / report / news / source / article) **failed**.

**Diagnosis.** v1 says "never use data from your memory", but only for *numbers* ("to get numbers"). Nothing tells the model how to handle *reasons*, or what to do when the search doesn't answer the question.

### Failure 2: an unneeded extra tool call (`relative_date`)

**Question:** "What was the USD to TWD rate last Monday?"

**v1 behavior.** First `get_exchange_rate(USD, TWD)` (today's rate, not what was asked), then `get_average_exchange_rate(USD, TWD, 2026-11-09, 2026-11-09)`. Correct answer, but one wasted tool call and one extra LLM round-trip, which matters on the free tier. The case passed, so this is an efficiency issue, not a correctness one.

**Diagnosis.** No tool says it can look up one past date. The model only found the trick (average with start = end) after trying the wrong tool.

### v2 change

v2 = v1 + two paragraphs:

```
For questions about WHY a price or currency moved, or about news, use web_search. In
your answer, only give reasons that appear in the search results, and say which
source each reason comes from (for example, 'According to Taiwan News, ...'). If the
results don't explain the move, say so plainly instead of guessing.          ← Rule A

For the rate on one past date, call get_average_exchange_rate with start_date and
end_date both set to that date. get_exchange_rate only gives the latest rate.  ← Rule B
```

### v2 result

| Case | v1 | v2 |
|---|---|---|
| `causal_why` | ❌ causes stated as facts, one from memory | ✅ every claim found in the search results |
| `relative_date` | ✅ but 2 calls | ✅ 1 call |
| other 11 cases | ✅ | ✅ (no regressions) |
| **Total tool choice** | **12/13** | **13/13** |

**`causal_why` in v2.** The searches were even worse this time. The first returned pages about **The Walking Dead** ("TWD"), the second CNN's front page. One result said the Taiwan dollar had actually *weakened*. The v2 answer:

> "Based on recent financial data and market reports, the available search results actually indicate that the New Taiwan Dollar (TWD) has generally been under depreciation pressure rather than getting stronger recently (with the Taiwanese dollar trading around 32.2 to 32.85 per US dollar, pressured by a stronger US dollar and capital outflows). Because the search results do not show a recent period of TWD strengthening, there are no specific news reports available explaining why it got stronger."

Checked by hand against the raw search results (`eval/runs/v2.json`):
- "depreciated to around 32.2 per US dollar ... pressured by a stronger US dollar and seasonal capital outflows" appears word for word in one result. "32.85" is in a Macrotrends result (Nov 6).
- It didn't invent a cause, and it corrected the question's false premise. Our own tool agrees: 1 USD = 32.88 TWD on Nov 11, a weak TWD.
- **Still not perfect:** it says "market reports" instead of naming the source, so it followed Rule A's "say which source" only loosely.

**`relative_date` in v2.** One call: `get_average_exchange_rate(USD, TWD, 2026-11-02, 2026-11-02)`. But v2 read "last Monday" (asked on Wednesday Nov 11) as **Nov 2**, while v1 read it as **Nov 9**. Both are valid English readings and both are accepted by the eval. v2 named the date in its answer ("Last Monday (November 2, 2026)"), so the user can see which one it used.

### Evaluation fixes made during this iteration

The checker was wrong a few times. Each fix was applied to **both** versions before comparing:

| Fix | Why | Effect |
|---|---|---|
| Mark differences / % changes of two structured-tool numbers as "computed" | v1 `compare_q1_q2` said "+21.19 IDR (3.97%)". That is correct arithmetic (554.962 − 533.77), not an invention | v1 grounded 12/13 → 13/13 |
| Treat large round numbers as rounded (3+ significant digits only) | v2 `crypto` said "Rp 1,339,000,000", the search said Rp 1,339,621,582 | v2 crypto flag removed |
| Ignore "ISO 4217" | v2 `unknown_code` said "not an ISO 4217 code". That's a standard's name, not a value | v2 unknown_code flag removed |

All three were checked by hand first, and each has a unit test (`tests/test_eval.py`), including one that keeps "16,000" vs 16,900 flagged.

### Limits of this evidence

- **One run per case.** The model ignores temperature, so `causal_why` could pass or fail on another run with either prompt. 1/1 vs 0/1 is a signal, not proof. Running `causal_why` several times per version would make it stronger.
- **The word check is easy to game.** Rule A says "According to ...", and the check looks for "according". So the hand check of every claim against the search results is the real evidence here, not the ✅.
- **The search query is a weak spot.** "TWD" matched The Walking Dead. Neither prompt tells the model to spell out currency names in search queries.

---

## After v2: a tool fix and a re-run (no prompt change)

**IHSG history (rehearsal finding F1).** A rehearsal showed the agent couldn't answer IHSG history questions. This was a tool gap, not a prompt problem: the history tool only asked a currency API. `get_average_exchange_rate` now also covers IHSG (from yfinance), and its description says so. Two eval cases were added. **v2 re-run on all 15 cases: 15/15 tool choice, 15/15 grounded, no regressions.** The tool descriptions are part of what the model reads, so v1's results (13 cases, old descriptions) are not a like-for-like comparison with this run.

**Finding F2: an invented source name.** In this re-run, `causal_why` passed the eval, but a hand check found:

> "According to recent reports (such as from *Focus Taiwan* or similar financial news updates), a strong rally in Taiwan stocks has driven the TWD to reverse its depreciation trend…"

Both causes are in the search results. "Focus Taiwan" is **not**. The real cause is in the tool, not the prompt: `web_search` gives the model each result's title and text, but not the website. Rule A asks the model to name sources it was never given, so it either stays vague ("market reports", first v2 run) or guesses (this run).

**Lesson:** a prompt rule can only be followed if the tools supply what the rule needs. Planned fix: include each result's site in the `web_search` output, and add an eval check that every source named in an answer appears in the search results.

---

## Candidate rules not added (no failure observed)

| Candidate | Why not added |
|---|---|
| "Never state a number that does not appear in a tool result." | v1 grounded 13/13 already. The existing "never guess or use data from your memory" covers it |
| "If all tools fail, say the data is unavailable." | v1 `unknown_code`: the tool failed, the agent searched, then said the rate was not available. No invented number |
| "Answer in the user's language." | v1 answered the Indonesian question in Indonesian |

## Ideas for v3 (not done)

- **Search queries:** "write currency names in full in search queries (e.g. 'Taiwan dollar', not 'TWD')". This would fix the Walking Dead results.
- **Named sources:** require the site name for each reason, and check that the name appears in the search results.
- **Ambiguous dates:** state the date used, and mention the other reading ("last Monday" = Nov 9 or Nov 2).
