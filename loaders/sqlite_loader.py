import json
import logging
import aiosqlite
import os
from typing import List, Optional, Dict, Any
from models.job import JobOffer

logger = logging.getLogger(__name__)

class SQLiteLoader:
    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS job_offers (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    company TEXT,
                    location TEXT,
                    url TEXT UNIQUE,
                    date_posted TEXT,
                    description TEXT,
                    tech_stack TEXT,
                    salary_estimation TEXT,
                    bullshit_score INTEGER,
                    is_relevant BOOLEAN,
                    summary TEXT
                )
            """)
            await db.commit()

    async def job_exists(self, url: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM job_offers WHERE url = ?", (url,)) as cursor:
                result = await cursor.fetchone()
                return result is not None

    async def save_job(self, job: JobOffer):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT OR IGNORE INTO job_offers (
                        id, title, company, location, url, date_posted, description,
                        tech_stack, salary_estimation, bullshit_score, is_relevant, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.id, job.title, job.company, job.location, job.url, job.date_posted, job.description,
                    json.dumps(job.tech_stack) if job.tech_stack else '[]',
                    job.salary_estimation,
                    job.bullshit_score,
                    job.is_relevant,
                    job.summary
                ))
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save job {job.id} to DB: {e}")

    async def get_jobs(
        self,
        location: Optional[str] = None,
        search: Optional[str] = None,
        relevant_only: bool = False,
        max_bullshit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM job_offers WHERE 1=1"
            params = []

            if relevant_only:
                query += " AND is_relevant = 1"

            if location and location.lower() != "all":
                query += " AND LOWER(location) LIKE ?"
                params.append(f"%{location.lower()}%")

            if max_bullshit is not None:
                query += " AND bullshit_score <= ?"
                params.append(max_bullshit)

            if search:
                query += " AND (LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tech_stack) LIKE ?)"
                search_param = f"%{search.lower()}%"
                params.extend([search_param, search_param, search_param, search_param])

            query += " ORDER BY id DESC"

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                result = []
                for r in rows:
                    item = dict(r)
                    try:
                        item["tech_stack"] = json.loads(item.get("tech_stack") or "[]")
                    except Exception:
                        item["tech_stack"] = []
                    item["is_relevant"] = bool(item.get("is_relevant"))
                    result.append(item)
                return result

    async def get_stats(self) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute("SELECT COUNT(*) as count FROM job_offers") as cursor:
                total_row = await cursor.fetchone()
                total_jobs = total_row["count"] if total_row else 0
                
            async with db.execute("SELECT COUNT(*) as count FROM job_offers WHERE is_relevant = 1") as cursor:
                rel_row = await cursor.fetchone()
                relevant_jobs = rel_row["count"] if rel_row else 0

            async with db.execute("SELECT AVG(bullshit_score) as avg_bs FROM job_offers WHERE bullshit_score IS NOT NULL") as cursor:
                bs_row = await cursor.fetchone()
                avg_bs = round(bs_row["avg_bs"], 1) if bs_row and bs_row["avg_bs"] is not None else 0.0

            return {
                "total_jobs": total_jobs,
                "relevant_jobs": relevant_jobs,
                "avg_bullshit_score": avg_bs
            }

    async def get_trends(self) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT tech_stack, location, bullshit_score, is_relevant FROM job_offers") as cursor:
                rows = await cursor.fetchall()
                
            tech_counts: Dict[str, int] = {}
            tech_by_location: Dict[str, Dict[str, int]] = {}
            tech_bs_scores: Dict[str, List[int]] = {}
            location_counts: Dict[str, int] = {}
            
            for row in rows:
                loc = row["location"] or "Unknown"
                loc_bucket = "Remote" if "remote" in loc.lower() else ("Luxembourg" if "luxembourg" in loc.lower() else ("France" if "france" in loc.lower() else "Autres"))
                location_counts[loc_bucket] = location_counts.get(loc_bucket, 0) + 1
                
                try:
                    techs = json.loads(row["tech_stack"] or "[]")
                except Exception:
                    techs = []
                    
                bs = row["bullshit_score"]
                
                for t in techs:
                    t_clean = t.strip()
                    if not t_clean:
                        continue
                    
                    tech_counts[t_clean] = tech_counts.get(t_clean, 0) + 1
                    
                    if loc_bucket not in tech_by_location:
                        tech_by_location[loc_bucket] = {}
                    tech_by_location[loc_bucket][t_clean] = tech_by_location[loc_bucket].get(t_clean, 0) + 1
                    
                    if bs is not None:
                        if t_clean not in tech_bs_scores:
                            tech_bs_scores[t_clean] = []
                        tech_bs_scores[t_clean].append(bs)

            # Top 15 technologies
            top_tech = sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:15]
            
            # Average Bullshit Score per top technology
            avg_bs_per_tech = {}
            for t, _ in top_tech:
                scores = tech_bs_scores.get(t, [])
                avg_bs_per_tech[t] = round(sum(scores) / len(scores), 1) if scores else 0.0

            return {
                "top_technologies": [{"name": k, "count": v} for k, v in top_tech],
                "location_distribution": location_counts,
                "tech_by_location": tech_by_location,
                "avg_bs_per_tech": avg_bs_per_tech,
                "total_analyzed_jobs": len(rows)
            }
