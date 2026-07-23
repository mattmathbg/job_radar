# 🎯 JobRadar — AI-Powered Job Search Agent

A CLI tool that searches jobs from multiple sources and rates each one against your profile using a local LLM — no API costs, no subscriptions, fully private.

## Features

- 🔍 **Multi-source search** — Remotive, Arbeitnow, LinkedIn (all free, no auth needed)
- 🤖 **AI-powered matching** — Local LLM rates each job against your profile (skills, experience, salary, remote preference)
- 🎨 **Beautiful terminal UI** — Color-coded scores, progress bars, detailed match panels via Rich
- 📊 **Smart scoring** — 0-100 score with breakdown: skills match, experience fit, salary fit, remote fit
- 💡 **AI reasoning** — Every rating comes with a plain-English explanation of why it matches (or doesn't)
- 💾 **Export** — Save results as JSON or CSV for further processing
- ⚡ **Fast & free** — Uses local models (llama.cpp), zero API costs
- 🔒 **Fully private** — All processing happens on your machine

## Demo

```
  ╔═══════════════════════════════════════════════════╗
  ║   🎯  J O B   R A D A R                         ║
  ║   AI-Powered Job Search Agent                    ║
  ╚═══════════════════════════════════════════════════╝

🔍 Searching for: python developer

✓ Found 10 unique jobs from 3 sources

┌───┬─────────────┬──────────────────────────┬──────────────┬────────────┬───────────┬──────────────┐
│ # │ Score       │ Job Title                │ Company      │ Location   │ Source    │ Salary       │
├───┼─────────────┼──────────────────────────┼──────────────┼────────────┼───────────┼──────────────┤
│ 1 │ ██████████░ │ Senior Python Engineer   │ TechCorp     │ Remote     │ Remotive  │ $130k-$160k  │
│ 2 │ █████████░░ │ Full-Stack Engineer      │ StartupXYZ   │ Anywhere   │ Remotive  │ $110k-$140k  │
│ 3 │ ████████░░░ │ Backend Developer        │ DataInc      │ New York   │ LinkedIn  │ —            │
└───┴─────────────┴──────────────────────────┴──────────────┴────────────┴───────────┴──────────────┘

━━━ Top 5 Match Details ━━━

╭──────────────────────────────────────────────────────╮
│ #1 — Senior Python Engineer @ TechCorp  [Excellent]  │
│ Score: 85/100                                        │
│                                                      │
│   🔗 https://remotive.com/job/python-engineer/...    │
│                                                      │
│   Skills Match:    90/100                            │
│   Experience Fit:  85/100                            │
│   Salary Fit:      80/100                            │
│   Remote Fit:      95/100                            │
│                                                      │
│   💡 Strong match — Python, Docker, and REST APIs    │
│      align perfectly with your 3yr experience.       │
╰──────────────────────────────────────────────────────╯
```

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/ANIRudH-lab-life/job-radar.git
cd job-radar
pip install -r requirements.txt
```

### 2. Set up your profile

Edit `profile.yaml` with your details:

```yaml
name: "Your Name"
title: "Software Engineer"
experience_years: 3
skills:
  - Python
  - JavaScript
  - TypeScript
  - React
  - Node.js
  - Docker
  - SQL
  - Git
desired_roles:
  - Full Stack Developer
  - Backend Engineer
salary_min: 80000
salary_max: 150000
location_preference: "Remote"
remote_ok: true
industries:
  - Technology
  - AI/ML
  - SaaS
```

### 3. (Optional) Start the LLM server for AI ratings

```bash
# Using llama.cpp
llama-server -m qwen3-1.7b.gguf --port 8080

# Or any OpenAI-compatible local server on port 8080
```

> JobRadar works without the LLM — you just won't get AI-powered scoring. Use `--no-ai` to skip.

### 4. Search for jobs!

```bash
python jobradar.py -q "python developer"
```

## Usage

### Search modes

```bash
# Quick search
python jobradar.py -q "machine learning engineer"

# With your profile (recommended for AI ratings)
python jobradar.py -q "backend developer" -p profile.yaml

# With location filter
python jobradar.py -q "data engineer" -l "London"

# Interactive mode (prompt-based)
python jobradar.py

# Skip AI rating (faster, no LLM needed)
python jobradar.py -q "devops engineer" --no-ai

# Limit results per source
python jobradar.py -q "react developer" --limit 10

# Custom LLM server URL
python jobradar.py -q "ML engineer" --llm-url http://192.168.1.100:8080
```

### Export results

```bash
# Export to JSON
python jobradar.py -q "python developer" --export results.json

# Export to CSV
python jobradar.py -q "python developer" --export results.csv

# Combine with profile
python jobradar.py -q "ML engineer" -p profile.yaml --export jobs.json
```

### CLI options

| Flag | Description | Default |
|------|-------------|---------|
| `-q`, `--query` | Search query | (interactive mode) |
| `-l`, `--location` | Location filter | `""` |
| `-p`, `--profile` | Profile YAML path | `profile.yaml` |
| `--no-ai` | Skip AI rating | `false` |
| `--export` | Export to JSON/CSV file | none |
| `--limit` | Max jobs per source | `25` |
| `--llm-url` | LLM server URL | `http://localhost:8080` |

## How It Works

1. **Search** — Queries 3 free job APIs simultaneously (no auth required):
   - [Remotive](https://remotive.com) — remote tech jobs
   - [Arbeitnow](https://www.arbeitnow.com) — global tech jobs
   - [LinkedIn](https://www.linkedin.com) — public job listings (web scraping)

2. **Deduplicate** — Removes duplicate postings (same title + company)

3. **Rate** — Your local LLM analyzes each job against your profile:
   - Skills match: Do your skills align with the job requirements?
   - Experience fit: Does your experience level match?
   - Salary fit: Does the salary range meet your expectations?
   - Remote fit: Does the work arrangement suit your preference?

4. **Rank & Display** — Sorts by AI match score (0-100), shows a color-coded table with detailed breakdown for the top 5 matches

5. **Export** (optional) — Save everything to JSON or CSV

## Profile Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Your name |
| `title` | string | Current/most recent job title |
| `experience_years` | int | Years of professional experience |
| `skills` | list | Technical skills (used for matching) |
| `desired_roles` | list | Roles you're interested in |
| `salary_min` | int | Minimum acceptable salary |
| `salary_max` | int | Maximum expected salary |
| `location_preference` | string | Preferred location |
| `remote_ok` | bool | Open to remote work |
| `industries` | list | Preferred industries |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_URL` | LLM server base URL | `http://localhost:8080` |
| `LLM_MODEL` | Model name for the LLM | `qwen3-1.7b` |

## Requirements

- Python 3.8+
- Internet connection (for job search APIs)
- [llama.cpp](https://github.com/ggerganov/llama.cpp) or any OpenAI-compatible local server (for AI ratings — optional)

### Python dependencies

- `rich` — terminal UI
- `pyyaml` — profile parsing
- `requests` — HTTP requests
- `beautifulsoup4` — LinkedIn scraping

## Recommended Models

Smaller models are faster. Larger models give better ratings.

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `qwen3-1.7b` | 1.7B | ⚡ Fast | Good |
| `qwen3-8b` | 8B | Moderate | Great |
| `llama-3.1-8b` | 8B | Moderate | Great |
| `qwen3-32b` | 32B | Slow | Excellent |

## License

MIT — use it however you want.

## Author

**Anirudh** — [GitHub](https://github.com/ANIRudH-lab-life)
