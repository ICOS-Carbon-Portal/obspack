from datetime import datetime


def dobjs_from_spec_list(specs: list[str], submitted_after: datetime) -> str:
    return f"""prefix cpmeta: <http://meta.icos-cp.eu/ontologies/cpmeta/>
prefix prov: <http://www.w3.org/ns/prov#>
prefix xsd: <http://www.w3.org/2001/XMLSchema#>
select ?dobj
where {{
    VALUES ?spec {{{"> <".join(specs)}}}
    ?dobj cpmeta:hasObjectSpec ?spec .
    BIND(EXISTS{{[] cpmeta:isNextVersionOf ?dobj}} AS ?hasNextVersion)
    ?dobj cpmeta:hasSizeInBytes ?size .
    ?dobj cpmeta:hasName ?fileName .
    ?dobj cpmeta:wasSubmittedBy/prov:endedAtTime ?submTime .
    ?dobj cpmeta:hasStartTime | (cpmeta:wasAcquiredBy / prov:startedAtTime) ?timeStart .
    ?dobj cpmeta:hasEndTime | (cpmeta:wasAcquiredBy / prov:endedAtTime) ?timeEnd .
    FILTER NOT EXISTS {{[] cpmeta:isNextVersionOf ?dobj}}
    FILTER( ?submTime >= {submitted_after.isoformat(timespec='milliseconds')}'Z'^^xsd:dateTime )
}}
order by desc(?submTime)
"""


def metadata_from_spec_list_old_query(specs: list[str]) -> str:
    return f"""prefix cpmeta: <http://meta.icos-cp.eu/ontologies/cpmeta/>
prefix prov: <http://www.w3.org/ns/prov#>
prefix xsd: <http://www.w3.org/2001/XMLSchema#>
select ?dobj ?hasNextVersion ?spec ?fileName ?size ?submTime ?timeStart ?timeEnd
where {{
    VALUES ?spec {{{"> <".join(specs)}}}
    ?dobj cpmeta:hasObjectSpec ?spec .
    BIND(EXISTS{{[] cpmeta:isNextVersionOf ?dobj}} AS ?hasNextVersion)
    ?dobj cpmeta:hasSizeInBytes ?size .
?dobj cpmeta:hasName ?fileName .
?dobj cpmeta:wasSubmittedBy/prov:endedAtTime ?submTime .
?dobj cpmeta:hasStartTime | (cpmeta:wasAcquiredBy / prov:startedAtTime) ?timeStart .
?dobj cpmeta:hasEndTime | (cpmeta:wasAcquiredBy / prov:endedAtTime) ?timeEnd .
    FILTER NOT EXISTS {{[] cpmeta:isNextVersionOf ?dobj}}
FILTER( ?submTime >= '2023-05-31T22:00:00.000Z'^^xsd:dateTime )
}}
order by desc(?submTime)
"""
