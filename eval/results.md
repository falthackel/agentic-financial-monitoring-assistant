# Evaluation Results

Generated 2026-11-11 20:14 by `python eval/run_eval.py`. Cases: [eval_cases.yaml](eval_cases.yaml). Raw runs: [runs/](runs/).

**How to read this**
- **Result** checks tool choice and arguments (plus a required word in the answer for some cases).
- **Numbers** is a separate check: ✅ means every number in the answer appears in a tool output. "computed" marks numbers that are a difference or % change of two tool numbers (correct arithmetic, not copied). ⚠️ lists numbers found nowhere: possibly invented, so they need a human look.
- The model ignores temperature, so results can change between runs. One run per case is a sample, not a guarantee.

## Summary

| Prompt | Model | Run | Result pass | Numbers grounded | Errors |
|---|---|---|---|---|---|
| v1 | gemini-3.5-flash-lite | 2026-11-11 | 12/13 | 13/13 | 0 |

## Per case

| Case | Question | Expected tools | v1 called | v1 result | v1 numbers |
|---|---|---|---|---|---|
| `single_pair` | What is the USD to IDR rate now? | get_exchange_rate | get_exchange_rate(USD, IDR) | ✅ pass | ✅ |
| `market_summary` | Give me a market summary for today. | get_price_table | get_price_table(USD,SGD,TWD,XAU,IHSG) | ✅ pass | ✅ |
| `subset_table` | What is the price of gold and IHSG? | get_price_table | get_price_table(XAU,IHSG) | ✅ pass | ✅ |
| `average_q1` | What was the average SGD to IDR rate in Q1 2026? | get_average_exchange_rate | get_average_exchange_rate(SGD, IDR, 2026-01-01, 2026-03-31) | ✅ pass | ✅ |
| `compare_q1_q2` | Compare the TWD to IDR rate in Q1 vs Q2 2026. | get_average_exchange_rate | get_average_exchange_rate(TWD, IDR, 2026-01-01, 2026-03-31), get_average_exchange_rate(TWD, IDR, 2026-04-01, 2026-06-30) | ✅ pass | ✅ (computed: 21.19, 3.97) |
| `crypto` | What is the bitcoin price in IDR? | web_search | web_search(bitcoin price in IDR today), web_search(current bitcoin price in IDR CoinMarketCap) | ✅ pass | ✅ |
| `causal_why` | Why did the TWD get stronger recently? | web_search | web_search(TWD strengthened reasons 2026 Taiwan dollar currency appreciation), web_search(Taiwan dollar appreciation reasons recent news TWD strong), web_search(why did Taiwan dollar appreciate sharply causes factors) | ❌ fail | ✅ |
| `follow_up` | What is the USD to IDR rate? → What about SGD? | get_exchange_rate | get_exchange_rate(SGD, IDR) | ✅ pass | ✅ |
| `unknown_code` | What is the rate of XYZ to IDR? | get_exchange_rate | get_exchange_rate(XYZ, IDR), web_search(XYZ currency to IDR exchange rate) | ✅ pass | ✅ |
| `off_topic` | What is an AI agent? | (no tool) | (none) | ✅ pass | ✅ |
| `gold_gram` | How much is 1 gram of gold in rupiah? | get_price_table | get_price_table(XAU) | ✅ pass | ✅ |
| `relative_date` | What was the USD to TWD rate last Monday? | get_average_exchange_rate | get_exchange_rate(USD, TWD), get_average_exchange_rate(USD, TWD, 2026-11-09, 2026-11-09) | ✅ pass | ✅ |
| `indonesian_question` | Berapa kurs SGD ke IDR hari ini? | get_exchange_rate | get_exchange_rate(SGD, IDR) | ✅ pass | ✅ |

## Problems found

### v1 · `causal_why`
- answer mentions none of: search, according, report, news, source, article
- answer: "The recent sharp appreciation of the New Taiwan Dollar (TWD) against the U.S. Dollar has been driven by several key factors: 1. **Market Speculation and Tariff Talks:** A primary driver behind the rapid surges has been heavy market speculation closely tied to ongoing trade and tariff negotiations be..."

