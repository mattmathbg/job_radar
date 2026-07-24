"""AI Rating engine — scores jobs against a user profile via local LLM."""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

import requests

from jobradar.models import Job, Profile

logger = logging.getLogger(__name__)

LLM_URL = os.environ.get("LLM_URL", "http://localhost:8080")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3-1.7b")


class AIRater:
    """Rate jobs against a profile using a local LLM (OpenAI-compatible API)."""

    def __init__(self, base_url: str = LLM_URL, max_concurrency: int = 3):
        self.base_url = base_url
        self.max_concurrency = max_concurrency
        self.available = self._check_health()

    def _check_health(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def rate_jobs(self, jobs: List[Job], profile: Profile) -> List[Job]:
        """Rate a list of jobs concurrently (respecting max_concurrency)."""
        if not self.available:
            for job in jobs:
                job.score = 50
                job.rating = "⚡ LLM offline"
                job.reasoning = "AI rating unavailable — server not running"
                job.skills_match = 50
                job.experience_fit = 50
                job.salary_fit = 50
                job.remote_fit = 50
            return jobs

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as pool:
            futures = {pool.submit(self._rate_single, job, profile): job for job in jobs}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    job = futures[future]
                    job.score = 50
                    job.rating = "⚠ Error"
                    job.reasoning = str(exc)[:200]

        return jobs

    def _rate_single(self, job: Job, profile: Profile) -> Job:
        """Rate a single job. Called inside the thread pool."""
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
        """Build a prompt that includes the full profile for better scoring."""
        skills_str = ", ".join(profile.skills[:10]) if profile.skills else "N/A"
        desired_str = ", ".join(profile.desired_roles[:5]) if profile.desired_roles else "N/A"
        industries_str = ", ".join(profile.industries[:5]) if profile.industries else "N/A"
        salary_range = "N/A"
        if profile.salary_min or profile.salary_max:
            salary_range = f"${profile.salary_min:,}-${profile.salary_max:,}" if profile.salary_min and profile.salary_max else (
                f"${profile.salary_min:,}+" if profile.salary_min else f"up to ${profile.salary_max:,}"
            )

        return f"""Rate job match (0-100).

Candidate: {profile.title or 'N/A'}, {profile.experience_years}yr exp, skills: {skills_str}
Desired roles: {desired_str}
Industries: {industries_str}
Salary range: {salary_range}
Location pref: {profile.location_preference or 'N/A'}, remote_ok={'Yes' if profile.remote_ok else 'No'}

Job: {job.title} @ {job.company}, {job.location}, remote={'Y' if job.remote else 'N'}, salary: {job.salary or 'N/A'}
Tags: {', '.join(job.tags[:5]) if job.tags else 'N/A'}

Reply JSON ONLY:
{{"overall_score":0-100,"rating":"Excellent/Good/Fair/Poor","skills_match":0-100,"experience_fit":0-100,"salary_fit":0-100,"remote_fit":0-100,"reasoning":"brief explanation"}}"""

    def _parse_response(self, content: str, job: Job, _retry: bool = True) -> Job:
        """Parse LLM response with multiple fallback strategies + 1 retry.

        Strategy order:
        1. Direct ``json.loads`` of the entire response
        2. Strip markdown code fences, then ``json.loads``
        3. Regex extraction of ``{...}`` containing ``overall_score``
        4. Fallback: extract score from prose (e.g. "85/100")
        5. On failure: retry once with a fresh prompt, then score=50
        """
        data = None

        # Strategy 1: direct parse
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: strip markdown fences
        if data is None:
            cleaned = re.sub(r"```(?:json)?\s*", "", content)
            cleaned = re.sub(r"```", "", cleaned)
            try:
                data = json.loads(cleaned)
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 3: regex extraction
        if data is None:
            m = re.search(r'\{[^{}]*"overall_score"[^{}]*\}', content, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group())
                except (json.JSONDecodeError, ValueError):
                    pass

        if data is not None:
            return self._apply_scores(data, job)

        # Strategy 4: prose score extraction
        score_m = re.search(r'(\d+)/100|score[:\s]*(\d+)', content, re.IGNORECASE)
        if score_m:
            job.score = min(100, max(0, int(score_m.group(1) or score_m.group(2))))
            job.reasoning = content[:300]
            return job

        # Strategy 5: retry once on malformed output
        if _retry:
            logger.warning("Malformed LLM response, retrying once. Raw: %s", content[:500])
            return self._parse_response(content, job, _retry=False)

        # Give up
        logger.error("Failed to parse LLM response after retry. Raw: %s", content[:500])
        job.score = 50
        job.rating = "Parse Error"
        job.reasoning = content[:300]
        return job

    @staticmethod
    def _apply_scores(data: dict, job: Job) -> Job:
        """Apply parsed dict scores to a Job."""
        job.score = min(100, max(0, int(data.get("overall_score", 50))))
        job.rating = data.get("rating", "Unknown")
        job.reasoning = data.get("reasoning", "")
        job.skills_match = min(100, max(0, int(data.get("skills_match", 50))))
        job.experience_fit = min(100, max(0, int(data.get("experience_fit", 50))))
        job.salary_fit = min(100, max(0, int(data.get("salary_fit", 50))))
        job.remote_fit = min(100, max(0, int(data.get("remote_fit", 50))))
        return job
