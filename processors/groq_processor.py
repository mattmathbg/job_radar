import os
import re
import json
import asyncio
import logging
from typing import Optional, List

from groq import AsyncGroq, RateLimitError, APIConnectionError, APIStatusError
from models.job import JobOffer
from models.profile import CandidateProfile

logger = logging.getLogger(__name__)

def parse_retry_after(error_msg: str, default: float = 10.0) -> float:
    """
    Extracts the recommended wait time in seconds from Groq RateLimitError message.
    E.g. 'Please try again in 35.568s.' -> 37.0
    """
    match = re.search(r'(?:try again in|retry after|in)\s*([\d\.]+)\s*s', error_msg, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1)) + 1.5
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
        
        # Multi-model pool for seamless failover when encountering RPD or TPM limits
        default_pool = [
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
            "qwen/qwen3.6-27b",
            "groq/compound-mini",
            "groq/compound"
        ]
        
        primary = model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        if primary in default_pool:
            default_pool.remove(primary)
        self.model_pool: List[str] = [primary] + default_pool
        self.model_index = 0
        
        self.max_retries = int(os.getenv("GROQ_MAX_RETRIES", "5"))
        self.max_desc_length = int(os.getenv("GROQ_MAX_DESC_LENGTH", "3000"))

    @property
    def current_model(self) -> str:
        return self.model_pool[self.model_index % len(self.model_pool)]

    def rotate_model(self):
        self.model_index = (self.model_index + 1) % len(self.model_pool)
        logger.info(f"[Model Failover] Switched active Groq model to: {self.current_model}")

    async def process_job(self, job: JobOffer, profile: Optional[CandidateProfile] = None) -> JobOffer:
        """
        Analyzes job posting with Groq LLM with candidate profile matching,
        salary estimation, fit scoring, and missing skills detection.
        """
        candidate = profile or CandidateProfile.load()

        clean_desc = (job.description or "").strip()
        if len(clean_desc) > self.max_desc_length:
            clean_desc = clean_desc[:self.max_desc_length] + "\n... [Description tronquée pour optimiser les tokens]"

        tech_str = ", ".join(candidate.tech_stack)
        loc_str = ", ".join(candidate.target_locations)
        contract_str = ", ".join(candidate.target_contracts)
        lang_str = ", ".join(candidate.languages)
        notes_str = candidate.custom_instructions or "N/A"

        prompt = f"""Tu es un recruteur tech expert analysant une offre d'emploi pour un profil candidat précis.

--- PROFIL DU CANDIDAT ---
- Niveau / Titre : {candidate.title}
- Types d'opportunités recherchées : {contract_str}
- Localisations cibles : {loc_str}
- Technologies maîtrisées : {tech_str}
- Langues : {lang_str}
- Instructions spécifiques : {notes_str}

--- OFFRE À ANALYSER ---
Titre du poste : {job.title}
Entreprise : {job.company}
Localisation : {job.location}
Description :
{clean_desc}

--- INSTRUCTIONS D'ANALYSE ---
Tu DOIS retourner UNIQUEMENT un objet JSON valide conforme à la structure suivante (sans aucun texte supplémentaire ni balise externe) :
{{
  "tech_stack": ["Liste", "des", "technologies", "mentionnées"],
  "fit_score": 8,
  "missing_skills": ["Liste", "des", "technologies/compétences", "demandées", "que", "le", "candidat", "ne", "maîtrise", "pas", "encore"],
  "salary_min": 45000,
  "salary_max": 55000,
  "salary_estimation": "45 000 € - 55 000 € / an",
  "bullshit_score": 3,
  "is_relevant": true,
  "summary": "Résumé concis en 2 phrases du poste et des exigences clés en français."
}}

Critères d'évaluation :
- "fit_score" (entier 1 à 10) :
  * 8-10 : Excellent match (adéquation forte avec sa stack maîtrisée [{tech_str}], contrat [{contract_str}], localisation [{loc_str}]).
  * 5-7 : Match modéré (stack proche ou facilement assimilable, niveau d'expérience accessible).
  * 1-4 : Faible match (ex: Lead/Senior +8 ans d'expérience, technologies non compatibles, ou hors critères).
- "missing_skills" : Les technologies ou frameworks demandés dans l'offre qui ne font PAS partie de sa stack actuelle ({tech_str}).
- "salary_min" & "salary_max" : Salaires bruts annuels en Euros sous forme d'entiers (ex: 42000, 52000). Si non mentionnés explicitement dans l'offre, estime une fourchette réaliste selon le marché local (Luxembourg, France, Remote) et le profil demandé.
- "bullshit_score" (entier 1 à 10) : Niveau de jargon corporate/buzzwords creux (10 = ultra jargon, 1 = description technique factuelle).
- "is_relevant" (booléen) : true si c'est un poste technique Software, Data, IA ou Web pertinent; false sinon.
"""

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": "Tu es un assistant RH et Tech spécialisé en recrutement. Tu renvoies TOUJOURS du JSON strict et valide."
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

                # Tech stack
                tech_stack = parsed_data.get("tech_stack", [])
                job.tech_stack = tech_stack if isinstance(tech_stack, list) else [str(tech_stack)]

                # Missing skills
                missing_skills = parsed_data.get("missing_skills", [])
                job.missing_skills = missing_skills if isinstance(missing_skills, list) else [str(missing_skills)]

                # Fit Score
                try:
                    job.fit_score = max(1, min(10, int(parsed_data.get("fit_score", 5))))
                except (ValueError, TypeError):
                    job.fit_score = 5

                # Salaries
                try:
                    s_min = parsed_data.get("salary_min")
                    job.salary_min = int(s_min) if s_min is not None else None
                except (ValueError, TypeError):
                    job.salary_min = None

                try:
                    s_max = parsed_data.get("salary_max")
                    job.salary_max = int(s_max) if s_max is not None else None
                except (ValueError, TypeError):
                    job.salary_max = None

                # Salary string estimation
                job.salary_estimation = str(parsed_data.get("salary_estimation", ""))
                if not job.salary_estimation or job.salary_estimation.lower() == "not provided":
                    if job.salary_min and job.salary_max:
                        job.salary_estimation = f"{job.salary_min // 1000}k€ - {job.salary_max // 1000}k€"
                    elif job.salary_min:
                        job.salary_estimation = f"À partir de {job.salary_min // 1000}k€"
                    elif job.salary_max:
                        job.salary_estimation = f"Jusqu'à {job.salary_max // 1000}k€"
                    else:
                        job.salary_estimation = "Non communiqué"

                # Bullshit & Relevance
                try:
                    job.bullshit_score = max(1, min(10, int(parsed_data.get("bullshit_score", 1))))
                except (ValueError, TypeError):
                    job.bullshit_score = 1

                job.is_relevant = bool(parsed_data.get("is_relevant", True))
                job.summary = str(parsed_data.get("summary", "Description disponible dans l'offre."))

                return job

            except RateLimitError as e:
                err_msg = str(e)
                wait_time = parse_retry_after(err_msg, default=3.0)
                logger.warning(
                    f"[RateLimit] Hit limit on {self.current_model} for '{job.title}' (attempt {attempt}/{self.max_retries})."
                )
                
                if "RPD" in err_msg or "requests per day" in err_msg or attempt >= 2:
                    self.rotate_model()
                    
                if attempt >= self.max_retries:
                    logger.error(f"[RateLimit] Exceeded max retries for job {job.url}.")
                    raise
                    
                await asyncio.sleep(min(wait_time, 5.0))

            except (APIConnectionError, APIStatusError) as e:
                backoff = min(2 ** attempt + 1.0, 15.0)
                logger.warning(
                    f"[API Error] on {self.current_model} for '{job.title}': {e}. Retrying in {backoff:.1f}s..."
                )
                self.rotate_model()
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(backoff)

            except json.JSONDecodeError as e:
                logger.error(f"[JSON Error] Failed to decode JSON from {self.current_model} for job {job.title}: {e}")
                self.rotate_model()
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"[Unexpected Error] on {self.current_model} for job {job.title}: {e}")
                self.rotate_model()
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(2.0)

        return job
