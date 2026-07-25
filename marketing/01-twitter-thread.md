# X/Twitter Launch Thread — Copy & Post

## Tweet 1 (Hook)
```
Job searching is broken.

You open 15 tabs. You re-read the same listings. You pay $30/month for tools that just scrape Indeed.

I built something different → a CLI that searches 8 job boards at once, scores every listing with a LOCAL AI model, and runs entirely on your machine. Zero cloud. Zero cost.

🧵
```

## Tweet 2 (The Problem)
```
Most job search tools do the same thing: scrape boards, dump results, charge you monthly.

But here's what nobody talks about — your resume data, your search history, your career preferences all go to someone else's server.

What if the AI ran on YOUR machine?
```

## Tweet 3 (The Solution)
```
Meet JobRadar 🔍

→ Searches 8 sources concurrently (Remotive, RemoteOK, Jobicy, Himalayas, Greenhouse ATS, Ashby ATS, Arbeitnow, LinkedIn*)
→ Scores every job 0-100 against YOUR profile using a local LLM
→ Web dashboard with Kanban pipeline to track applications
→ Persistent cache so you never re-review the same job

*LinkedIn is opt-in (may violate ToS)
```

## Tweet 4 (The Local AI Angle)
```
The AI runs on your machine via Ollama or llama.cpp. No API keys. No subscriptions. No data leaving your laptop.

Model: qwen3-1.7b (1.1GB, runs on CPU)
Scoring: skills match, experience fit, salary fit, remote fit
Speed: 8 boards searched concurrently in ~10 seconds
```

## Tweet 5 (The Numbers)
```
What makes it different:

✓ 8 concurrent sources (most tools: 1-3)
✓ Local LLM scoring (most tools: cloud APIs = $$$)
✓ Web dashboard + CLI (most tools: terminal only)
✓ Cross-platform: Linux, macOS, Windows
✓ Zero dependencies on external services
✓ MIT licensed, fully open source
```

## Tweet 6 (Social Proof / How to Use)
```
Quick start:

git clone https://github.com/ANIRudH-lab-life/job-radar
cd job-radar
bash setup.sh  # or .\setup.ps1 on Windows

# Pick Ollama (recommended) or llama.cpp
# Search:
python -m jobradar -q "python developer" -p profile.yaml

That's it. 8 boards. AI-scored. On your machine.
```

## Tweet 7 (CTA)
```
If you're tired of job board tab hell and paying for tools that just aggregate feeds — give it a try.

⭐ Star it if you find it useful:
github.com/ANIRudH-lab-life/job-radar

MIT licensed. No vendor lock-in. Your data stays yours.

#OpenSource #JobSearch #AI #LocalLLM #BuildInPublic
```
