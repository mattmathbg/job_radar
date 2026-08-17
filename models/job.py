from typing import List, Optional
from pydantic import BaseModel, Field

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
    tech_stack: Optional[List[str]] = Field(default_factory=list)
    salary_estimation: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    bullshit_score: Optional[int] = None
    fit_score: Optional[int] = None
    missing_skills: Optional[List[str]] = Field(default_factory=list)
    is_relevant: Optional[bool] = None
    summary: Optional[str] = None
