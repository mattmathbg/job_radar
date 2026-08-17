import asyncio
import logging
from typing import List
import uuid

from jobspy import scrape_jobs
from models.job import JobOffer
from .base import BaseExtractor

logger = logging.getLogger(__name__)

class JobSpyExtractor(BaseExtractor):
    def __init__(self, sites: List[str] = None):
        self.sites = sites or ["linkedin", "indeed"]

    async def extract(self, roles: List[str], locations: List[str]) -> List[JobOffer]:
        all_jobs = []
        for role in roles:
            for location in locations:
                logger.info(f"Scraping for role '{role}' in '{location}' via JobSpy...")
                try:
                    jobs_df = await asyncio.to_thread(
                        scrape_jobs,
                        site_name=self.sites,
                        search_term=role,
                        location=location,
                        results_wanted=20,
                    )

                    if jobs_df is None or jobs_df.empty:
                        logger.info(f"No jobs found for {role} in {location}")
                        continue

                    for _, row in jobs_df.iterrows():
                        desc = str(row.get("description", ""))
                        if not desc or desc.lower() == "nan":
                            continue
                            
                        date_posted = str(row.get("date_posted", "")) if row.get("date_posted") else None

                        job_offer = JobOffer(
                            id=str(row.get("id", uuid.uuid4())),
                            title=str(row.get("title", "Unknown")),
                            company=str(row.get("company", "Unknown")),
                            location=str(row.get("location", "Unknown")),
                            url=str(row.get("job_url", "")),
                            date_posted=date_posted,
                            description=desc
                        )
                        all_jobs.append(job_offer)
                except Exception as e:
                    logger.error(f"Error scraping {role} in {location}: {e}")
                    
        return all_jobs
