# 🎯 JobRadar — AI-Powered Job Search Agent

A CLI tool that searches jobs from **6 sources** and rates each one against your profile using a local LLM — no API costs, no subscriptions, fully private.

## Features

- 🔍 **Multi-source search** — Remotive, Arbeitnow, RemoteOK, Jobicy, Himalayas, LinkedIn (all free, no auth needed)
- 🤖 **AI-powered matching** — Local LLM rates each job against your profile (skills, experience, salary, remote preference, desired roles, industries)
- 🎨 **Beautiful terminal UI** — Color-coded scores, progress bars, detailed match panels via Rich
- 📊 **Smart scoring** — 0-100 score with breakdown: skills match, experience fit, salary fit, remote fit
- 💡 **AI reasoning** — Every rating comes with a plain-English explanation of why it matches (or doesn't)
- ⚡ **Concurrent searches** — All sources searched in parallel via ThreadPoolExecutor
- 💾 **Export** — Save results as JSON or CSV for further processing
- 🔒 **Fully private** — All processing happens on your machine

## Sources

| Source | Auth | Pagination | Notes |
|--------|------|------------|-------|
| [Remotive](https://remotive.com) | None | Server-side `limit` param | Remote tech jobs |
| [Arbeitnow](https://www.arbeitnow.com) | None | `?page=N` (100/page) | Global tech jobs |
| [RemoteOK](https://remoteok.com) | None | None (~100 latest) | Remote jobs, client-side filter |
| [Jobicy](https://jobicy.com) | None | `?count=N&tag=X` | Remote jobs, tag-filtered |
| [Himalayas](https://himalayas.app) | None | `?limit=N&offset=N` | Remote jobs, server-side search |
| [LinkedIn](https://www.linkedin.com) | None | Offset-based | ⚠️ **Disabled by default** — see ToS warning |

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
# or
python -m jobradar -q "python developer"
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

# Enable LinkedIn (off by default — may violate ToS)
python jobradar.py -q "python" --enable-linkedin

# Control pagination
python jobradar.py -q "python" --max-pages 5

# Control AI concurrency
python jobradar.py -q "python" --max-concurrency 5
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
| `--limit` | Max jobs per source | `50` |
| `--llm-url` | LLM server URL | `http://localhost:8080` |
| `--max-pages` | Max pages per source | `3` |
| `--max-concurrency` | Max concurrent AI rating calls | `3` |
| `--enable-linkedin` | Enable LinkedIn scraping | `false` (off by default) |

## LinkedIn ToS Warning

⚠️ **LinkedIn scraping is disabled by default.** The LinkedIn source depends on
undocumented HTML markup and **may violate LinkedIn's Terms of Service**. It
is provided as-is for educational purposes. To enable it, use `--enable-linkedin`
or set `JOBRADAR_ENABLE_LINKEDIN=1`. Use at your own risk.

## How It Works

1. **Search** — Queries 5 free job APIs concurrently (plus LinkedIn if enabled):
   - [Remotive](https://remotive.com) — remote tech jobs
   - [Arbeitnow](https://www.arbeitnow.com) — global tech jobs (paginated)
   - [RemoteOK](https://remoteok.com) — remote jobs
   - [Jobicy](https://jobicy.com) — remote jobs with industry tags
   - [Himalayas](https://himalayas.app) — remote jobs with salary data
   - [LinkedIn](https://www.linkedin.com) — public job listings (web scraping, opt-in)

2. **Deduplicate** — Removes duplicate postings (same title + company)

3. **Rate** — Your local LLM analyzes each job against your full profile:
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
| `JOBRADAR_ENABLE_LINKEDIN` | Enable LinkedIn scraping | `0` (disabled) |

## Requirements

- Python 3.8+
- Internet connection (for job search APIs)
- [llama.cpp](https://github.com/ggerganov/llama.cpp) or any OpenAI-compatible local server (for AI ratings — optional)

### Python dependencies

- `rich` — terminal UI
- `pyyaml` — profile parsing
- `requests` — HTTP requests
- `beautifulsoup4` — LinkedIn scraping
- `pytest` — testing (dev dependency)
- `responses` — HTTP mocking in tests (dev dependency)

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v
```

## Recommended Models

Smaller models are faster. Larger models give better ratings.

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `qwen3-1.7b` | 1.7B | ⚡ Fast | Good |
| `qwen3-8b` | 8B | Moderate | Great |
| `llama-3.1-8b` | 8B | Moderate | Great |
| `qwen3-32b` | 32B | Slow | Excellent |

## License

MIT — see [LICENSE](LICENSE).

## Author

**Anirudh** — [GitHub](https://github.com/ANIRudH-lab-life)
