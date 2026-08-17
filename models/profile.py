import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field

PROFILE_FILE_PATH = os.getenv("PROFILE_FILE_PATH", "data/profile.json")

DEFAULT_PROFILE = {
    "title": "Étudiant L3 → M1 Informatique",
    "target_roles": ["Software Engineer", "Data Engineer", "AI Engineer"],
    "target_contracts": ["Stage", "Alternance", "Junior"],
    "target_locations": ["Luxembourg", "France", "Remote"],
    "tech_stack": [
        "Python",
        "FastAPI",
        "Streamlit",
        "Docker",
        "LangGraph",
        "MongoDB",
        "SQLite"
    ],
    "languages": [
        "Français (natif)",
        "Anglais (technique courant)"
    ],
    "custom_instructions": "Recherche activement une opportunité junior, stage ou alternance technique stimulante avec forte composante Python / Data / IA."
}

class CandidateProfile(BaseModel):
    title: str = "Étudiant L3 → M1 Informatique"
    target_roles: List[str] = Field(default_factory=lambda: ["Software Engineer", "Data Engineer", "AI Engineer"])
    target_contracts: List[str] = Field(default_factory=lambda: ["Stage", "Alternance", "Junior"])
    target_locations: List[str] = Field(default_factory=lambda: ["Luxembourg", "France", "Remote"])
    tech_stack: List[str] = Field(default_factory=lambda: [
        "Python", "FastAPI", "Streamlit", "Docker", "LangGraph", "MongoDB", "SQLite"
    ])
    languages: List[str] = Field(default_factory=lambda: [
        "Français (natif)", "Anglais (technique courant)"
    ])
    custom_instructions: Optional[str] = "Recherche activement une opportunité junior, stage ou alternance technique."

    @classmethod
    def load(cls, file_path: str = PROFILE_FILE_PATH) -> "CandidateProfile":
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(**data)
            except Exception:
                pass
        
        # Save default if not exists
        profile = cls(**DEFAULT_PROFILE)
        profile.save(file_path)
        return profile

    def save(self, file_path: str = PROFILE_FILE_PATH):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.dict(), f, indent=2, ensure_ascii=False)
