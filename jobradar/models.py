"""Data models for JobRadar."""

from dataclasses import dataclass, field
from typing import List, Optional

import yaml


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    salary: str = ""
    source: str = ""
    remote: bool = False
    tags: List[str] = field(default_factory=list)
    posted: str = ""
    # AI ratings
    score: int = 0
    rating: str = ""
    reasoning: str = ""
    skills_match: int = 0
    experience_fit: int = 0
    salary_fit: int = 0
    remote_fit: int = 0


@dataclass
class Profile:
    name: str = "User"
    title: str = ""
    experience_years: int = 0
    skills: List[str] = field(default_factory=list)
    desired_roles: List[str] = field(default_factory=list)
    salary_min: int = 0
    salary_max: int = 0
    location_preference: str = ""
    remote_ok: bool = True
    industries: List[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str) -> "Profile":
        """Load a Profile from a YAML file.

        Raises FileNotFoundError if the file does not exist, or ValueError
        if the YAML is invalid.
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError(f"Profile YAML must be a mapping, got {type(data).__name__}")
        known = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in known}
        unknown = set(data.keys()) - known
        if unknown:
            # Warn but don't fail — allow forward-compatible profiles
            import warnings
            warnings.warn(f"Unknown profile fields ignored: {unknown}")
        return cls(**filtered)
