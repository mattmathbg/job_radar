import os
import asyncio
from typing import Optional
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loaders.sqlite_loader import SQLiteLoader
from models.profile import CandidateProfile

app = FastAPI(title="Job Radar API", version="2.1.0")
loader = SQLiteLoader()

@app.on_event("startup")
async def startup_db():
    await loader.init_db()

@app.get("/api/jobs")
async def get_jobs(
    location: Optional[str] = None,
    search: Optional[str] = None,
    relevant_only: bool = False,
    max_bullshit: Optional[int] = Query(None, ge=1, le=10),
    min_fit_score: Optional[int] = Query(None, ge=1, le=10),
    sort_by: Optional[str] = Query("fit_score_desc", regex="^(fit_score_desc|salary_desc|bullshit_asc|latest)$")
):
    jobs = await loader.get_jobs(
        location=location,
        search=search,
        relevant_only=relevant_only,
        max_bullshit=max_bullshit,
        min_fit_score=min_fit_score,
        sort_by=sort_by
    )
    return {"jobs": jobs, "count": len(jobs)}

@app.get("/api/stats")
async def get_stats():
    return await loader.get_stats()

@app.get("/api/trends")
async def get_trends():
    return await loader.get_trends()

@app.get("/api/profile")
async def get_profile():
    return CandidateProfile.load()

@app.post("/api/profile")
async def update_profile(profile: CandidateProfile):
    profile.save()
    return {"status": "success", "profile": profile}

# Mount web directory for static frontend files
web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(web_dir, "index.html"))
