# Standard library imports.
from dataclasses import dataclass
from typing import Literal, TypeAlias

Envri: TypeAlias = Literal['ICOS', 'SITES', 'ICOSCities']


@dataclass(frozen=True)
class EnvriConfig:
    envri: Envri
    meta_resources_prefix: str
    station_prefix: str
    meta_staging_url: str
    meta_url: str
    sparql: str
    try_ingest_url: str
    who_am_i: str


ICOS_CONFIG = EnvriConfig(
    envri='ICOS',
    meta_resources_prefix='http://meta.icos-cp.eu/resources/cpmeta/',
    station_prefix='https://meta.icos-cp.eu/resources/stations/',
    meta_staging_url='https://metastaging.icos-cp.eu/upload',
    meta_url='https://meta.icos-cp.eu/upload',
    sparql='https://meta.icos-cp.eu/sparql',
    try_ingest_url='https://data.icos-cp.eu/tryingest',
    who_am_i='https://cpauth.icos-cp.eu/whoami',
)

SITES_CONFIG = EnvriConfig(
    envri='SITES',
    meta_resources_prefix='easter_egg',
    station_prefix='easter_egg',
    meta_staging_url='easter_egg',
    meta_url='easter_egg',
    sparql='easter_egg',
    try_ingest_url='easter_egg',
    who_am_i='easter_egg',
)

CITIES_CONFIG = EnvriConfig(
    envri='ICOSCities',
    meta_resources_prefix='https://citymeta.icos-cp.eu/resources/cpmeta/',
    station_prefix='https://citymeta.icos-cp.eu/resources/stations/',
    meta_staging_url='https://citymetastaging.icos-cp.eu/upload',
    meta_url='https://citymeta.icos-cp.eu/upload',
    sparql='https://citymeta.icos-cp.eu/sparql',
    try_ingest_url='https://citydata.icos-cp.eu/tryingest',
    who_am_i='https://cpauth.icos-cp.eu/whoami',
)

ENVRIES: dict[Envri, EnvriConfig] = {
    'ICOS': ICOS_CONFIG,
    'SITES': SITES_CONFIG,
    'ICOSCities': CITIES_CONFIG
}
