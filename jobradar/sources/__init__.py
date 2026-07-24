"""Job search sources — one module per API."""

from jobradar.sources.remotive import RemotiveSearch
from jobradar.sources.arbeitnow import ArbeitnowSearch
from jobradar.sources.linkedin import LinkedInSearch
from jobradar.sources.remoteok import RemoteOKSearch
from jobradar.sources.jobicy import JobicySearch
from jobradar.sources.himalayas import HimalayasSearch

__all__ = [
    "RemotiveSearch",
    "ArbeitnowSearch",
    "LinkedInSearch",
    "RemoteOKSearch",
    "JobicySearch",
    "HimalayasSearch",
]
