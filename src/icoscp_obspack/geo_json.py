# Standard library imports.
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

# Local application/library specific imports.
from icoscp_obspack.doi import EnhancedJSONEncoder

GeometryType: TypeAlias = Literal['Point']
GeoFeatureType: TypeAlias = Literal['Feature']
GeoJsonType: TypeAlias = Literal['FeatureCollection']

@dataclass(frozen=True)
class Geometry:
    coordinates: tuple[float, float]
    type: GeometryType

@dataclass(frozen=True)
class GeoProperties:
    label: str

@dataclass(frozen=True)
class GeoFeature:
    geometry: Geometry
    properties: GeoProperties
    type: GeoFeatureType

@dataclass(frozen=True)
class GeoJson:
    features: list[GeoFeature]
    type: GeoJsonType

def produce_geo_json(geo_json: GeoJson, path_to_file: Path):
    with open(path_to_file, 'w') as geo_json_f:
        json.dump(geo_json, geo_json_f, cls=EnhancedJSONEncoder)