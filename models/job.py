from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime

class JobOffer(BaseModel):
    # Données extraites
    id: str
    title: str
    company: str
    location: str
    url: str
    date_posted: Optional[str] = None
    description: str

    # Données enrichies par LLM
    tech_stack: Optional[List[str]] = None
    salary_estimation: Optional[str] = None
    bullshit_score: Optional[int] = None
    is_relevant: Optional[bool] = None
    summary: Optional[str] = None
