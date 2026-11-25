"""Tests for the pure helpers of the netCDF and .txt writer."""
# Related third party imports.
import pytest

# Local application/library specific imports.
from icoscp_obspack.data_writer import without_ncdump_type_suffixes


@pytest.mark.parametrize(
    ('ncdump_value', 'expected'),
    [('-9b', '-9'), ('-9s', '-9'), ('127b', '127'), ('NaNf', 'NaN'), ('1019LL', '1019'),
     ('1.e+34f', '1.e+34'), ('-Infinityf', '-Infinity'), ('200UB', '200'), ('8ULL', '8'),
     ('1, 2, 3s', '1, 2, 3')])
def test_ncdump_type_suffixes_are_removed(ncdump_value, expected):
    assert without_ncdump_type_suffixes(ncdump_value) == expected


@pytest.mark.parametrize('ncdump_value', ['-9', '934.', '-1.e+34', '2015.67129'])
def test_numbers_without_a_suffix_are_left_alone(ncdump_value):
    assert without_ncdump_type_suffixes(ncdump_value) == ncdump_value
