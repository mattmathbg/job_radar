import os
import asyncio
import logging
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from extractors.jobspy_extractor import JobSpyExtractor
from processors.groq_processor import GroqProcessor
from loaders.sqlite_loader import SQLiteLoader
from api import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_etl():
    logger.info("Starting ETL Pipeline...")
    try:
        loader = SQLiteLoader()
        await loader.init_db()
        
        extractor = JobSpyExtractor()
        
        roles = ["Software Engineer", "Data Engineer"]
        locations = ["Luxembourg", "France", "Remote"]
        
        # 1. Extract
        logger.info("--- EXTRACTION PHASE ---")
        raw_jobs = await extractor.extract(roles=roles, locations=locations)
        logger.info(f"Extracted {len(raw_jobs)} raw jobs.")

        # 2. Collect jobs to process (newly extracted + existing jobs needing AI enrichment)
        jobs_to_process = []
        for job in raw_jobs:
            if not await loader.job_exists(job.url):
                jobs_to_process.append(job)

        # Also queue existing jobs that need backfill of fit_score / salary
        backfill_jobs = await loader.get_jobs_needing_enrichment(limit=25)
        existing_urls = {j.url for j in jobs_to_process}
        for bj in backfill_jobs:
            if bj.url not in existing_urls:
                jobs_to_process.append(bj)

        total_jobs = len(jobs_to_process)
        logger.info(f"Found {total_jobs} total jobs to process/enrich with LLM.")

        if not jobs_to_process:
            logger.info("No jobs to process. Pipeline is up-to-date.")
            return

        # 3. Process & Load
        logger.info("--- PROCESSING & LOADING PHASE ---")
        processor = None
        try:
            processor = GroqProcessor()
        except Exception as e:
            logger.error(f"Failed to initialize GroqProcessor: {e}")

        pacing_delay = float(os.getenv("GROQ_PACING_DELAY", "2.0"))
        new_jobs_processed = 0
        
        for idx, job in enumerate(jobs_to_process, 1):
            try:
                if processor:
                    logger.info(f"[{idx}/{total_jobs}] Analyzing with Groq LLM: {job.title} at {job.company}")
                    processed_job = await processor.process_job(job)
                    await loader.save_job(processed_job)
                    await asyncio.sleep(pacing_delay)
                else:
                    job.summary = "Description disponible dans l'offre."
                    job.is_relevant = True
                    job.bullshit_score = 1
                    job.fit_score = 5
                    job.tech_stack = []
                    job.missing_skills = []
                    await loader.save_job(job)
                new_jobs_processed += 1
            except Exception as e:
                logger.error(f"Failed to process job {job.title} ({job.url}): {e}")
                # Save raw job if LLM processing fails so data is preserved
                job.summary = "Analyse IA temporairement indisponible."
                job.is_relevant = True
                job.bullshit_score = 1
                job.fit_score = 5
                job.tech_stack = []
                job.missing_skills = []
                await loader.save_job(job)
                new_jobs_processed += 1
                
        logger.info(f"ETL Pipeline Finished. Processed and saved {new_jobs_processed} jobs.")
    except Exception as e:
        logger.error(f"Critical error in ETL pipeline execution: {e}", exc_info=True)

async def main():
    logger.info("Starting Job Radar Service...")
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_etl, 'cron', hour=8, minute=0)
    
    # Run ETL once at startup in background task
    asyncio.create_task(run_etl())
    
    scheduler.start()
    
    # Start Web API Server
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
