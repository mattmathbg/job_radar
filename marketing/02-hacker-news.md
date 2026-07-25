# Show HN: JobRadar — Open-source job search agent with local AI scoring

## Title (for HN submission)
```
Show HN: JobRadar – Local AI scores jobs across 8 boards, zero cloud dependency
```

## Body
```
I got tired of job searching tools that are just prettier wrappers around Indeed scraping, so I built JobRadar — a CLI tool that searches 8 job sources concurrently and scores every listing against your profile using a local LLM.

**What it does:**
- Searches 8 sources at once: Remotive, Arbeitnow, RemoteOK, Jobicy, Himalayas, Greenhouse ATS (15 companies), Ashby ATS (15 companies), and optionally LinkedIn
- Scores each job 0-100 on skills match, experience fit, salary fit, and remote fit using a local LLM (Ollama or llama.cpp)
- Web dashboard with Kanban pipeline, filters, and config editor
- Persistent cache so you don't re-review the same jobs

**Why local LLM:**
Every other tool I found uses cloud APIs (Claude, OpenAI) for scoring, which means your resume and search data go to someone else's server, and you pay per-token. JobRadar runs qwen3-1.7b (1.1GB) on your CPU via Ollama or llama.cpp. Zero API costs, zero data leaves your machine.

**How it works:**
The Greenhouse and Ashby sources pull directly from company career page APIs (no scraping, no auth). The board sources use public APIs. LinkedIn is off by default and requires an explicit flag because it scrapes undocumented HTML.

The LLM scores jobs against a profile YAML you define (skills, experience, desired roles, salary range, location preference). It returns structured JSON with per-dimension scores and reasoning.

**Stack:** Python, Rich (terminal UI), FastAPI (dashboard), SQLite (cache), requests/BeautifulSoup (scraping).

**Honest limitations:**
- The local LLM scoring is good for filtering, not perfect — it's a guide, not a decision-maker
- LinkedIn scraping breaks when they change their HTML (hence it's opt-in)
- Some sources have rate limits that cap how many jobs you can fetch per run

GitHub: https://github.com/ANIRudH-lab-life/job-radar

MIT licensed.
```
