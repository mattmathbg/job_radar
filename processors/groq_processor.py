import os
import re
import json
import asyncio
import logging
from typing import Optional

from groq import AsyncGroq, RateLimitError, APIConnectionError, APIStatusError
from models.job import JobOffer

logger = logging.getLogger(__name__)

def parse_retry_after(error_msg: str, default: float = 15.0) -> float:
    """
    Extracts the recommended wait time in seconds from Groq RateLimitError message.
    E.g. 'Please try again in 35.568s.' -> 36.5
    """
    match = re.search(r'(?:try again in|retry after|in)\s*([\d\.]+)\s*s', error_msg, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1)) + 1.5  # Add 1.5s safety margin
        except ValueError:
            pass
    return default

def clean_llm_json_response(raw_text: str) -> str:
    """
    Cleans raw response from LLM, stripping thinking tags, markdown blocks, etc.
    """
    text = raw_text.strip()
    
    # Strip <think>...</think> tags if present
    if "<think>" in text and "</think>" in text:
        text = text.split("</think>", 1)[-1].strip()
        
    # Strip markdown code blocks ```json ... ```
    if "```" in text:
        blocks = text.split("```")
        for block in blocks:
            cleaned = block.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            if cleaned.startswith("{") and cleaned.endswith("}"):
                return cleaned
                
    # Fallback to finding the outer curly braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
        
    return text

class GroqProcessor:
    def __init__(self, model_name: Optional[str] = None):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY environment variable not found.")
        self.client = AsyncGroq(api_key=api_key)
        
        # Primary model (default to groq/compound or env var)
        self.primary_model = model_name or os.getenv("GROQ_MODEL", "groq/compound")
        # Lightweight fallback model to reduce token/rate limit pressure
        self.fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "groq/compound-mini")
        self.current_model = self.primary_model
        
        self.max_retries = int(os.getenv("GROQ_MAX_RETRIES", "5"))
        self.max_desc_length = int(os.getenv("GROQ_MAX_DESC_LENGTH", "3000"))

    async def process_job(self, job: JobOffer) -> JobOffer:
        """
        Analyzes job posting with Groq LLM, with adaptive rate-limit handling,
        retry-after backoff, and model fallback.
        """
        # Truncate description to save tokens and avoid hitting TPM limits
        clean_desc = (job.description or "").strip()
        if len(clean_desc) > self.max_desc_length:
            clean_desc = clean_desc[:self.max_desc_length] + "\n... [Description tronquée pour optimiser les tokens]"

        prompt = f"""Analyze the following job description and extract key information.
You MUST return ONLY a valid JSON object matching exactly this structure, with no extra text or markdown:
{{
  "tech_stack": ["List", "of", "technologies", "mentioned"],
  "salary_estimation": "Estimated salary range if mentioned, otherwise 'Not provided'",
  "bullshit_score": integer from 1 to 10 evaluating how much corporate jargon/buzzwords are used (10 = full of buzzwords),
  "is_relevant": true if it's a genuine Software or Data engineering role, false otherwise,
  "summary": "A concise 2-sentence summary of the role and requirements in French"
}}

Job Title: {job.title}
Company: {job.company}
Description: {clean_desc}
"""

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert HR and tech recruiter assistant. You output strict, valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    model=self.current_model,
                    temperature=0.1
                )

                raw_content = response.choices[0].message.content or ""
                cleaned_json_text = clean_llm_json_response(raw_content)

                parsed_data = json.loads(cleaned_json_text)

                job.tech_stack = parsed_data.get("tech_stack", [])
                if not isinstance(job.tech_stack, list):
                    job.tech_stack = [str(job.tech_stack)]
                    
                job.salary_estimation = str(parsed_data.get("salary_estimation", "Not provided"))
                job.bullshit_score = int(parsed_data.get("bullshit_score", 1))
                job.is_relevant = bool(parsed_data.get("is_relevant", True))
                job.summary = str(parsed_data.get("summary", "Description disponible dans l'offre."))

                # Successfully processed
                return job

            except RateLimitError as e:
                wait_time = parse_retry_after(str(e), default=20.0)
                logger.warning(
                    f"[RateLimit] Hit Groq rate limit for '{job.title}' on attempt {attempt}/{self.max_retries}. "
                    f"Waiting {wait_time:.1f}s before retry..."
                )
                
                # Switch to lighter fallback model if we hit rate limits on primary
                if self.current_model != self.fallback_model and attempt >= 2:
                    logger.info(f"[Model Fallback] Switching from {self.current_model} to {self.fallback_model}")
                    self.current_model = self.fallback_model
                    
                if attempt >= self.max_retries:
                    logger.error(f"[RateLimit] Exceeded max retries ({self.max_retries}) for job {job.url}.")
                    raise
                    
                await asyncio.sleep(wait_time)

            except (APIConnectionError, APIStatusError) as e:
                backoff = min(2 ** attempt + 2.0, 30.0)
                logger.warning(
                    f"[API Error] Groq API error on attempt {attempt}/{self.max_retries} for '{job.title}': {e}. "
                    f"Retrying in {backoff:.1f}s..."
                )
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(backoff)

            except json.JSONDecodeError as e:
                logger.error(f"[JSON Error] Failed to decode JSON from Groq for job {job.title}: {e}")
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"[Unexpected Error] Unexpected error processing job {job.title}: {e}")
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(2.0)

        return job
