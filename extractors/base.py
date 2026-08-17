from abc import ABC, abstractmethod
from typing import List
from models.job import JobOffer

class BaseExtractor(ABC):
    @abstractmethod
    async def extract(self, roles: List[str], locations: List[str]) -> List[JobOffer]:
        """
        Extrait les offres d'emploi pour les rôles et localisations donnés.
        """
        pass
