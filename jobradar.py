#!/usr/bin/env python3
"""
🎯 JobRadar — AI-Powered Job Search Agent
Searches jobs from multiple sources and rates them against your profile using local LLM.
"""

import argparse
import csv
import json
import os
import re
import sys
import textwrap
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
import yaml
from bs4 import BeautifulSoup
from rich import box
from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.markup import escape

# ─── Configuration ────────────────────────────────────────────────────────────

LLM_URL = os.environ.get("LLM_URL", "http://localhost:8080")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3-1.7b")
DEFAULT_PROFILE = "profile.yaml"
RESULTS_DIR = Path.home() / ".jobradar"

console = Console()


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    salary: str = ""
    source: str = ""
    remote: bool = False
    tags: list = field(default_factory=list)
    posted: str = ""
    # AI ratings
    score: int = 0
    rating: str = ""
    reasoning: str = ""
    skills_match: int = 0
    experience_fit: int = 0
    salary_fit: int = 0
    remote_fit: int = 0


@dataclass
class Profile:
    name: str = "User"
    title: str = ""
    experience_years: int = 0
    skills: list = field(default_factory=list)
    desired_roles: list = field(default_factory=list)
    salary_min: int = 0
    salary_max: int = 0
    location_preference: str = ""
    remote_ok: bool = True
    industries: list = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str) -> "Profile":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ─── Job Search Sources ───────────────────────────────────────────────────────

class RemotiveSearch:
    """Search jobs via Remotive.com API (free, no auth)."""
    BASE = "https://remotive.com/api/remote-jobs"
    SOURCE = "Remotive"

    @staticmethod
    def search(query: str, limit: int = 30) -> list[Job]:
        try:
            resp = requests.get(
                RemotiveSearch.BASE,
                params={"search": query, "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            jobs = []
            for item in data.get("jobs", [])[:limit]:
                salary = ""
                if item.get("salary"):
                    salary = item["salary"]
                jobs.append(Job(
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", "Anywhere"),
                    url=item.get("url", ""),
                    description=(item.get("description") or "")[:500],
                    salary=salary,
                    source=RemotiveSearch.SOURCE,
                    remote=True,
                    tags=item.get("tags", []),
                    posted=item.get("publication_date", ""),
                ))
            return jobs
        except Exception as e:
            console.print(f"  [dim]⚠ Remotive: {e}[/dim]")
            return []


class ArbeitnowSearch:
    """Search jobs via Arbeitnow.com API (free, no auth)."""
    BASE = "https://www.arbeitnow.com/api/job-board-api"
    SOURCE = "Arbeitnow"

    @staticmethod
    def search(query: str, limit: int = 30) -> list[Job]:
        try:
            resp = requests.get(ArbeitnowSearch.BASE, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            jobs = []
            query_lower = query.lower()
            for item in data.get("data", []):
                title = item.get("title", "")
                desc = BeautifulSoup(item.get("description", "") or "", "html.parser").get_text()[:500]
                tags = item.get("tags", [])
                # Basic relevance filter
                searchable = f"{title} {desc} {' '.join(tags)}".lower()
                if query_lower not in searchable and not any(
                    q in searchable for q in query_lower.split()
                ):
                    continue
                salary = ""
                if item.get("salary"):
                    salary = item["salary"]
                jobs.append(Job(
                    title=title,
                    company=item.get("company_name", ""),
                    location=item.get("location", ""),
                    url=item.get("url", ""),
                    description=desc,
                    salary=salary,
                    source=ArbeitnowSearch.SOURCE,
                    remote=item.get("remote", False),
                    tags=tags,
                    posted=item.get("created_at", ""),
                ))
                if len(jobs) >= limit:
                    break
            return jobs
        except Exception as e:
            console.print(f"  [dim]⚠ Arbeitnow: {e}[/dim]")
            return []


class LinkedInSearch:
    """Search jobs via LinkedIn's public job search (web scraping)."""
    SOURCE = "LinkedIn"

    @staticmethod
    def search(query: str, location: str = "", limit: int = 20) -> list[Job]:
        try:
            search_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            params = {
                "keywords": query,
                "location": location or "United States",
                "start": 0,
                "sortBy": "DD",  # Date Descending
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = requests.get(search_url, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li")
            jobs = []
            for card in cards[:limit]:
                try:
                    title_el = card.find("h3", class_="base-card__full-link")
                    title = title_el.get_text(strip=True) if title_el else ""
                    url = title_el["href"].split("?")[0] if title_el and title_el.get("href") else ""
                    company_el = card.find("h4", class_="hidden-nested-link")
                    company = company_el.get_text(strip=True) if company_el else ""
                    location_el = card.find("span", class_="job-search-card__location")
                    loc = location_el.get_text(strip=True) if location_el else ""
                    if not title:
                        continue
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=loc,
                        url=url,
                        source=LinkedInSearch.SOURCE,
                        remote="remote" in loc.lower(),
                    ))
                except Exception:
                    continue
            return jobs
        except Exception as e:
            console.print(f"  [dim]⚠ LinkedIn: {e}[/dim]")
            return []


# ─── AI Rating Engine ─────────────────────────────────────────────────────────

class AIRater:
    """Rate jobs against a profile using local LLM."""

    def __init__(self, base_url: str = LLM_URL):
        self.base_url = base_url
        self.available = self._check_health()

    def _check_health(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def rate_job(self, job: Job, profile: Profile) -> Job:
        if not self.available:
            job.score = 50
            job.rating = "⚡ LLM offline"
            job.reasoning = "AI rating unavailable — server not running"
            job.skills_match = 50
            job.experience_fit = 50
            job.salary_fit = 50
            job.remote_fit = 50
            return job

        prompt = self._build_prompt(job, profile)

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": "Respond ONLY with valid JSON. No thinking, no explanation, no markdown. Just the JSON object."},
                        {"role": "user", "content": f"/no_think\n{prompt}"},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 200,
                    "stop": ["</tool_call>"],
                },
                timeout=120,
            )
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
            content = msg.get("content", "") or ""
            # Fallback: check reasoning_content if content is empty (qwen3 thinking mode)
            if not content.strip():
                content = msg.get("reasoning_content", "") or ""
            # Strip any <think> tags that leaked through
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            # Also strip lone <think> tags without closing
            content = re.sub(r'<think>.*', '', content, flags=re.DOTALL).strip()
            job = self._parse_response(content, job)
        except Exception as e:
            job.score = 50
            job.rating = "⚠ Rating failed"
            job.reasoning = str(e)[:200]
            job.skills_match = 50
            job.experience_fit = 50
            job.salary_fit = 50
            job.remote_fit = 50

        return job

    def _build_prompt(self, job: Job, profile: Profile) -> str:
        skills_str = ", ".join(profile.skills[:10]) if profile.skills else "N/A"

        return f"""Rate job match (0-100).

Candidate: {profile.title or 'N/A'}, {profile.experience_years}yr exp, skills: {skills_str}
Job: {job.title} @ {job.company}, {job.location}, remote={'Y' if job.remote else 'N'}, salary: {job.salary or 'N/A'}
Tags: {', '.join(job.tags[:5]) if job.tags else 'N/A'}

Reply JSON ONLY:
{{"overall_score":0-100,"rating":"Excellent/Good/Fair/Poor","skills_match":0-100,"experience_fit":0-100,"salary_fit":0-100,"remote_fit":0-100,"reasoning":"brief explanation"}}"""

    def _parse_response(self, content: str, job: Job) -> Job:
        # Try to extract JSON from response
        try:
            # Find JSON in response
            json_match = re.search(r'\{[^{}]*"overall_score"[^{}]*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                job.score = min(100, max(0, int(data.get("overall_score", 50))))
                job.rating = data.get("rating", "Unknown")
                job.reasoning = data.get("reasoning", "")
                job.skills_match = min(100, max(0, int(data.get("skills_match", 50))))
                job.experience_fit = min(100, max(0, int(data.get("experience_fit", 50))))
                job.salary_fit = min(100, max(0, int(data.get("salary_fit", 50))))
                job.remote_fit = min(100, max(0, int(data.get("remote_fit", 50))))
            else:
                # Fallback: try to parse score from text
                score_match = re.search(r'(\d+)/100|score[:\s]*(\d+)', content, re.IGNORECASE)
                if score_match:
                    job.score = int(score_match.group(1) or score_match.group(2))
                job.reasoning = content[:300]
        except Exception:
            job.score = 50
            job.reasoning = content[:300]

        return job


# ─── Display Functions ────────────────────────────────────────────────────────

def score_color(score: int) -> str:
    if score >= 80:
        return "bold green"
    elif score >= 60:
        return "bold yellow"
    elif score >= 40:
        return "bold dark_orange"
    else:
        return "bold red"


def score_bar(score: int) -> str:
    filled = score // 5
    empty = 20 - filled
    return f"[{score_color(score)}]{'█' * filled}[/{score_color(score)}][dim]{'░' * empty}[/dim] {score}/100"


def display_header():
    logo = """
[bold cyan]
  ╔═══════════════════════════════════════════════════╗
  ║   🎯  J O B   R A D A R                         ║
  ║   AI-Powered Job Search Agent                    ║
  ╚═══════════════════════════════════════════════════╝[/bold cyan]"""
    console.print(logo)


def display_jobs(jobs: list[Job], profile: Optional[Profile] = None, ai_enabled: bool = True):
    if not jobs:
        console.print("\n[bold red]No jobs found.[/bold red] Try different keywords.\n")
        return

    # Sort by score (descending)
    jobs.sort(key=lambda j: j.score, reverse=True)

    # Main table
    table = Table(
        title=f"[bold cyan]Found {len(jobs)} Jobs[/bold cyan]",
        box=box.ROUNDED,
        show_lines=True,
        title_style="bold cyan",
        padding=(0, 1),
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Score", justify="center", width=12)
    table.add_column("Job Title", style="bold white", min_width=25, max_width=35)
    table.add_column("Company", style="cyan", min_width=15, max_width=20)
    table.add_column("Location", style="dim", min_width=12, max_width=18)
    table.add_column("Source", style="magenta", width=10)
    table.add_column("Salary", style="green", width=14)

    for i, job in enumerate(jobs, 1):
        score_text = score_bar(job.score) if ai_enabled else "[dim]N/A[/dim]"
        title_text = job.title[:33] + "…" if len(job.title) > 35 else job.title
        company_text = job.company[:18] + "…" if len(job.company) > 20 else job.company
        loc_text = job.location[:16] + "…" if len(job.location) > 18 else job.location
        salary_text = job.salary[:12] if job.salary else "[dim]—[/dim]"

        table.add_row(
            str(i),
            score_text,
            title_text,
            company_text,
            loc_text,
            f"[magenta]{job.source}[/magenta]",
            salary_text,
        )

    console.print(table)
    console.print()

    # Detailed view for top 5
    if ai_enabled:
        console.print("[bold cyan]━━━ Top 5 Match Details ━━━[/bold cyan]\n")
        for i, job in enumerate(jobs[:5], 1):
            rating_color = score_color(job.score)
            panel_content = Text()
            panel_content.append(f"  🔗 {job.url}\n\n", style="dim underline blue")
            panel_content.append(f"  Skills Match:    ", style="bold")
            panel_content.append(f"{job.skills_match}/100\n", style=score_color(job.skills_match))
            panel_content.append(f"  Experience Fit:  ", style="bold")
            panel_content.append(f"{job.experience_fit}/100\n", style=score_color(job.experience_fit))
            panel_content.append(f"  Salary Fit:      ", style="bold")
            panel_content.append(f"{job.salary_fit}/100\n", style=score_color(job.salary_fit))
            panel_content.append(f"  Remote Fit:      ", style="bold")
            panel_content.append(f"{job.remote_fit}/100\n", style=score_color(job.remote_fit))
            if job.reasoning:
                panel_content.append(f"\n  💡 {job.reasoning}\n", style="italic")

            console.print(Panel(
                panel_content,
                title=f"[bold {rating_color}]#{i} — {job.title} @ {job.company}  [{job.rating}]  Score: {job.score}/100[/bold {rating_color}]",
                border_style=rating_color,
                padding=(0, 1),
            ))


def export_results(jobs: list[Job], path: str, fmt: str = "json"):
    if fmt == "json":
        with open(path, "w") as f:
            json.dump([asdict(j) for j in jobs], f, indent=2, default=str)
    elif fmt == "csv":
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "title", "company", "location", "url", "salary",
                "source", "remote", "score", "rating", "reasoning",
            ])
            writer.writeheader()
            for j in jobs:
                writer.writerow({k: v for k, v in asdict(j).items() if k in writer.fieldnames})
    console.print(f"[green]✓ Exported {len(jobs)} jobs to {path}[/green]")


# ─── Main Search Logic ────────────────────────────────────────────────────────

def search_jobs(
    query: str,
    location: str = "",
    profile: Optional[Profile] = None,
    ai_enabled: bool = True,
    export_path: str = "",
    limit: int = 30,
) -> list[Job]:
    """Main search pipeline."""
    display_header()

    # Step 1: Search multiple sources
    console.print(f"\n[bold cyan]🔍 Searching for:[/bold cyan] [bold white]{escape(query)}[/bold white]")
    if location:
        console.print(f"[bold cyan]📍 Location:[/bold cyan] [bold white]{escape(location)}[/bold white]")
    console.print()

    all_jobs: list[Job] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Searching sources...", total=3)

        # Remotive
        progress.update(task, description="[cyan]Remotive...[/cyan]")
        remotive_jobs = RemotiveSearch.search(query, limit=limit)
        all_jobs.extend(remotive_jobs)
        progress.update(task, advance=1, description=f"[green]Remotive: {len(remotive_jobs)} jobs[/green]")

        # Arbeitnow
        progress.update(task, description="[cyan]Arbeitnow...[/cyan]")
        arbeitnow_jobs = ArbeitnowSearch.search(query, limit=limit)
        all_jobs.extend(arbeitnow_jobs)
        progress.update(task, advance=1, description=f"[green]Arbeitnow: {len(arbeitnow_jobs)} jobs[/green]")

        # LinkedIn
        progress.update(task, description="[cyan]LinkedIn...[/cyan]")
        linkedin_jobs = LinkedInSearch.search(query, location=location, limit=limit)
        all_jobs.extend(linkedin_jobs)
        progress.update(task, advance=1, description=f"[green]LinkedIn: {len(linkedin_jobs)} jobs[/green]")

    # Deduplicate by title + company
    seen = set()
    unique_jobs = []
    for j in all_jobs:
        key = (j.title.lower().strip(), j.company.lower().strip())
        if key not in seen:
            seen.add(key)
            unique_jobs.append(j)
    all_jobs = unique_jobs

    console.print(f"\n[green]✓ Found {len(all_jobs)} unique jobs from {len(set(j.source for j in all_jobs))} sources[/green]\n")

    if not all_jobs:
        return []

    # Step 2: AI Rating
    if ai_enabled:
        rater = AIRater()
        if rater.available:
            console.print(f"[bold cyan]🤖 Rating jobs with local LLM ({LLM_MODEL})...[/bold cyan]\n")
            profile = profile or Profile(name="Job Seeker")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TextColumn("[dim]{task.fields[elapsed]}[/dim]"),
                console=console,
            ) as progress:
                task = progress.add_task("AI Rating...", total=len(all_jobs), elapsed="")
                start_time = time.time()

                for idx, job in enumerate(all_jobs):
                    elapsed = time.strftime("%M:%S", time.gmtime(time.time() - start_time))
                    progress.update(task, description=f"[cyan]Rating: {job.title[:30]}...[/cyan]", elapsed=elapsed)
                    rater.rate_job(job, profile)
                    # Small delay to avoid overwhelming the single-threaded LLM server
                    if idx < len(all_jobs) - 1:
                        time.sleep(0.5)
                    progress.update(task, advance=1)
        else:
            console.print("[yellow]⚠ Local LLM not available. Running without AI ratings.[/yellow]")
            console.print(f"[dim]  Start llama-server on {LLM_URL} to enable AI ratings[/dim]\n")
            for job in all_jobs:
                job.score = 50
                job.rating = "No AI"
    else:
        for job in all_jobs:
            job.score = 50
            job.rating = "Skipped"

    # Step 3: Display
    display_jobs(all_jobs, profile, ai_enabled)

    # Step 4: Export
    if export_path:
        fmt = "csv" if export_path.endswith(".csv") else "json"
        export_results(all_jobs, export_path, fmt)

    return all_jobs


# ─── CLI ──────────────────────────────────────────────────────────────────────

def interactive_mode(profile: Optional[Profile] = None):
    """Run in interactive mode."""
    display_header()

    console.print("[bold cyan]Welcome to JobRadar![/bold cyan]")
    console.print("[dim]Type your search query, or 'quit' to exit.[/dim]\n")

    if profile:
        console.print(f"[green]✓ Profile loaded:[/green] {profile.name} — {profile.title}")
        if profile.skills:
            console.print(f"  Skills: {', '.join(profile.skills[:8])}")
        console.print()

    while True:
        try:
            query = console.input("[bold cyan]🔍 Search> [/bold cyan]").strip()
            if not query or query.lower() in ("quit", "exit", "q"):
                console.print("\n[dim]Goodbye! 👋[/dim]")
                break

            location = console.input("[dim]📍 Location (Enter to skip)> [/dim]").strip()

            search_jobs(
                query=query,
                location=location,
                profile=profile,
                ai_enabled=True,
            )
            console.print()

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye! 👋[/dim]")
            break


def main():
    parser = argparse.ArgumentParser(
        description="🎯 JobRadar — AI-Powered Job Search Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          %(prog)s                                    # Interactive mode
          %(prog)s search -q "python developer"      # Quick search
          %(prog)s search -q "ML engineer" -p my.yaml # With profile
          %(prog)s search -q "backend" --export jobs.json
          %(prog)s search -q "data engineer" --no-ai  # Skip AI rating
        """),
    )
    subparsers = parser.add_subparsers(dest="command")

    # Default: interactive mode
    parser.add_argument("-q", "--query", help="Search query (if provided, runs search mode)")
    parser.add_argument("-l", "--location", default="", help="Location filter")
    parser.add_argument("-p", "--profile", default=DEFAULT_PROFILE, help="Profile YAML file")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI rating (faster)")
    parser.add_argument("--export", help="Export results to file (JSON or CSV)")
    parser.add_argument("--limit", type=int, default=25, help="Max jobs per source")
    parser.add_argument("--llm-url", default=LLM_URL, help="LLM server URL")

    args = parser.parse_args()

    # Set LLM URL via environment
    os.environ["LLM_URL"] = args.llm_url

    # Load profile
    profile = None
    profile_path = Path(args.profile)
    if profile_path.exists():
        try:
            profile = Profile.from_yaml(str(profile_path))
            console.print(f"[green]✓ Profile loaded:[/green] {profile.name}")
        except Exception as e:
            console.print(f"[yellow]⚠ Could not load profile: {e}[/yellow]")

    if args.query:
        # Direct search mode
        search_jobs(
            query=args.query,
            location=args.location,
            profile=profile,
            ai_enabled=not args.no_ai,
            export_path=args.export or "",
            limit=args.limit,
        )
    else:
        # Interactive mode
        interactive_mode(profile)


if __name__ == "__main__":
    main()
