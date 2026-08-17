import json
import logging
import aiosqlite
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from models.job import JobOffer

logger = logging.getLogger(__name__)

class SQLiteLoader:
    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # 1. Base table creation
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
                    summary TEXT,
                    fit_score INTEGER DEFAULT 1,
                    missing_skills TEXT DEFAULT '[]',
                    salary_min INTEGER,
                    salary_max INTEGER,
                    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

            # 2. Schema migration / ALTER TABLE for existing databases
            new_columns = [
                ("fit_score", "INTEGER DEFAULT 1"),
                ("missing_skills", "TEXT DEFAULT '[]'"),
                ("salary_min", "INTEGER"),
                ("salary_max", "INTEGER"),
                ("added_at", "DATETIME"),
            ]
            for col_name, col_type in new_columns:
                try:
                    await db.execute(f"ALTER TABLE job_offers ADD COLUMN {col_name} {col_type}")
                    await db.commit()
                    logger.info(f"Added column {col_name} to job_offers table.")
                except Exception as e:
                    # Column already exists or handled
                    logger.debug(f"ALTER TABLE for {col_name}: {e}")

            # Populate added_at for legacy rows if null
            try:
                await db.execute("UPDATE job_offers SET added_at = datetime('now') WHERE added_at IS NULL")
                await db.commit()
            except Exception as e:
                logger.debug(f"Backfill added_at: {e}")

    async def job_exists(self, url: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM job_offers WHERE url = ?", (url,)) as cursor:
                result = await cursor.fetchone()
                return result is not None

    async def get_jobs_needing_enrichment(self, limit: int = 30) -> List[JobOffer]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM job_offers 
                WHERE salary_min IS NULL OR fit_score IS NULL OR fit_score = 1
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                jobs = []
                for r in rows:
                    item = dict(r)
                    try:
                        techs = json.loads(item.get("tech_stack") or "[]")
                    except Exception:
                        techs = []
                    try:
                        missing = json.loads(item.get("missing_skills") or "[]")
                    except Exception:
                        missing = []
                        
                    job = JobOffer(
                        id=item["id"],
                        title=item["title"] or "",
                        company=item["company"] or "",
                        location=item["location"] or "",
                        url=item["url"] or "",
                        date_posted=item.get("date_posted"),
                        description=item.get("description") or "",
                        tech_stack=techs,
                        salary_estimation=item.get("salary_estimation"),
                        salary_min=item.get("salary_min"),
                        salary_max=item.get("salary_max"),
                        bullshit_score=item.get("bullshit_score"),
                        fit_score=item.get("fit_score"),
                        missing_skills=missing,
                        is_relevant=bool(item.get("is_relevant")),
                        summary=item.get("summary")
                    )
                    jobs.append(job)
                return jobs

    async def save_job(self, job: JobOffer):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                await db.execute("""
                    INSERT INTO job_offers (
                        id, title, company, location, url, date_posted, description,
                        tech_stack, salary_estimation, bullshit_score, is_relevant, summary,
                        fit_score, missing_skills, salary_min, salary_max, added_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        tech_stack=excluded.tech_stack,
                        salary_estimation=excluded.salary_estimation,
                        bullshit_score=excluded.bullshit_score,
                        is_relevant=excluded.is_relevant,
                        summary=excluded.summary,
                        fit_score=excluded.fit_score,
                        missing_skills=excluded.missing_skills,
                        salary_min=excluded.salary_min,
                        salary_max=excluded.salary_max
                """, (
                    job.id,
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    job.date_posted,
                    job.description,
                    json.dumps(job.tech_stack or []),
                    job.salary_estimation,
                    job.bullshit_score,
                    job.is_relevant,
                    job.summary,
                    job.fit_score if job.fit_score is not None else 1,
                    json.dumps(job.missing_skills or []),
                    job.salary_min,
                    job.salary_max,
                    now_str
                ))
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to save job {job.id} to DB: {e}")

    async def get_jobs(
        self,
        location: Optional[str] = None,
        search: Optional[str] = None,
        relevant_only: bool = False,
        max_bullshit: Optional[int] = None,
        min_fit_score: Optional[int] = None,
        sort_by: Optional[str] = "fit_score_desc"
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

            if min_fit_score is not None:
                query += " AND fit_score >= ?"
                params.append(min_fit_score)

            if search:
                query += " AND (LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tech_stack) LIKE ? OR LOWER(missing_skills) LIKE ?)"
                search_param = f"%{search.lower()}%"
                params.extend([search_param, search_param, search_param, search_param, search_param])

            # Sorting logic
            if sort_by == "fit_score_desc":
                query += " ORDER BY COALESCE(fit_score, 0) DESC, id DESC"
            elif sort_by == "salary_desc":
                query += " ORDER BY COALESCE(salary_max, salary_min, 0) DESC, id DESC"
            elif sort_by == "bullshit_asc":
                query += " ORDER BY COALESCE(bullshit_score, 10) ASC, id DESC"
            else:
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

                    try:
                        item["missing_skills"] = json.loads(item.get("missing_skills") or "[]")
                    except Exception:
                        item["missing_skills"] = []

                    item["is_relevant"] = bool(item.get("is_relevant"))
                    item["fit_score"] = item.get("fit_score") if item.get("fit_score") is not None else 1
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

            async with db.execute("SELECT AVG(fit_score) as avg_fit FROM job_offers WHERE fit_score IS NOT NULL AND fit_score > 1") as cursor:
                fit_row = await cursor.fetchone()
                avg_fit = round(fit_row["avg_fit"], 1) if fit_row and fit_row["avg_fit"] is not None else 0.0

            return {
                "total_jobs": total_jobs,
                "relevant_jobs": relevant_jobs,
                "avg_bullshit_score": avg_bs,
                "avg_fit_score": avg_fit
            }

    async def get_trends(self) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Check columns to safely query added_at
            cursor = await db.execute("PRAGMA table_info(job_offers)")
            col_info = await cursor.fetchall()
            existing_cols = [c[1] for c in col_info]
            
            query_cols = ["tech_stack", "location", "bullshit_score", "is_relevant", "fit_score", "salary_min", "salary_max", "date_posted"]
            if "added_at" in existing_cols:
                query_cols.append("added_at")
                
            query_str = f"SELECT {', '.join(query_cols)} FROM job_offers"
            
            async with db.execute(query_str) as cursor:
                rows = await cursor.fetchall()
                
            tech_counts: Dict[str, int] = {}
            tech_by_location_raw: Dict[str, Dict[str, int]] = {}
            tech_bs_scores: Dict[str, List[int]] = {}
            location_counts: Dict[str, int] = {}
            salary_by_location_raw: Dict[str, List[float]] = {}
            fit_by_location_raw: Dict[str, List[int]] = {}

            # Historical date counts by location bucket
            history_date_counts: Dict[str, Dict[str, int]] = {}
            all_dates_set = set()
            
            for row in rows:
                row_dict = dict(row)
                loc = row_dict.get("location") or "Unknown"
                loc_lower = loc.lower()
                
                if "remote" in loc_lower or "télétravail" in loc_lower or "distanciel" in loc_lower:
                    loc_bucket = "Remote"
                elif "luxembourg" in loc_lower:
                    loc_bucket = "Luxembourg"
                elif "france" in loc_lower or "paris" in loc_lower or "metz" in loc_lower or "nancy" in loc_lower or "strasbourg" in loc_lower or "lyon" in loc_lower:
                    loc_bucket = "France"
                else:
                    loc_bucket = "Autres"

                location_counts[loc_bucket] = location_counts.get(loc_bucket, 0) + 1

                # Date parsing for historical trend (fallback to date_posted or added_at or 2026-08-17)
                raw_date = row_dict.get("date_posted") or (str(row_dict.get("added_at"))[:10] if row_dict.get("added_at") else None)
                if not raw_date or len(raw_date) < 10:
                    raw_date = "2026-08-17"
                date_clean = raw_date[:10]
                all_dates_set.add(date_clean)

                if date_clean not in history_date_counts:
                    history_date_counts[date_clean] = {}
                history_date_counts[date_clean][loc_bucket] = history_date_counts[date_clean].get(loc_bucket, 0) + 1
                
                # Tech stack parsing
                try:
                    techs = json.loads(row_dict.get("tech_stack") or "[]")
                except Exception:
                    techs = []
                    
                bs = row_dict.get("bullshit_score")
                fit = row_dict.get("fit_score")
                s_min = row_dict.get("salary_min")
                s_max = row_dict.get("salary_max")

                # Salary aggregation (average of salary_min and salary_max)
                if s_min is not None or s_max is not None:
                    if s_min is not None and s_max is not None:
                        avg_s = (s_min + s_max) / 2.0
                    else:
                        avg_s = float(s_min if s_min is not None else s_max)
                    
                    if loc_bucket not in salary_by_location_raw:
                        salary_by_location_raw[loc_bucket] = []
                    salary_by_location_raw[loc_bucket].append(avg_s)

                if fit is not None:
                    if loc_bucket not in fit_by_location_raw:
                        fit_by_location_raw[loc_bucket] = []
                    fit_by_location_raw[loc_bucket].append(fit)
                
                for t in techs:
                    t_clean = t.strip()
                    if not t_clean:
                        continue
                    
                    tech_counts[t_clean] = tech_counts.get(t_clean, 0) + 1
                    
                    if loc_bucket not in tech_by_location_raw:
                        tech_by_location_raw[loc_bucket] = {}
                    tech_by_location_raw[loc_bucket][t_clean] = tech_by_location_raw[loc_bucket].get(t_clean, 0) + 1
                    
                    if bs is not None:
                        if t_clean not in tech_bs_scores:
                            tech_bs_scores[t_clean] = []
                        tech_bs_scores[t_clean].append(bs)

            # Top 15 technologies globally
            top_tech = sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:15]
            
            # Top 5 technologies for EACH region
            tech_by_location: Dict[str, List[Dict[str, Any]]] = {}
            for loc, t_dict in tech_by_location_raw.items():
                sorted_loc_tech = sorted(t_dict.items(), key=lambda x: x[1], reverse=True)[:5]
                tech_by_location[loc] = [{"name": name, "count": count} for name, count in sorted_loc_tech]

            # Average Salary per location
            avg_salary_by_location: Dict[str, int] = {}
            for loc, sal_list in salary_by_location_raw.items():
                if sal_list:
                    avg_salary_by_location[loc] = int(round(sum(sal_list) / len(sal_list)))

            # Average Fit score per location
            avg_fit_by_location: Dict[str, float] = {}
            for loc, fit_list in fit_by_location_raw.items():
                if fit_list:
                    avg_fit_by_location[loc] = round(sum(fit_list) / len(fit_list), 1)

            # Average Bullshit Score per top technology
            avg_bs_per_tech = {}
            for t, _ in top_tech:
                scores = tech_bs_scores.get(t, [])
                avg_bs_per_tech[t] = round(sum(scores) / len(scores), 1) if scores else 0.0

            # Build history_trends with sorted chronological dates
            sorted_dates = sorted(list(all_dates_set))
            target_regions = ["Luxembourg", "France", "Remote", "Autres"]
            series: Dict[str, List[int]] = {reg: [] for reg in target_regions}
            
            for d in sorted_dates:
                d_counts = history_date_counts.get(d, {})
                for reg in target_regions:
                    series[reg].append(d_counts.get(reg, 0))

            history_trends = {
                "dates": sorted_dates,
                "series": series
            }

            return {
                "top_technologies": [{"name": k, "count": v} for k, v in top_tech],
                "location_distribution": location_counts,
                "tech_by_location": tech_by_location,
                "avg_salary_by_location": avg_salary_by_location,
                "avg_fit_by_location": avg_fit_by_location,
                "avg_bs_per_tech": avg_bs_per_tech,
                "history_trends": history_trends,
                "total_analyzed_jobs": len(rows)
            }
