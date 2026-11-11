# Currency & Asset Price Agent

A terminal chat assistant that answers questions about exchange rates and asset prices in Indonesian rupiah (USD, SGD, TWD, gold, and the IHSG stock index). It is an **AI agent**: for each question, Gemini decides which data tool to call, and falls back to web search when the structured data can't answer.

## 1. Project background

Financial data comes in different shapes. Exchange rates are published once a day, a stock index changes every minute, and some assets (like crypto) are not covered by either source. Instead of hard-coding one API call per question, this project lets an LLM agent choose:

- **which tool** fits the question (one rate, an average over time, a full price table, or a web search),
- **how to combine** sources with different update speeds,
- **when to fall back** to a web search if a tool fails.

Built with **LangChain** (`create_agent`) and **Google Gemini**, using free data from the **Frankfurter API**, **yfinance**, and **DuckDuckGo**.

More detail (scope, architecture diagram, limitations, evaluation): [docs/README.md](docs/README.md)

## 2. Project directory

```
.
├── currency_agent.py   # Start here: runs the terminal chat
├── cli.py              # Terminal input/output (ESC or 'exit' to quit, 'reset' to clear)
├── agent.py            # Gemini model + LangChain agent + conversation memory
├── tools.py            # The 4 tools the agent can call (see below)
├── prompts.py          # System prompt versions
├── trace_log.py        # Writes each tool call and result to agent_log.txt
├── tests/              # Offline unit tests (no Gemini, no internet)
├── eval/               # Evaluation: test questions, runner, results.md
├── docs/README.md      # Detailed project documentation
├── docs/dev_log.md     # Development log: task timeline + technical notes
├── docs/prompt_iterations.md  # Prompt changes: failure → fix → measured result
├── demo_script.md      # Step-by-step live demo (questions, what to show)
├── flowchart.svg       # Architecture diagram (image)
├── requirements.txt    # Pinned Python packages
├── requirements-dev.txt # requirements.txt + pytest
└── .env.example        # Template for your API key
```

**The 4 tools** (in `tools.py`):

| Tool | What it answers | Data source |
|---|---|---|
| `get_exchange_rate` | The latest rate for one pair, e.g. USD to TWD | Frankfurter (daily) |
| `get_average_exchange_rate` | Average, min and max over a date range, e.g. Q1 vs Q2 | Frankfurter (daily) |
| `get_price_table` | A price table in IDR for several assets, with % change | Frankfurter + yfinance (IHSG, per minute) |
| `web_search` | Anything else, e.g. crypto or "why did TWD go up?" | DuckDuckGo |

## 3. Environment setup

You need **Python 3.10** and a free **Google Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey).

**Windows (PowerShell):**

```powershell
git clone <this-repo-url>
cd <repo-folder>
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux:**

```bash
git clone <this-repo-url>
cd <repo-folder>
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then open `.env` and replace `your-key-here` with your key. The `.env` file is ignored by git, so your key is never committed.

## 4. Steps to run

1. Activate the environment (if it isn't active already):
   - Windows: `.venv\Scripts\activate`
   - macOS / Linux: `source .venv/bin/activate`
2. Start the chat:
   ```
   python currency_agent.py
   ```
3. Ask a question, for example:
   - `market summary today`
   - `what is the USD to TWD rate?`
   - `average SGD to IDR in Q1 2026`
   - `bitcoin price in rupiah`
4. Useful commands:
   - `reset`: forget the conversation and start fresh
   - `exit` or **ESC**: quit (on macOS/Linux use `Ctrl+C`)
5. While the agent works, the terminal shows each tool it calls (`🔧`) and whether the result came back OK (`✅`) or failed (`❌`). The full trace is also saved to `agent_log.txt` (recreated each time you start the program).
6. Optional: run the offline tests (they don't use Gemini or the internet):
   ```
   pip install -r requirements-dev.txt
   pytest
   ```
