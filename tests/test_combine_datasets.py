"""Tests for the data-level merge logic.

`combine_datasets` does no I/O, so it can be driven with plain stubs exposing only the two
attributes it reads off a data object (`hash` and `specification`). Keeping it that way is what
makes these tests possible — see the "Data-level merge logic" section of CLAUDE.md.
"""
# Standard library imports.
from dataclasses import dataclass, replace
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
    load_datasets,
    looks_like_a_sentinel,
    mask_sentinels,
)
from icoscp_obspack.tracers import (
    DATA_LEVEL_PER_TYPE,
    SENTINEL_VALUE_FLAG,
    TRACERS,
    Sentinel,
    Tracer,
)

TRACER = TRACERS['co2']
GAS = TRACER.key
STATION = 'XXX'
HEIGHT = 50.0


def utc(year: int, month: int = 1, day: int = 1, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


@dataclass(frozen=True)
class StubDobj:
    """The only attributes the code under test reads off a `DataObject`."""
    hash: str
    data_type: str
    tracer: Tracer = TRACER

    @property
    def fileName(self) -> str:  # noqa: N802 - mirrors `DataObject`
        return f'{self.hash}.zip'

    @property
    def specification(self):
        return SimpleNamespace(self=SimpleNamespace(uri=self.tracer.specs[self.data_type]))


def normalised_frame(first: datetime, n_hours: int, data_type: str) -> pd.DataFrame:
    """An hourly frame shaped like `load_datasets` output."""
    stamps = [first + timedelta(hours=i) for i in range(n_hours)]
    return pd.DataFrame({
        'Datetime': stamps,
        'Meas': [400.0 + i * 0.01 for i in range(n_hours)],
        'Level': [DATA_LEVEL_PER_TYPE[data_type]] * n_hours,
    })


def loaded(hash_: str, data_type: str, data_start: datetime, n_hours: int) -> LoadedDataset:
    return LoadedDataset(
        dobj=StubDobj(hash=hash_, data_type=data_type), data_type=data_type,
        data=normalised_frame(data_start, n_hours, data_type))


def levels_in_order(combined: pd.DataFrame) -> list[int]:
    """The distinct ICOS data levels, in the order they appear in the combined frame."""
    return list(combined['Level'].loc[combined['Level'].shift() != combined['Level']])


# --------------------------------------------------------------------------------------------
# combine_datasets
# --------------------------------------------------------------------------------------------

def test_a_single_dataset_passes_through_indexed_by_datetime():
    only = loaded('l2', 'L2', utc(2020), 10)

    combined, used = combine_datasets([only], STATION, HEIGHT, TRACER)

    assert combined.index.name == 'Datetime'
    assert len(combined) == 10
    assert [dobj.hash for dobj in used] == ['l2']


def test_no_datasets_of_a_type_leaves_that_type_out():
    combined, used = combine_datasets(
        [loaded('h', 'historic', utc(2015), 5)], STATION, HEIGHT, TRACER)

    assert levels_in_order(combined) == [DATA_LEVEL_PER_TYPE['historic']]
    assert [dobj.hash for dobj in used] == ['h']


def test_historic_is_trimmed_at_the_first_l2_row_leaving_no_gap():
    """The cut uses the first L2 data row, so historic covers everything before it.

    The temporal interval reported in the metadata is not consulted: were it used, historic
    would be cut at the interval start and the stretch between that and the first L2 row would
    be covered by neither data type.
    """
    historic = loaded('h', 'historic', utc(2020, 1, 1), 24 * 10)          # Jan 1 -> Jan 10
    l2 = loaded('l2', 'L2', utc(2020, 1, 6), 24 * 5)                      # Jan 6 -> Jan 10

    combined, _ = combine_datasets([historic, l2], STATION, HEIGHT, TRACER)

    kept_historic = combined[combined['Level'] == DATA_LEVEL_PER_TYPE['historic']]
    assert kept_historic.index.max() == utc(2020, 1, 5, 23)
    # Every hour from the start of historic to the end of L2 is covered exactly once.
    assert combined.index.min() == utc(2020, 1, 1)
    assert not combined.index.duplicated().any()
    assert len(combined) == 24 * 10


def test_l2_takes_priority_over_fasttrack_where_they_overlap():
    l2 = loaded('l2', 'L2', utc(2021, 1, 1), 24 * 10)                     # Jan 1 -> Jan 10
    fasttrack = loaded('ft', 'fasttrack', utc(2021, 1, 5), 24 * 10)       # overlaps Jan 5-10

    combined, used = combine_datasets([l2, fasttrack], STATION, HEIGHT, TRACER)

    kept_ft = combined[combined['Level'] == DATA_LEVEL_PER_TYPE['fasttrack']]
    # L2 runs to Jan 10 23:00; FastTrack resumes on the next hour rather than replacing any of it.
    assert kept_ft.index.min() == utc(2021, 1, 11)
    assert [dobj.hash for dobj in used] == ['l2', 'ft']


def test_nrt_is_trimmed_at_the_last_fasttrack_row():
    fasttrack = loaded('ft', 'fasttrack', utc(2022, 1, 1), 24 * 5)        # Jan 1 -> Jan 5
    nrt = loaded('nrt', 'nrt', utc(2022, 1, 3), 24 * 5)                   # overlaps Jan 3-5

    combined, _ = combine_datasets([fasttrack, nrt], STATION, HEIGHT, TRACER)

    kept_nrt = combined[combined['Level'] == DATA_LEVEL_PER_TYPE['nrt']]
    assert kept_nrt.index.min() == utc(2022, 1, 6)


def test_nrt_is_trimmed_against_l2_when_there_is_no_fasttrack():
    """Radon's shape: level-2 and near-real-time data only, overlapping in time."""
    l2 = loaded('l2', 'L2', utc(2022, 1, 1), 24 * 3)                      # Jan 1 -> Jan 3
    nrt = loaded('nrt', 'nrt', utc(2022, 1, 2), 24 * 3)                   # overlaps Jan 2-3

    combined, _ = combine_datasets([l2, nrt], STATION, HEIGHT, TRACER)

    kept_nrt = combined[combined['Level'] == DATA_LEVEL_PER_TYPE['nrt']]
    assert kept_nrt.index.min() == utc(2022, 1, 4)
    assert not combined.index.duplicated().any()


def test_nrt_is_kept_whole_when_it_does_not_overlap():
    l2 = loaded('l2', 'L2', utc(2022, 1, 1), 24)
    nrt = loaded('nrt', 'nrt', utc(2022, 1, 2), 24)

    combined, _ = combine_datasets([l2, nrt], STATION, HEIGHT, TRACER)

    kept_nrt = combined[combined['Level'] == DATA_LEVEL_PER_TYPE['nrt']]
    assert len(kept_nrt) == 24


def test_all_four_types_are_concatenated_in_priority_order():
    datasets = [
        loaded('h', 'historic', utc(2014), 24),
        loaded('l2', 'L2', utc(2016), 24),
        loaded('ft', 'fasttrack', utc(2018), 24),
        loaded('nrt', 'nrt', utc(2020), 24),
    ]

    combined, used = combine_datasets(datasets, STATION, HEIGHT, TRACER)

    assert levels_in_order(combined) == [
        DATA_LEVEL_PER_TYPE['historic'], DATA_LEVEL_PER_TYPE['L2'],
        DATA_LEVEL_PER_TYPE['fasttrack'], DATA_LEVEL_PER_TYPE['nrt']]
    assert [dobj.hash for dobj in used] == ['h', 'l2', 'ft', 'nrt']


def test_input_order_does_not_change_the_output_order():
    """Priority comes from the data type, not from the order objects arrive in."""
    datasets = [
        loaded('nrt', 'nrt', utc(2020), 24),
        loaded('h', 'historic', utc(2014), 24),
        loaded('ft', 'fasttrack', utc(2018), 24),
        loaded('l2', 'L2', utc(2016), 24),
    ]

    combined, _ = combine_datasets(datasets, STATION, HEIGHT, TRACER)

    assert levels_in_order(combined) == [
        DATA_LEVEL_PER_TYPE['historic'], DATA_LEVEL_PER_TYPE['L2'],
        DATA_LEVEL_PER_TYPE['fasttrack'], DATA_LEVEL_PER_TYPE['nrt']]


def test_a_deprecated_duplicate_is_concatenated_rather_than_discarded(monkeypatch):
    """Objects listed in `deprecated_dobjs_to_use` extend the type instead of replacing it."""
    extra_hash = 'a' * 24
    monkeypatch.setitem(
        mdp.deprecated_dobjs_to_use[GAS], STATION,
        {HEIGHT: [f'https://meta.icos-cp.eu/objects/{extra_hash}']})

    current = loaded('l2', 'L2', utc(2021), 24)
    earlier = loaded(extra_hash, 'L2', utc(2019), 24)     # ends before `current` begins

    combined, used = combine_datasets([current, earlier], STATION, HEIGHT, TRACER)

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

    combined, used = combine_datasets([older, newer], STATION, HEIGHT, TRACER)

    assert [dobj.hash for dobj in used] == ['newer']
    assert len(combined) == 9
    assert combined.index.min() == utc(2021)


def test_an_older_duplicate_does_not_displace_the_dataset_in_place():
    """The mirror case: a duplicate ending earlier leaves both rows and hash untouched."""
    newer = loaded('newer', 'L2', utc(2021), 9)
    older = loaded('older', 'L2', utc(2020), 5)

    combined, used = combine_datasets([newer, older], STATION, HEIGHT, TRACER)

    assert [dobj.hash for dobj in used] == ['newer']
    assert len(combined) == 9
    assert combined.index.min() == utc(2021)


# --------------------------------------------------------------------------------------------
# load_datasets
# --------------------------------------------------------------------------------------------

def raw_frame(
        first: datetime, n_hours: int, flags: str, value_column: str = GAS,
        std_column: str = 'Stdev') -> pd.DataFrame:
    """A data file as `get_dataset` returns it, before normalisation."""
    stamps = [first + timedelta(hours=i) for i in range(n_hours)]
    return pd.DataFrame({
        'Year': [t.year for t in stamps], 'Month': [t.month for t in stamps],
        'Day': [t.day for t in stamps], 'Hour': [t.hour for t in stamps],
        'Minute': [0] * n_hours,
        'DecimalDate': [t.year + i / 8760 for i, t in enumerate(stamps)],
        value_column: [400.0 + i for i in range(n_hours)],
        std_column: [0.1] * n_hours,
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
    dobj = StubDobj('l2', 'L2')

    result = load_datasets([dobj], TRACER, False, 'unused', True)

    assert len(result) == 1
    data = result[0].data
    assert result[0].data_type == 'L2'
    assert {'JulDate', 'Meas', 'Datetime', 'Level'} <= set(data.columns)
    assert GAS not in data.columns                      # renamed to 'Meas'
    assert data['Level'].unique().tolist() == [DATA_LEVEL_PER_TYPE['L2']]
    assert data['Datetime'].iloc[0] == utc(2020)


@pytest.mark.parametrize(
    ('data_type', 'expected_kept'),
    [('nrt', ['U']), ('L2', ['O', 'U']), ('historic', ['O', 'U']), ('fasttrack', ['O', 'U'])])
def test_load_datasets_keeps_only_the_good_flags_of_each_type(
        stub_get_dataset, data_type, expected_kept):
    stub_get_dataset['d'] = raw_frame(utc(2020), 30, 'OUN')
    dobj = StubDobj('d', data_type)

    result = load_datasets([dobj], TRACER, True, 'unused', True)

    assert sorted(result[0].data['Flag'].unique()) == expected_kept


def test_load_datasets_keeps_every_row_when_flags_are_disabled(stub_get_dataset):
    stub_get_dataset['d'] = raw_frame(utc(2020), 30, 'OUN')
    dobj = StubDobj('d', 'nrt')

    result = load_datasets([dobj], TRACER, False, 'unused', True)

    assert len(result[0].data) == 30


def test_load_datasets_ignores_objects_of_another_specification(stub_get_dataset):
    other = SimpleNamespace(
        hash='other',
        specification=SimpleNamespace(self=SimpleNamespace(uri='http://example.org/not-a-gas-spec')))

    assert load_datasets([other], TRACER, True, 'unused', True) == []


def test_load_datasets_renames_the_standard_deviation_column(stub_get_dataset):
    stub_get_dataset['l2'] = raw_frame(utc(2020), 3, 'O')
    dobj = StubDobj('l2', 'L2')

    result = load_datasets([dobj], TRACER, False, 'unused', True)

    assert 'Stdev' in result[0].data.columns


def test_load_datasets_uses_the_alternate_columns_of_a_tracer(stub_get_dataset):
    """A tracer may name its value and standard deviation columns differently."""
    tracer = replace(TRACER, value_column='14C', std_column='WeightedStdErr')
    stub_get_dataset['l2'] = raw_frame(
        utc(2020), 3, 'O', value_column=tracer.value_column, std_column=tracer.std_column)
    dobj = StubDobj('l2', 'L2', tracer=tracer)

    result = load_datasets([dobj], tracer, False, 'unused', True)

    data = result[0].data
    assert {'Meas', 'Stdev'} <= set(data.columns)
    assert tracer.value_column not in data.columns
    assert tracer.std_column not in data.columns


def test_load_datasets_ignores_data_types_a_tracer_does_not_provide(stub_get_dataset):
    """Radon has no historic data, so that specification never matches one of its objects."""
    tracer = TRACERS['rn']
    assert 'historic' not in tracer.specs

    historic_only = SimpleNamespace(
        hash='hist',
        specification=SimpleNamespace(
            self=SimpleNamespace(uri=TRACERS['co2'].specs['historic'])))

    assert load_datasets([historic_only], tracer, True, 'unused', True) == []


def test_load_datasets_accepts_the_fasttrack_specification_radon_shares_with_the_gases(
        stub_get_dataset):
    """
    Radon's FastTrack objects carry the specification shared with the greenhouse gases, so at
    this point they are indistinguishable from a CO2 FastTrack object. The separation happens
    earlier, in `dobjs_from_station_by_sampling_height`, which reads the tracer from the file
    name; `load_datasets` only ever matches on the specification URI.
    """
    tracer = TRACERS['rn']
    assert tracer.specs['fasttrack'] == TRACERS['co2'].specs['fasttrack']
    stub_get_dataset['ft'] = raw_frame(
        utc(2026, 4), 3, 'O', value_column=tracer.value_column, std_column=tracer.std_column)

    result = load_datasets(
        [StubDobj('ft', 'fasttrack', tracer=tracer)], tracer, False, 'unused', True)

    assert [loaded_dataset.data_type for loaded_dataset in result] == ['fasttrack']


# --------------------------------------------------------------------------------------------
# mask_sentinels
# --------------------------------------------------------------------------------------------

def source_rows(**columns: list) -> pd.DataFrame:
    """A few source rows of CO2, good unless a 'Flag' column says otherwise."""
    n = len(next(iter(columns.values())))
    defaults = {GAS: [400.0] * n, 'Stdev': [0.1] * n, 'NbPoints': [10] * n, 'Flag': ['O'] * n}
    return pd.DataFrame({**defaults, **columns})


def mask(dataset: pd.DataFrame, tracer=TRACER, good_flags=('O', 'U')) -> pd.DataFrame:
    return mask_sentinels(dataset, tracer, list(good_flags), 'source.zip')


@pytest.mark.parametrize(
    'value', [-9.0, -9.99, -9.9, -99.99, -999.9, -999.99, -9999.0, -999990.0])
def test_sentinel_shapes_are_recognised(value):
    assert looks_like_a_sentinel(pd.Series([value])).iloc[0]


@pytest.mark.parametrize('value', [9.99, 999.99, -9.98, -1.5, -90.0, -0.99, 0.0])
def test_other_values_do_not_look_like_a_sentinel(value):
    assert not looks_like_a_sentinel(pd.Series([value])).iloc[0]


def test_the_expected_sentinel_becomes_missing_and_its_good_flag_bad(capsys):
    result = mask(source_rows(**{GAS: [400.0, -999.99, -999.99], 'Flag': ['O', 'O', 'N']}))

    assert result[GAS].iloc[0] == 400.0
    assert result[GAS].iloc[1:].isna().all()
    assert result['Flag'].tolist() == ['O', SENTINEL_VALUE_FLAG, 'N']
    assert '1 row(s) hold a sentinel value under a good flag' in capsys.readouterr().out


def test_rows_are_kept():
    dataset = source_rows(**{GAS: [-999.99, -999.99]})

    assert len(mask(dataset)) == 2


def test_a_sentinel_only_masks_its_own_column():
    """A missing standard deviation does not make the measurement missing, nor bad."""
    result = mask(source_rows(Stdev=[-9.99, 0.1]))

    assert result['Stdev'].isna().tolist() == [True, False]
    assert result[GAS].tolist() == [400.0, 400.0]
    assert result['Flag'].tolist() == ['O', 'O']


def test_the_flag_is_only_corrected_for_the_measured_value():
    result = mask(source_rows(LTR=[-999.99], CMR=[-999.99], STTB=[-999.99]))

    assert result[['LTR', 'CMR', 'STTB']].isna().all(axis=None)
    assert result['Flag'].tolist() == ['O']


def test_an_unexpected_sentinel_is_reported_and_masked(capsys):
    result = mask(source_rows(Stdev=[-999.9, -999.9, 0.1], **{GAS: [-999990.0, 400.0, 400.0]}))

    assert result['Stdev'].isna().tolist() == [True, True, False]
    assert result[GAS].isna().tolist() == [True, False, False]
    assert result['Flag'].iloc[0] == SENTINEL_VALUE_FLAG
    out = capsys.readouterr().out
    assert 'column Stdev holds -999.9 on 2 row(s)' in out
    assert 'expected -9.99; masked' in out
    assert f'column {GAS} holds -999990 on 1 row(s)' in out


def test_an_unexpected_sentinel_is_only_reported_where_negatives_are_valid(capsys):
    """A Delta-14C of -9.9 per mil is plausible, so it is kept, but still reported."""
    tracer = replace(
        TRACER, value_column='14C', clip_negatives=False,
        sentinels={'14C': Sentinel(-999.99, negatives_are_valid=True)})
    dataset = pd.DataFrame({'14C': [-9.9, -999.99, -25.3], 'Flag': ['O', 'O', 'O']})

    result = mask(dataset, tracer)

    assert result['14C'].iloc[0] == -9.9
    assert pd.isna(result['14C'].iloc[1])
    assert result['14C'].iloc[2] == -25.3
    assert result['Flag'].tolist() == ['O', SENTINEL_VALUE_FLAG, 'O']
    out = capsys.readouterr().out
    assert 'column 14C holds -9.9 on 1 row(s)' in out
    assert 'left as is' in out
    assert '-25.3' not in out


def test_sttb_keeps_its_negative_values():
    result = mask(source_rows(STTB=[-9.99, -0.2, -999.99]))

    assert result['STTB'].iloc[:2].tolist() == [-9.99, -0.2]
    assert pd.isna(result['STTB'].iloc[2])


def test_an_integer_sentinel_becomes_the_integer_fill_value():
    result = mask(source_rows(NbPoints=[-9, 10]))

    assert pd.api.types.is_integer_dtype(result['NbPoints'])
    assert result['NbPoints'].tolist() == [mdp.INT_FILL_VALUE, 10]


def test_columns_a_dataset_lacks_are_skipped():
    """Some historic files have no LTR, CMR or STTB."""
    result = mask(source_rows(**{GAS: [-999.99]}))

    assert 'LTR' not in result.columns


def test_the_source_dataset_is_left_untouched():
    dataset = source_rows(**{GAS: [-999.99]})

    mask(dataset)

    assert dataset[GAS].iloc[0] == -999.99
    assert dataset['Flag'].iloc[0] == 'O'


def test_every_tracer_declares_the_sentinels_of_its_value_and_standard_deviation():
    for tracer in TRACERS.values():
        assert {tracer.value_column, tracer.std_column} <= set(tracer.sentinels), tracer.key
        # A value column holding genuine negatives must not lose them to the sentinel shape.
        assert tracer.sentinels[tracer.value_column].negatives_are_valid == (
            not tracer.clip_negatives), tracer.key


def test_load_datasets_masks_sentinels_before_filtering_flags(stub_get_dataset):
    """The corrected flag is what lets `use_flags` drop the row."""
    frame = raw_frame(utc(2020), 3, 'O')
    frame.loc[1, GAS] = -999.99
    stub_get_dataset['l2'] = frame

    filtered = load_datasets([StubDobj('l2', 'L2')], TRACER, True, 'unused', True)
    kept = load_datasets([StubDobj('l2', 'L2')], TRACER, False, 'unused', True)

    assert len(filtered[0].data) == 2
    assert not filtered[0].data['Meas'].isna().any()
    assert len(kept[0].data) == 3
    assert kept[0].data['Flag'].tolist() == ['O', SENTINEL_VALUE_FLAG, 'O']
    assert pd.isna(kept[0].data['Meas'].iloc[1])
