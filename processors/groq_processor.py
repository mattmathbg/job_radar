import os
import json
import logging
from typing import Optional

from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models.job import JobOffer

logger = logging.getLogger(__name__)

class GroqProcessor:
    def __init__(self, model_name: str = "groq/compound"):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY environment variable not found.")
        self.client = AsyncGroq(api_key=api_key)
        self.model_name = model_name

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type(Exception)
    )
    async def process_job(self, job: JobOffer) -> JobOffer:
        prompt = f"""
Analyze the following job description and extract key information.
You MUST return ONLY a valid JSON object matching exactly this structure, no markdown formatting or extra text:
{{
  "tech_stack": ["List", "of", "technologies", "mentioned"],
  "salary_estimation": "Estimated salary range if mentioned, otherwise 'Not provided'",
  "bullshit_score": integer from 1 to 10 evaluating how much corporate jargon/buzzwords are used (10 = full of buzzwords),
  "is_relevant": true if it's a genuine Software or Data engineering role, false otherwise,
  "summary": "A concise 2-sentence summary of the role and requirements in French"
}}

Job Title: {job.title}
Company: {job.company}
Description: {job.description}
"""
        
        try:
            response = await self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that outputs strict JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model_name,
                temperature=0.0
            )

            result_text = response.choices[0].message.content
            
            # Clean markdown codeblock wrappers if present
            if "```" in result_text:
                parts = result_text.split("```")
                if len(parts) >= 2:
                    result_text = parts[1]
                    if result_text.startswith("json"):
                        result_text = result_text[4:]
            result_text = result_text.strip()

            parsed_data = json.loads(result_text)

            job.tech_stack = parsed_data.get("tech_stack", [])
            job.salary_estimation = str(parsed_data.get("salary_estimation", ""))
            job.bullshit_score = int(parsed_data.get("bullshit_score", 0))
            job.is_relevant = bool(parsed_data.get("is_relevant", True))
            job.summary = str(parsed_data.get("summary", ""))

            return job
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON for job {job.id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling Groq API for job {job.id}: {e}")
            if self.model_name == "groq/compound":
                self.model_name = "qwen/qwen3.6-27b"
            raise
