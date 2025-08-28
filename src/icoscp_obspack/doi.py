# Standard library imports.
import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, TypeAlias

# Local application/library specific imports.
from icoscp_obspack.citation import AuthorWithWeight
from icoscp_obspack.config import Config

Uri: TypeAlias = str
NameIdentifierSchemeName: TypeAlias = Literal['ORCID', 'ISNI', 'ROR', 'FLUXNET']
FunderIdentifierType: TypeAlias = Literal['Crossref Funder ID', 'GRID', 'ISNI', 'ROR', 'Other']
NameType: TypeAlias = Literal['Personal', 'Organizational']
ContributorType: TypeAlias = Literal[
    'ContactPerson', 'DataCollector', 'DataCurator', 'DataManager', 'Distributor', 'Editor',
    'HostingInstitution', 'Other', 'Producer', 'ProjectLeader', 'ProjectManager', 'ProjectMember',
    'RegistrationAgency', 'RegistrationAuthority', 'RelatedPerson', 'ResearchGroup',
    'RightsHolder', 'Researcher', 'Sponsor', 'Supervisor', 'WorkPackageLeader']
DateType: TypeAlias = Literal[
    'Accepted', 'Available', 'Copyrighted', 'Collected', 'Created', 'Issued', 'Submitted', 'Updated',
    'Valid', 'Other']
DescriptionType: TypeAlias = Literal[
        'Abstract', 'Methods', 'SeriesInformation', 'TableOfContents', 'TechnicalInfo', 'Other']
DoiPublicationState: TypeAlias = Literal['draft', 'registered', 'findable']
DoiPublicationEvent: TypeAlias = Literal['publish', 'register', 'hide']
TitleType: TypeAlias = Literal['AlternativeTitle', 'Subtitle', 'TranslatedTitle', 'Other']
ResourceTypeGeneral: TypeAlias = Literal[
    'Audiovisual', 'Collection', 'Dataset', 'Event', 'Image', 'InteractiveResource', 'Model',
    'PhysicalObject', 'Service', 'Software', 'Sound', 'Text', 'Workflow', 'Other']

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o: Any):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)

@dataclass(frozen=True)
class GenericName:
    name: str
    nameType: NameType

@dataclass(frozen=True)
class PersonalName:
    givenName: str
    familyName: str
    nameType: NameType

@dataclass(frozen=True)
class NameIdentifierScheme:
    nameIdentifierScheme: NameIdentifierSchemeName
    schemeUri: Uri | None = None
    def __init__(self, name_identifier_scheme: NameIdentifierSchemeName):
        if name_identifier_scheme == 'ORCID':
            scheme_uri = 'http://orcid.org/'
        elif name_identifier_scheme == 'ISNI':
            scheme_uri = 'http://www.isni.org/'
        elif name_identifier_scheme == 'ROR':
            scheme_uri = 'https://ror.org'
        elif name_identifier_scheme == 'FLUXNET':
            scheme_uri = None
        object.__setattr__(self, 'nameIdentifierScheme', name_identifier_scheme)
        object.__setattr__(self, 'schemeUri', scheme_uri)

@dataclass(frozen=True)
class NameIdentifier:
    nameIdentifier: str
    scheme: NameIdentifierScheme

@dataclass(frozen=True)
class FunderIdentifierScheme:
    funderIdentifierType: FunderIdentifierType
    schemeUri: Uri | None = None
    def __init__(self, funder_identifier_type: FunderIdentifierType):
        if funder_identifier_type == 'Crossref Funder ID':
            scheme_uri = 'https://www.crossref.org/services/funder-registry/'
        elif funder_identifier_type == 'GRID':
            scheme_uri = 'https://www.grid.ac/'
        elif funder_identifier_type == 'ISNI':
            scheme_uri = 'http://www.isni.org/'
        elif funder_identifier_type == 'ROR':
            scheme_uri = 'https://ror.org'
        elif funder_identifier_type == 'Other':
            scheme_uri = None
        object.__setattr__(self, 'funderIdentifierType', funder_identifier_type)
        object.__setattr__(self, 'schemeUri', scheme_uri)

#@dataclass(frozen=True)
#class FunderIdentifierValidator:
#    scheme: FunderIdentifierScheme
#    regex: Regex
#    expectedFormat: str

@dataclass(frozen=True)
class FunderIdentifier:
    funderIdentifier: str | None = None
    scheme: FunderIdentifierScheme | None = None

@dataclass(frozen=True)
class Affiliation:
    name: str

@dataclass(frozen=True)
class Creator:
    name: PersonalName | GenericName
    nameIdentifiers: list[NameIdentifier]
    affiliation: list[Affiliation]

@dataclass(frozen=True)
class Award:
    awardNumber: str | None = None
    awardTitle: str | None = None
    awardUri: Uri | None = None

@dataclass(frozen=True)
class FundingReference:
    funderName: str | None = None
    funderIdentifier: FunderIdentifier | None = None
    award: Award | None = None

@dataclass(frozen=True)
class Contributor:
    name: PersonalName | GenericName
    nameIdentifiers: list[NameIdentifier]
    affiliation: list[Affiliation]
    contributorType: ContributorType | None = None

@dataclass(frozen=True)
class Title:
    title: str
    titleType: TitleType | None = None
    lang: str | None = None

@dataclass(frozen=True)
class ResourceType:
    resourceType: str | None = None
    resourceTypeGeneral: ResourceTypeGeneral | None = None

@dataclass(frozen=True)
class Subject:
    subject: str
    lang: str | None = None
    valueUri: Uri | None = None

@dataclass(frozen=True)
class Date:
    date: str
    dateType: DateType | None = None

@dataclass(frozen=True)
class Version:
    major: int
    minor: int

@dataclass(frozen=True)
class Rights:
    rights: str
    rightsUri: Uri | None = None

@dataclass(frozen=True)
class Description:
    description: str
    descriptionType: DescriptionType
    lang: str | None = None

@dataclass(frozen=True)
class GeoLocationPoint:
    pointLongitude: float | None = None
    pointLatitude: float | None = None

@dataclass(frozen=True)
class GeoLocationBox:
    westBoundLongitude: float | None = None
    eastBoundLongitude: float | None = None
    southBoundLatitude: float | None = None
    northBoundLatitude: float | None = None

@dataclass(frozen=True)
class GeoLocation:
    geoLocationPoint: GeoLocationPoint | None = None
    geoLocationBox: GeoLocationBox | None = None
    geoLocationPlace: str | None = None

@dataclass(frozen=True)
class Doi:
    prefix: str
    suffix: str

@dataclass(frozen=True)
class DoiMeta:
    doi: Doi
    state: DoiPublicationState = 'draft'
    event: DoiPublicationEvent | None = None
    creators: list[Creator] = field(default_factory=lambda: [])
    titles: list[Title] | None = None
    publisher: str | None = None
    publicationYear: int | None = None
    types: ResourceType | None = None
    subjects: list[Subject] = field(default_factory=lambda: [])
    contributors: list[Contributor] = field(default_factory=lambda: [])
    dates: list[Date] = field(default_factory=lambda: [])
    formats: list[str] = field(default_factory=lambda: [])
    version: Version | None = None
    rightsList: list[Rights] | None = None
    descriptions: list[Description] = field(default_factory=lambda: [])
    url: str | None = None
    fundingReferences: list[FundingReference] | None = None
    geoLocations: list[GeoLocation] | None = None

def produce_doi_meta(config: Config, authors: list[AuthorWithWeight], geo_locations: list[GeoLocation]) -> None:
    now = datetime.now()
    obspack_name = (
            f'obspack_{config.gas}_466_{config.obspack_product_name}_'
            f'{config.obspack_product_version}_{datetime.now().strftime("%Y%m%d")}')
    doi_meta = DoiMeta(
        doi=Doi(prefix=config.doi.split('/')[0], suffix=config.doi.split('/')[1]),
        state='draft',
        event=None,
        creators=_list_of_creators(authors),
        titles=[Title(title=f'{config.title_for_doi}; {obspack_name}')],
        publisher=config.publisher_for_doi,
        publicationYear=now.year,
        types=ResourceType(resourceType=config.resource_type_for_doi, resourceTypeGeneral='Dataset'),
        subjects=[Subject(subject=subject) for subject in config.subjects_for_doi],
        contributors=_list_of_contributors(authors),
        dates=[Date(date=datetime.strftime(now, '%Y-%m-%d'), dateType='Issued')],
        formats=[config.format_info_for_doi],
        version=Version(major=config.major_version_for_doi, minor=config.minor_version_for_doi),
        rightsList=[Rights(rights=config.rights_for_doi, rightsUri=config.rights_uri_for_doi)],
        descriptions=[Description(
            description=config.description_for_doi,
            descriptionType='Abstract',
            lang='en-uk')],
        url='https://meta.icos-cp.eu/objects/', # To be updated in the DOI app after the data object is uploaded to the Carbon Portal.
        fundingReferences=[],
        geoLocations=geo_locations
    )
    with open(config.doi_json_file, 'w') as doi_json_f:
        json.dump(doi_meta, doi_json_f, cls=EnhancedJSONEncoder)

def _list_of_contributors(authors: list[AuthorWithWeight]) -> list[Contributor]:
    contributors = [_organization_to_doi_contributor('ICOS RI', 'Distributor')]
    contributors.extend([_author_to_doi_contributor(author) for author in authors])
    contributors.append(_organization_to_doi_contributor('ICOS Carbon Portal', 'DataCurator'))
    contributors.append(_organization_to_doi_contributor('ICOS Atmosphere Thematic Centre', 'DataManager'))
    contributors.append(_organization_to_doi_contributor('ICOS Flask And Calibration Laboratory', 'DataCollector'))
    contributors.append(_organization_to_doi_contributor('ICOS Flask And Calibration Laboratory', 'DataCurator'))
    contributors.append(_organization_to_doi_contributor('ICOS Central Radiocarbon Laboratory', 'DataCurator'))
    return contributors

def _list_of_creators(authors: list[AuthorWithWeight]) -> list[Creator]:
    creators = [_organization_to_doi_creator('ICOS RI')]
    creators.extend([_author_to_doi_creator(author) for author in authors])
    creators.append(_organization_to_doi_creator('ICOS Carbon Portal'))
    creators.append(_organization_to_doi_creator('ICOS Atmosphere Thematic Centre'))
    creators.append(_organization_to_doi_creator('ICOS Flask And Calibration Laboratory'))
    creators.append(_organization_to_doi_creator('ICOS Central Radiocarbon Laboratory'))
    return creators

def _organization_to_doi_contributor(organization_name: str, contributor_type: ContributorType) -> Contributor:
    return Contributor(
        name=GenericName(name=organization_name, nameType='Organizational'),
        nameIdentifiers=[],
        affiliation=[],
        contributorType=contributor_type
    )

def _organization_to_doi_creator(organization_name: str) -> Creator:
    return Creator(
        name=GenericName(name=organization_name, nameType='Organizational'),
        nameIdentifiers=[],
        affiliation=[]
    )

def _author_to_doi_contributor(author: AuthorWithWeight) -> Contributor:
    return Contributor(
        name=PersonalName(givenName=author.first_name, familyName=author.last_name, nameType='Personal'),
        nameIdentifiers=_orcid_name_identifiers(author.orcid),
        affiliation=[],
        contributorType='DataCollector'
    )

def _author_to_doi_creator(author: AuthorWithWeight) -> Creator:
    return Creator(
        name=PersonalName(givenName=author.first_name, familyName=author.last_name, nameType='Personal'),
        nameIdentifiers=_orcid_name_identifiers(author.orcid),
        affiliation=[]
    )

def _orcid_name_identifiers(orcid: str | None) -> list[NameIdentifier]:
    return [] if orcid is None else [NameIdentifier(orcid, NameIdentifierScheme('ORCID'))]
