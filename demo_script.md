# Demo Script

A live demo of the agent in 5–8 minutes, plus a 2–3 minute version for the backup recording.

**The story the demo tells:** *"I built an agent with tools, made its reasoning visible, measured it with test cases, and iterated on the prompt based on failures."*

Each question below shows one part of that story. Answers change a little every run (the model ignores temperature), so the script lists **what to point at**, not exact numbers.

---

## Before the demo

**The day before**
- [ ] `git checkout demo-v1` (the frozen demo version) and `pytest`: all tests pass
- [ ] One rehearsal of the full script below (about 15–20 Gemini requests)
- [ ] Backup recording saved locally, and open-able without internet

**30 minutes before**
- [ ] Gemini quota: the free daily quota resets at **16:00 Taiwan time** (midnight US Pacific). If the demo is in the morning, don't use quota the evening before beyond one rehearsal
- [ ] Ask one test question (`USD to TWD rate`) to confirm the key and the quota work
- [ ] Terminal: **Windows Terminal** (not old `cmd`, which may not show emoji), font size 16+, dark theme, window wide enough for the price table
- [ ] Activate the environment: `.venv\Scripts\activate`
- [ ] Clear the screen (`cls`), then start: `python currency_agent.py`. This also starts a fresh `agent_log.txt`
- [ ] Open in a second window, ready to show: `eval/results.md`, `docs/prompt_iterations.md`, and `agent_log.txt`
- [ ] Have this script on paper or a second screen

---

## The demo (6 questions, in this order)

Type each question exactly as written. They are one conversation, so **don't type `reset`** between them (question 2 depends on question 1).

### 1. Market summary: choosing the right tool

```
Give me a market summary for today.
```

**Expect:** `🔧 get_price_table()` once, then a table: USD, SGD, TWD, gold, IHSG.

**Point at:** the single 🔧 line.

**Say:** *"The agent chose the table tool: one call for five assets, instead of five separate rate lookups. Each line starting with 🔧 is the agent's real decision, shown live, not an explanation written afterwards."*

### 2. Follow-up: memory + a different tool

```
How does that SGD price compare with its Q1 2026 average?
```

**Expect:** `🔧 get_average_exchange_rate(... SGD, IDR, 2026-01-01, 2026-03-31)`, then a comparison with a difference and a %.

**Point at:** the dates in the tool call, and the word "that".

**Say:** *"I never said which SGD price, or what dates Q1 means. It understood 'that' from the previous answer, and turned 'Q1 2026' into January 1 to March 31 itself."*

### 3. Gold per gram: a domain detail

```
How much is 1 gram of gold in rupiah?
```

**Expect:** `🔧 get_price_table(assets='XAU')`, then a price in Rp per gram.

**Say:** *"Gold is quoted in US dollars per troy ounce, but people in Indonesia buy it by the gram. The tool converts it, so the agent doesn't do the math itself, which is where models make mistakes."*

*(Skip this one in the short recording.)*

### 4. An unknown code: an error and a fallback

```
What is the rate of XYZ to IDR?
```

**Expect:** `❌ get_exchange_rate → ERROR: ...`, then usually `🔧 web_search(...)`, then an answer saying XYZ is not a real currency and there is no rate.

**Point at:** the ❌ line, and that **no number** appears in the answer.

**Say:** *"The tool failed, which is shown with ❌, and the agent didn't crash. It tried web search as a fallback, then said honestly that there is no rate. The worst thing a finance assistant can do is make up a number, and my evaluation checks every number in every answer against the tool results."*

### 5. A "why" question: the prompt fix

```
Why did the Taiwan dollar get weaker recently?
```

**Expect:** one or more `🔧 web_search(...)` calls, then an answer that names where the reasons come from (e.g. "According to Bloomberg…"), or says that the search doesn't explain it.

**Point at:** the source name in the answer.

**Say:** *"This is the failure my evaluation found. The first prompt version answered 'why' questions with causes stated as facts, one of them not in any search result: it came from the model's memory. I added one rule: only give reasons that are in the search results, say where they come from, and say so if the search doesn't explain it. Now it cites its source."*

**If the answer has no source this time:** *"You can see why I measure this. The model isn't fully repeatable, so one good run isn't proof. That's why it's a test case, not a one-off check."*

### 6. Off-topic: knowing when *not* to use a tool

```
What is an AI agent?
```

**Expect:** no 🔧 line at all, just an answer.

**Say:** *"No tool this time. Part of being an agent is deciding when a tool isn't needed."*

Then press **ESC** to quit.

---

## Closing (1–2 minutes): measured and improved

1. **Open `eval/results.md`**, the summary table.
   *"13 test cases: every tool, a follow-up, an unknown code, an off-topic question, a relative date, and one in Indonesian. Each is scored on tool choice and on whether every number is grounded in a tool result. Version 1 passed 12 of 13; version 2 passes 13 of 13."*
2. **Open `docs/prompt_iterations.md`**, the "Failure 1" section.
   *"Here's the failure, with the actual answer, what I changed, and the result. I also only added rules for failures I actually saw: three 'obvious' rules weren't needed, so I left them out."*
3. **Optional, if there's time:** run `pytest` (it takes about 8 seconds).
   *"51 tests that don't call Gemini at all. They use a fake model, so I can test the error handling for free and safely."*

**One-line summary to end on:** *"Tools for the facts, visible steps so you can trust it, and an evaluation that tells me whether a change actually helped."*

---

## Backup recording (2–3 minutes)

Record the same flow, shorter:

| Time | What | From above |
|---|---|---|
| 0:00–0:15 | One sentence: what the agent does | "It answers currency and asset questions in rupiah, choosing between four data tools." |
| 0:15–0:45 | Question 1 (table) | point at the single 🔧 |
| 0:45–1:15 | Question 2 (follow-up) | point at "that" and the dates |
| 1:15–1:40 | Question 4 (XYZ) | point at ❌ and the fallback |
| 1:40–2:10 | Question 5 (why) | point at the source |
| 2:10–2:45 | `eval/results.md` + `docs/prompt_iterations.md` | v1 12/13 → v2 13/13 |

Tips: record at 1080p, zoom the terminal font, and do one or two takes. Keep a take where something small goes wrong if the recovery looks good: a ❌ followed by a fallback *is* the feature.

---

## If something goes wrong live

| Problem | What you'll see | What to do |
|---|---|---|
| Gemini quota / rate limit | `⚠️ Gemini quota or rate limit reached (429)...` | Say *"That's the error handling: a clear message, and the chat keeps running."* Wait a minute and retry once. If it fails again, switch to the backup recording |
| Gemini is slow | Nothing for 10–30 s | Keep talking about the 🔧 lines. The timeout is 30 s, after which a clear message appears |
| A web search fails | `❌ web_search → ERROR: ...` | Normal. The agent usually retries with another search. Point at it as the fallback |
| An answer has no text | `(The model returned no text answer...)` | Ask the same question again |
| Something else breaks | Python error | Switch to the backup recording, then show `eval/results.md` and `docs/prompt_iterations.md`. They don't need Gemini |

**Quota budget:** the full script uses about 15–20 Gemini requests. One rehearsal plus the live demo is well within the free daily limit. Don't run the full evaluation on the demo day.
