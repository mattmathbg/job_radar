import os
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loaders.sqlite_loader import SQLiteLoader

app = FastAPI(title="Job Radar API")
loader = SQLiteLoader()

@app.on_event("startup")
async def startup_db():
    await loader.init_db()

@app.get("/api/jobs")
async def get_jobs(
    location: Optional[str] = None,
    search: Optional[str] = None,
    relevant_only: bool = False,
    max_bullshit: Optional[int] = Query(None, ge=1, le=10)
):
    jobs = await loader.get_jobs(
        location=location,
        search=search,
        relevant_only=relevant_only,
        max_bullshit=max_bullshit
    )
    return {"jobs": jobs, "count": len(jobs)}

@app.get("/api/stats")
async def get_stats():
    return await loader.get_stats()

@app.get("/api/trends")
async def get_trends():
    return await loader.get_trends()

# Mount web directory for static frontend files
web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(web_dir, "index.html"))
