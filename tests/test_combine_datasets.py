"""Tests for the data-level merge logic.

`combine_datasets` does no I/O, so it can be driven with plain stubs exposing only the two
attributes it reads off a data object (`hash` and `specificInfo`). Keeping it that way is what
makes these tests possible — see the "Data-level merge logic" section of CLAUDE.md.
"""
# Standard library imports.
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

# Related third party imports.
import pandas as pd
import pytest

# Local application/library specific imports.
import icoscp_obspack.metadata_and_data_processing as mdp
from icoscp_obspack.metadata_and_data_processing import (
    LoadedDataset,
    combine_datasets,
    data_level_per_data_type,
    load_datasets,
    specs_per_gas,
)

GAS = 'co2'
STATION = 'XXX'
HEIGHT = 50.0


def utc(year: int, month: int = 1, day: int = 1, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


@dataclass(frozen=True)
class StubDobj:
    """The only attributes the code under test reads off a `DataObject`.

    `specificInfo` deliberately exposes the `acquisition.interval` shape rather than a
    `SpatioTemporalMeta`, which is the branch ATC data objects take.
    """
    hash: str
    data_type: str
    interval_start: datetime
    interval_stop: datetime

    @property
    def specification(self):
        return SimpleNamespace(self=SimpleNamespace(uri=specs_per_gas[GAS][self.data_type]))

    @property
    def specificInfo(self):  # noqa: N802 - mirrors the icoscp_core attribute name
        return SimpleNamespace(acquisition=SimpleNamespace(interval=SimpleNamespace(
            start=self.interval_start.isoformat(), stop=self.interval_stop.isoformat())))


def normalised_frame(first: datetime, n_hours: int, data_type: str) -> pd.DataFrame:
    """An hourly frame shaped like `load_datasets` output."""
    stamps = [first + timedelta(hours=i) for i in range(n_hours)]
    return pd.DataFrame({
        'Datetime': stamps,
        'Meas': [400.0 + i * 0.01 for i in range(n_hours)],
        'Level': [data_level_per_data_type[data_type]] * n_hours,
    })


def loaded(
        hash_: str, data_type: str, data_start: datetime, n_hours: int,
        interval_start: datetime | None = None,
        interval_stop: datetime | None = None) -> LoadedDataset:
    """Build a LoadedDataset whose metadata interval can differ from its data range."""
    data = normalised_frame(data_start, n_hours, data_type)
    dobj = StubDobj(
        hash=hash_, data_type=data_type,
        interval_start=data_start if interval_start is None else interval_start,
        interval_stop=data['Datetime'].iloc[-1] if interval_stop is None else interval_stop)
    return LoadedDataset(dobj=dobj, data_type=data_type, data=data)


def levels_in_order(combined: pd.DataFrame) -> list[int]:
    """The distinct ICOS data levels, in the order they appear in the combined frame."""
    return list(combined['Level'].loc[combined['Level'].shift() != combined['Level']])


# --------------------------------------------------------------------------------------------
# combine_datasets
# --------------------------------------------------------------------------------------------

def test_a_single_dataset_passes_through_indexed_by_datetime():
    only = loaded('l2', 'L2', utc(2020), 10)

    combined, used = combine_datasets([only], STATION, HEIGHT, GAS)

    assert combined.index.name == 'Datetime'
    assert len(combined) == 10
    assert [dobj.hash for dobj in used] == ['l2']


def test_no_datasets_of_a_type_leaves_that_type_out():
    combined, used = combine_datasets(
        [loaded('h', 'historic', utc(2015), 5)], STATION, HEIGHT, GAS)

    assert levels_in_order(combined) == [data_level_per_data_type['historic']]
    assert [dobj.hash for dobj in used] == ['h']


def test_historic_is_trimmed_at_the_l2_interval_from_metadata():
    """The cut uses the L2 metadata start, not the first L2 data row."""
    historic = loaded('h', 'historic', utc(2020, 1, 1), 24 * 10)          # Jan 1 -> Jan 10
    l2 = loaded(
        'l2', 'L2', utc(2020, 1, 6), 24 * 5,                              # data starts Jan 6
        interval_start=utc(2020, 1, 5))                                   # metadata says Jan 5

    combined, _ = combine_datasets([historic, l2], STATION, HEIGHT, GAS)

    kept_historic = combined[combined['Level'] == data_level_per_data_type['historic']]
    assert kept_historic.index.max() < utc(2020, 1, 5)
    # Jan 5 -> Jan 6 is covered by neither, because the metadata interval governs the cut.
    assert combined.index.min() == utc(2020, 1, 1)


def test_l2_takes_priority_over_fasttrack_where_they_overlap():
    l2 = loaded('l2', 'L2', utc(2021, 1, 1), 24 * 10, interval_stop=utc(2021, 1, 8))
    fasttrack = loaded('ft', 'fasttrack', utc(2021, 1, 5), 24 * 10)       # overlaps Jan 5-10

    combined, used = combine_datasets([l2, fasttrack], STATION, HEIGHT, GAS)

    kept_ft = combined[combined['Level'] == data_level_per_data_type['fasttrack']]
    assert kept_ft.index.min() > utc(2021, 1, 8)
    assert [dobj.hash for dobj in used] == ['l2', 'ft']


def test_nrt_is_trimmed_at_the_fasttrack_interval_stop():
    fasttrack = loaded('ft', 'fasttrack', utc(2022, 1, 1), 24 * 5, interval_stop=utc(2022, 1, 4))
    nrt = loaded('nrt', 'nrt', utc(2022, 1, 3), 24 * 5)                   # overlaps Jan 3-4

    combined, _ = combine_datasets([fasttrack, nrt], STATION, HEIGHT, GAS)

    kept_nrt = combined[combined['Level'] == data_level_per_data_type['nrt']]
    assert kept_nrt.index.min() > utc(2022, 1, 4)


def test_nrt_is_kept_whole_when_there_is_no_fasttrack():
    l2 = loaded('l2', 'L2', utc(2022, 1, 1), 24)
    nrt = loaded('nrt', 'nrt', utc(2022, 1, 2), 24)

    combined, _ = combine_datasets([l2, nrt], STATION, HEIGHT, GAS)

    kept_nrt = combined[combined['Level'] == data_level_per_data_type['nrt']]
    assert len(kept_nrt) == 24


def test_all_four_types_are_concatenated_in_priority_order():
    datasets = [
        loaded('h', 'historic', utc(2014), 24, interval_stop=utc(2015)),
        loaded('l2', 'L2', utc(2016), 24, interval_start=utc(2016), interval_stop=utc(2017)),
        loaded('ft', 'fasttrack', utc(2018), 24, interval_stop=utc(2019)),
        loaded('nrt', 'nrt', utc(2020), 24),
    ]

    combined, used = combine_datasets(datasets, STATION, HEIGHT, GAS)

    assert levels_in_order(combined) == [
        data_level_per_data_type['historic'], data_level_per_data_type['L2'],
        data_level_per_data_type['fasttrack'], data_level_per_data_type['nrt']]
    assert [dobj.hash for dobj in used] == ['h', 'l2', 'ft', 'nrt']


def test_input_order_does_not_change_the_output_order():
    """Priority comes from the data type, not from the order objects arrive in."""
    datasets = [
        loaded('nrt', 'nrt', utc(2020), 24),
        loaded('h', 'historic', utc(2014), 24, interval_stop=utc(2015)),
        loaded('ft', 'fasttrack', utc(2018), 24, interval_stop=utc(2019)),
        loaded('l2', 'L2', utc(2016), 24, interval_start=utc(2016), interval_stop=utc(2017)),
    ]

    combined, _ = combine_datasets(datasets, STATION, HEIGHT, GAS)

    assert levels_in_order(combined) == [
        data_level_per_data_type['historic'], data_level_per_data_type['L2'],
        data_level_per_data_type['fasttrack'], data_level_per_data_type['nrt']]


def test_a_deprecated_duplicate_is_concatenated_rather_than_discarded(monkeypatch):
    """Objects listed in `deprecated_dobjs_to_use` extend the type instead of replacing it."""
    extra_hash = 'a' * 24
    monkeypatch.setitem(
        mdp.deprecated_dobjs_to_use[GAS], STATION,
        {HEIGHT: [f'https://meta.icos-cp.eu/objects/{extra_hash}']})

    current = loaded('l2', 'L2', utc(2021), 24)
    earlier = loaded(extra_hash, 'L2', utc(2019), 24)     # ends before `current` begins

    combined, used = combine_datasets([current, earlier], STATION, HEIGHT, GAS)

    assert len(combined) == 48
    assert combined.index.min() == utc(2019)
    assert sorted(dobj.hash for dobj in used) == sorted(['l2', extra_hash])


def test_the_most_recent_dataset_wins_when_a_type_is_duplicated():
    """An unexpected duplicate of a data type resolves to the most recent data.

    Both the rows and the reported data object must come from the same dataset; they used to
    disagree, the newer object being reported while the older object's rows were returned.
    """
    older = loaded('older', 'L2', utc(2020), 5)
    newer = loaded('newer', 'L2', utc(2021), 9)

    combined, used = combine_datasets([older, newer], STATION, HEIGHT, GAS)

    assert [dobj.hash for dobj in used] == ['newer']
    assert len(combined) == 9
    assert combined.index.min() == utc(2021)


def test_an_older_duplicate_does_not_displace_the_dataset_in_place():
    """The mirror case: a duplicate ending earlier leaves both rows and hash untouched."""
    newer = loaded('newer', 'L2', utc(2021), 9)
    older = loaded('older', 'L2', utc(2020), 5)

    combined, used = combine_datasets([newer, older], STATION, HEIGHT, GAS)

    assert [dobj.hash for dobj in used] == ['newer']
    assert len(combined) == 9
    assert combined.index.min() == utc(2021)


# --------------------------------------------------------------------------------------------
# load_datasets
# --------------------------------------------------------------------------------------------

def raw_frame(first: datetime, n_hours: int, flags: str) -> pd.DataFrame:
    """A data file as `get_dataset` returns it, before normalisation."""
    stamps = [first + timedelta(hours=i) for i in range(n_hours)]
    return pd.DataFrame({
        'Year': [t.year for t in stamps], 'Month': [t.month for t in stamps],
        'Day': [t.day for t in stamps], 'Hour': [t.hour for t in stamps],
        'Minute': [0] * n_hours,
        'DecimalDate': [t.year + i / 8760 for i, t in enumerate(stamps)],
        GAS: [400.0 + i for i in range(n_hours)],
        'Flag': [flags[i % len(flags)] for i in range(n_hours)],
    })


@pytest.fixture
def stub_get_dataset(monkeypatch):
    """Replace the single I/O call in load_datasets with a lookup by data object hash."""
    frames: dict[str, pd.DataFrame] = {}
    monkeypatch.setattr(
        mdp, 'get_dataset', lambda dobj, zip_dir, cached: frames[dobj.hash].copy())
    return frames


def test_load_datasets_normalises_columns(stub_get_dataset):
    stub_get_dataset['l2'] = raw_frame(utc(2020), 3, 'O')
    dobj = StubDobj('l2', 'L2', utc(2020), utc(2021))

    result = load_datasets([dobj], GAS, False, 'unused', True)

    assert len(result) == 1
    data = result[0].data
    assert result[0].data_type == 'L2'
    assert {'JulDate', 'Meas', 'Datetime', 'Level'} <= set(data.columns)
    assert GAS not in data.columns                      # renamed to 'Meas'
    assert data['Level'].unique().tolist() == [data_level_per_data_type['L2']]
    assert data['Datetime'].iloc[0] == utc(2020)


@pytest.mark.parametrize(
    ('data_type', 'expected_kept'),
    [('nrt', ['U']), ('L2', ['O', 'U']), ('historic', ['O', 'U']), ('fasttrack', ['O', 'U'])])
def test_load_datasets_keeps_only_the_good_flags_of_each_type(
        stub_get_dataset, data_type, expected_kept):
    stub_get_dataset['d'] = raw_frame(utc(2020), 30, 'OUN')
    dobj = StubDobj('d', data_type, utc(2020), utc(2021))

    result = load_datasets([dobj], GAS, True, 'unused', True)

    assert sorted(result[0].data['Flag'].unique()) == expected_kept


def test_load_datasets_keeps_every_row_when_flags_are_disabled(stub_get_dataset):
    stub_get_dataset['d'] = raw_frame(utc(2020), 30, 'OUN')
    dobj = StubDobj('d', 'nrt', utc(2020), utc(2021))

    result = load_datasets([dobj], GAS, False, 'unused', True)

    assert len(result[0].data) == 30


def test_load_datasets_ignores_objects_of_another_specification(stub_get_dataset):
    other = SimpleNamespace(
        hash='other',
        specification=SimpleNamespace(self=SimpleNamespace(uri='http://example.org/not-a-gas-spec')))

    assert load_datasets([other], GAS, True, 'unused', True) == []
