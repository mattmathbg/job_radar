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
        
        if not raw_jobs:
            logger.info("No raw jobs found during extraction.")
            return

        # 2. Process & 3. Load
        logger.info("--- PROCESSING & LOADING PHASE ---")
        processor = None
        try:
            processor = GroqProcessor()
        except Exception as e:
            logger.error(f"Failed to initialize GroqProcessor: {e}")

        # Filter out existing jobs first
        jobs_to_process = []
        for job in raw_jobs:
            if await loader.job_exists(job.url):
                logger.debug(f"Job already in DB: {job.title} at {job.company}")
            else:
                jobs_to_process.append(job)

        total_new_jobs = len(jobs_to_process)
        logger.info(f"Found {total_new_jobs} new jobs to process and save.")

        pacing_delay = float(os.getenv("GROQ_PACING_DELAY", "2.0"))
        new_jobs_processed = 0
        
        for idx, job in enumerate(jobs_to_process, 1):
            try:
                if processor:
                    logger.info(f"[{idx}/{total_new_jobs}] Processing with Groq LLM: {job.title} at {job.company}")
                    processed_job = await processor.process_job(job)
                    await loader.save_job(processed_job)
                    # Pacing delay between API calls to prevent exceeding Rate Limits (TPM / RPM)
                    await asyncio.sleep(pacing_delay)
                else:
                    # Fallback if processor is disabled
                    job.summary = "Description disponible dans l'offre."
                    job.is_relevant = True
                    job.bullshit_score = 1
                    job.tech_stack = []
                    await loader.save_job(job)
                new_jobs_processed += 1
            except Exception as e:
                logger.error(f"Failed to process job {job.title} ({job.url}): {e}")
                # Save raw job if LLM processing fails so data is not lost
                job.summary = "Analyse IA temporairement indisponible."
                job.is_relevant = True
                job.bullshit_score = 1
                job.tech_stack = []
                await loader.save_job(job)
                new_jobs_processed += 1
                
        logger.info(f"ETL Pipeline Finished. Processed and saved {new_jobs_processed} new jobs.")
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
