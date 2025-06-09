# Standard library imports.
from typing import Optional

# Related third party imports.
import pandas as pd

# Local application/library specific imports.
from icoscp_obspack.config import Config

def citation(config: Config, as_contrib: bool = False) -> str:
    """Return the formatted citation json."""
    data_col = 'DataCollector' if as_contrib else ''
    data_cur = 'DataCurator' if as_contrib else ''
    data_dist = 'Distributor' if as_contrib else ''
    data_man = 'DataManager' if as_contrib else ''
    s = '"contributors": [' if as_contrib else '"creators": ['

    s = s + _inst_dcite_json('ICOS RI', data_dist)
    for i, person in config.col_contribs.iterrows():
        if person['weight'] > 0:
            p_json = _p_dcite_json(first_name=person['fname'],
                                  last_name=person['lname'],
                                  orcid=person['orcid'],
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


def _p_dcite_json(first_name: str, last_name: str,
                 orcid: Optional[str] = None, affiliation: Optional[str] = None,
                 contrib_type: Optional[str] = None) -> str:
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


def cleanup_author_list(contribs: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicates in the author list."""
    contribs = contribs.sort_values('lname', ascending=False).\
        drop_duplicates(subset=['fname', 'lname'])
    contribs.loc[contribs['weight'].isnull(), 'weight'] = 0
    contribs['wght'] = 100 - contribs.weight.astype(int)
    contribs = contribs.sort_values(by=['wght', 'lname'], ascending=True)
    return contribs
