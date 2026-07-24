# 🎯 JobRadar — AI-Powered Job Search Agent

A CLI tool that searches jobs from **6 free sources** simultaneously and rates each one against your profile using a local LLM — no API costs, no subscriptions, fully private.

## Features

- 🔍 **Multi-source search** — Remotive, Arbeitnow, RemoteOK, Jobicy, Himalayas (+ opt-in LinkedIn)
- 🤖 **AI-powered matching** — Local LLM rates each job against your full profile
- ⚡ **Concurrent** — All sources searched in parallel, AI ratings batched
- 📊 **Detailed scoring** — Skills match, experience fit, salary fit, remote fit (0-100 each)
- 💾 **Export** — JSON or CSV output
- 🎨 **Beautiful UI** — Rich terminal with color-coded scores and progress bars

## Quick Start

```bash
cd job-radar
pip install -r requirements.txt

# Search (no AI — fast)
python -m jobradar -q "python developer" --no-ai

# Search with AI rating (requires local LLM)
python -m jobradar -q "python developer" -p profile.yaml

# Interactive mode
python -m jobradar
```

## Job Sources

| Source | Auth Required | Notes |
|--------|:---:|-------|
| Remotive | No | Remote jobs only |
| Arbeitnow | No | Paginated, worldwide |
| RemoteOK | No | Remote jobs, 100+ per query |
| Jobicy | No | Remote jobs with salary data |
| Himalayas | No | Remote jobs with salary/seniority |
| LinkedIn | **Opt-in** | ⚠️ May violate ToS — off by default |

## Profile Configuration

Create a `profile.yaml`:

```yaml
name: "Your Name"
title: "Software Engineer"
experience_years: 5
skills: [Python, Docker, AWS, React]
desired_roles: [Backend Engineer, SRE]
salary_min: 100000
salary_max: 160000
location_preference: "Remote"
remote_ok: true
industries: [Fintech, SaaS]
```

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `-q`, `--query` | — | Search query (triggers search mode) |
| `-l`, `--location` | — | Location filter |
| `-p`, `--profile` | `profile.yaml` | Profile YAML file |
| `--no-ai` | off | Skip AI rating (faster) |
| `--export` | — | Export to `.json` or `.csv` |
| `--limit` | `50` | Max jobs per source |
| `--max-pages` | `3` | Max pages per source |
| `--max-concurrency` | `3` | Max concurrent AI calls |
| `--enable-linkedin` | off | ⚠️ Enable LinkedIn scraping |
| `--llm-url` | `localhost:8080` | LLM server URL |

## Architecture

```
jobradar/
├── __init__.py          # Package init
├── __main__.py          # python -m jobradar entrypoint
├── models.py            # Job, Profile dataclasses
├── rating.py            # AIRater with retry + concurrent calls
├── display.py           # Rich terminal UI
├── cli.py               # argparse + search pipeline
└── sources/
    ├── remotive.py      # Remotive API
    ├── arbeitnow.py     # Arbeitnow API (paginated)
    ├── linkedin.py      # LinkedIn scraping (opt-in)
    ├── remoteok.py      # RemoteOK API
    ├── jobicy.py        # Jobicy API
    └── himalayas.py     # Himalayas API
```

## ⚠️ LinkedIn Warning

LinkedIn scraping is **disabled by default** because it depends on undocumented HTML markup that can break at any time and may violate LinkedIn's Terms of Service. Enable only if you understand the risks:

```bash
python -m jobradar -q "python dev" --enable-linkedin
# or
JOBRADAR_ENABLE_LINKEDIN=1 python -m jobradar -q "python dev"
```

## Tests

```bash
pip install pytest
pytest tests/ -v
```

## License

MIT — see [LICENSE](LICENSE)
