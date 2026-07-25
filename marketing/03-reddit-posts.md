# Reddit Post — r/cscareerquestions

## Title
```
I built a free job search tool that scores listings with a local AI — no subscriptions, no cloud
```

## Body
```
Hey everyone,

I've been job searching and got frustrated with how fragmented and expensive the tools are. You end up with 20 browser tabs open, re-reading the same listings, and most "AI" job tools just charge you $30/month to run a keyword filter.

So I built JobRadar — it's open source and runs entirely on your machine.

**What it does:**
- Searches 8 job boards at once (Remotive, RemoteOK, Jobicy, Himalayas, Arbeitnow, plus direct ATS feeds from Greenhouse and Ashby companies)
- Scores every listing 0-100 against your profile using a local AI model (no cloud APIs, no data leaving your laptop)
- Has a web dashboard where you can track jobs in a Kanban pipeline (Discovered → Reviewing → Applied → Interviewing)
- Caches results so you don't re-review the same jobs every day

**The local AI part:** It runs qwen3-1.7b via Ollama or llama.cpp. The model scores each job on skills match, experience fit, salary fit, and remote fit. It's not perfect — it's a starting point, not a verdict. You're still the one deciding.

**Setup:** One command — `bash setup.sh` (or `.\setup.ps1` on Windows). It asks if you want Ollama (recommended) or llama.cpp, downloads the model, and you're ready.

**Why I'm posting here:** I think a lot of people in this sub would benefit from a free, privacy-respecting alternative to the paid tools. No vendor lock-in, no data collection, MIT licensed.

GitHub: https://github.com/ANIRudH-lab-life/job-radar

Would love feedback on what sources to add or how to improve the scoring.
```

---

# Reddit Post — r/LocalLLaMA

## Title
```
JobRadar: Open-source job search agent that scores listings with local LLM (qwen3-1.7b via Ollama)
```

## Body
```
Built a job search tool that runs entirely locally — no cloud APIs, no subscriptions.

It searches 8 job boards concurrently and uses a local LLM (qwen3-1.7b via Ollama or llama.cpp) to score each listing against your profile. Returns structured JSON scores for skills match, experience fit, salary fit, and remote fit.

**How it works with Ollama:**
1. `ollama pull qwen3:1.7b`
2. `python -m jobradar -q "python developer" -p profile.yaml --llm-url http://localhost:11434`

The tool auto-detects whether you're running Ollama or llama.cpp and uses the right model name and health endpoint.

**Why local:** Every other job search tool uses Claude/OpenAI APIs for scoring. Your resume data, search patterns, and career preferences all go to third-party servers. This keeps everything on your machine.

GitHub: https://github.com/ANIRudH-lab-life/job-radar

Would be interesting to hear if anyone wants to try it with a larger model — the scoring prompt is structured JSON output, so bigger models might give better reasoning.
```
