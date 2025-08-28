# Standard library imports.
from dataclasses import dataclass
from typing import Optional

# Related third party imports.
import requests
from requests.structures import CaseInsensitiveDict


@dataclass(frozen=True)
class Author:
    uri: str
    first_name: str
    last_name: str
    orcid: str | None
    weight: int | None
    start: str | None
    end: str | None

@dataclass(frozen=True)
class AuthorWithWeight(Author):
    weight: int
    @classmethod
    def from_author(
        cls, author: Author, default_weight: int = 0, imposed_weight: int | None = None) \
    -> 'AuthorWithWeight':
        return AuthorWithWeight(
            uri=author.uri,
            first_name=author.first_name,
            last_name=author.last_name,
            orcid=author.orcid,
            weight=imposed_weight or author.weight or default_weight,
            start=author.start,
            end=author.end
        )


def citation(authors: list[AuthorWithWeight], as_contrib: bool = False) -> str:
    """Return the formatted citation json."""
    data_col = 'DataCollector' if as_contrib else ''
    data_cur = 'DataCurator' if as_contrib else ''
    data_dist = 'Distributor' if as_contrib else ''
    data_man = 'DataManager' if as_contrib else ''
    s = '"contributors": [' if as_contrib else '"creators": ['

    s = s + _inst_dcite_json('ICOS RI', data_dist)
    for author in authors:
        if author.weight > 0:
            p_json = _p_dcite_json(
                first_name=author.first_name,
                last_name=author.last_name,
                orcid=author.orcid,
                contrib_type=data_col)
            s = s + ',' + p_json
    s = s + ',' + _inst_dcite_json('ICOS Carbon Portal', data_cur)
    s = s + ',' + _inst_dcite_json('ICOS Atmosphere Thematic Centre', data_man)
    s = s + ',' + _inst_dcite_json('ICOS Flask And Calibration Laboratory', data_col)
    if as_contrib:
        s = s + ',' + _inst_dcite_json('ICOS Flask And Calibration Laboratory', data_cur)
    s = s + ',' + _inst_dcite_json('ICOS Central Radiocarbon Laboratory', data_cur)
    s = s + ' ]\n'
    return s


def _inst_dcite_json(name: str, contrib_type: Optional[str] = None) -> str:
    """Return the formatted institute datacite json."""
    s = '  {\n  "name" : {\n    "name" : "'+name+'",\n'
    s = s + '    "nameType" : "Organizational"\n  },\n'
    s = s + '  "affiliation" : [ ],\n'
    if contrib_type is not None:
        s = s + '  "contributorType" : "'+contrib_type+'",\n'
    s = s + '  "nameIdentifiers" : [ ]\n'
    s = s + '  }'
    return s


def _p_dcite_json(
        first_name: str, last_name: str, orcid: Optional[str] = None,
        affiliation: Optional[str] = None, contrib_type: Optional[str] = None) -> str:
    """Return the formatted person datacite json."""
    s = ('  {\n  "name" : {\n    "familyName" : "' + last_name + '",\n' +
         '    "givenName" : "' + first_name + '",\n' +
         '    "nameType" : "Personal"\n  },\n')
    if affiliation is not None:
        s = s + '  "affiliation" : "' + affiliation + '",\n'
    else:
        s = s + '  "affiliation" : [ ],\n'
    if contrib_type is not None:
        s = s + '  "contributorType" : "' + contrib_type + '",\n'
    if orcid is not None:
        s = (s + '  "nameIdentifiers" : [ {\n' + '    "nameIdentifier" : "' +
             orcid + '",\n    "scheme" : {\n')
        s = s + '      "nameIdentifierScheme" : "ORCID",\n'
        s = s + '      "schemeUri" : "http://orcid.org/"\n    } \n  } ]\n '
    else:
        s = s + '  "nameIdentifiers" : [ ]\n'
    s = s + '  }'
    return s


def doi_citation(doi: str, citation_style: str = 'elsevier-harvard') -> str:
    url = f'https://doi.org/{doi}'
    headers: CaseInsensitiveDict[str] = CaseInsensitiveDict()
    headers['Accept'] = f'text/x-bibliography; style={citation_style}'
    resp = requests.get(url, headers=headers)
    if resp.ok:
        return resp.text
    else:
        print(f'Citation not found for DOI {url}.')
        return 'citation not found'
