# Standard library imports.
from pathlib import Path

# Related third party imports.
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from datetime import datetime, timedelta
from matplotlib.lines import Line2D
from numpy.typing import ArrayLike
from urllib.error import HTTPError, URLError

# Local application/library specific imports.
from icoscp_obspack.config import Config
from icoscp_obspack.utils import ccgfilt
from icoscp_obspack.utils.utils import timeit


def plot_timeseries_station(
        config: Config,
        dataset: pd.DataFrame,
        global_avg: pd.DataFrame,
        global_avg_filtered: pd.DataFrame,
        station_id: str,
        sampling_height: float,
        filename: str
) -> None:
    """Plot measurements, trend, smoothed curve."""
    path_to_png = Path(config.png, filename)
    # Make a copy of the dataset without timezone information in the index.
    # This is necessary for the ghg_filter_ts function to work correctly.
    dataset_wo_tz = dataset.copy()
    dataset_wo_tz.index = dataset_wo_tz.index.tz_localize(None)
    time0 = datetime.now()
    dataset_filtered = ghg_filter_ts(dataset_wo_tz['JulDate'], dataset_wo_tz['Meas'])
    _ = timeit(time0, f'    Filter timeseries for station {station_id} at sampling height {sampling_height}', config.print_timing_messages)
    station_and_height = f'{station_id} {str(int(sampling_height))}'
    last_time = dataset['JulDate'].to_numpy()[-1]
    fig = plt.figure(figsize=(15, 8))
    ax = fig.add_axes(rect=[0.125, 0.115, 0.775, 0.775])
    ax.set_title(
        f'{config.plot_gas_label} at {station_and_height}; measurements, trend and seasonal signal',
        fontsize=18)
    ax.set_xlabel('Year', fontsize=14)
    ax.set_ylabel(f'{config.plot_gas_label} {config.plot_unit_label}', fontsize=14)
    ax.set_xlim(2010, last_time)
    ax.set_ylim(*config.plot_limy)
    ax.set_xticks(range(2010, int(last_time) + 1))
    ax.grid(zorder=0, linestyle='-.', color='grey')
    ax.set_facecolor('whitesmoke')
    sns.set_style("white")
    graph_info: dict[int, tuple[str, str]] = {
        0: ('Hist.', 'lightgreen'), 1: ('NRT', 'red'), 2: ('L2', 'green'), 15: ('L1.5', 'olive')
    }
    lines: dict[str, Line2D] = {}
    for data_level, (data_type_label, color) in graph_info.items():
        lines[data_type_label], = ax.plot(
            dataset.loc[dataset['Level'] == data_level, 'JulDate'],
            dataset.loc[dataset['Level'] == data_level, 'Meas'],
            label=f'{station_and_height} {data_type_label}',
            color=color, marker='+', markersize=4, linewidth=0)
    lines['Station trend'], = ax.plot(
        dataset_filtered.index,
        dataset_filtered['Trend'],
        label=f'Trend from {station_and_height}',
        color='black')
    lines['Station smoothed curve'], = ax.plot(
        dataset_filtered.index,
        dataset_filtered['SmoothCurve'],
        label=f'Smoothed curve {station_and_height}',
        color='blue')
    lines['Global average'], = ax.plot(
        global_avg['JulDate'],
        global_avg['Meas'],
        label='Global average',
        color='red', marker='+', markersize=3, linewidth=0)
    lines['Global trend'], = ax.plot(
        global_avg_filtered.index,
        global_avg_filtered['Trend'],
        label='Global trend',
        color='yellow', linestyle="--")
    ax.legend(
        handles=[
            lines['Hist.'], lines['L2'], lines['L1.5'], lines['NRT'], lines['Station smoothed curve'],
            lines['Station trend'], lines['Global average'], lines['Global trend']],
        loc=2)
    fig.savefig(path_to_png, dpi=150)
    if config.display_plots:
        plt.show()
    plt.close()


def get_global_average(c: Config) -> pd.DataFrame:
    if c.gas == 'co2' and c.use_mauna_loa_for_global_co2:
        # Get the most recent Mauna Loa CO2 data.
        url = 'https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_weekly_mlo.txt'
        skip_rows = 37
        names = ['JulDate', 'Meas']
        cols = [3, 4]
        global_avg_path = Path(c.output, 'co2_weekly_mlo.txt')
    elif c.gas in ['co2', 'ch4', 'n2o']:
        # Get the most recent monthly marine BL global averages.
        url = f'https://gml.noaa.gov/webdata/ccgg/trends/{c.gas}/{c.gas}_mm_gl.txt'
        skip_rows = 58 if c.gas == 'co2' else 65
        names = ['JulDate', 'Meas', 'Trend']
        cols = [2, 3, 5]
        global_avg_path = Path(c.output, f'{c.gas}_mm_gl.txt')
    else:
        print(f'No global average data is available for gas {c.gas}.')
        return pd.DataFrame(columns=['JulDate', 'Meas', 'Trend'])
    try:
        global_avg = pd.read_csv(
            url, skiprows=skip_rows, header=None,
            names=names, delimiter=r'\s+', usecols=cols)
    except (HTTPError, URLError) as e:
        print(f'HTTP or URL error occurred: {e}')
        print(f'Trying cache in "{global_avg_path}"')
        global_avg = pd.read_csv(global_avg_path)
    except Exception as e:
        print(f'Unexpected error: {e}')
        raise e
    else:
        global_avg = global_avg.query('Meas>20')
        global_avg['DateTime'] = global_avg['JulDate'].apply(t2dt)
        global_avg.set_index('DateTime', inplace=True)
        global_avg.to_csv(global_avg_path)
    return global_avg


def t2dt(timepoint: float) -> datetime:
    """Convert a fractional year timestamp to a datetime object."""
    year = int(timepoint)
    remainder = timepoint - year
    boy = datetime(year, 1, 1)
    eoy = datetime(year + 1, 1, 1)
    seconds = remainder * (eoy - boy).total_seconds()
    return boy + timedelta(seconds=seconds)


def ghg_filter_ts(
        time: ArrayLike, meas: ArrayLike, shortTerm: int = 80, longTerm: int = 667, numPolyterms: int = 3,
        numHarmonics: int = 4, timeZero: int = 2010, sampleInterval: float = 1/24) -> pd.DataFrame:
    """Function wrapper to the CCGCRV routine from Thonen et al. (1996)

    Filters a timeseries by smoothing and removing higher frequency
    information and fitting a trend and harmonic oscillation.
    Specifically, designed for greenhouse gas observations.
    The input parameters are further described in ccgfilt.py, under the
    ccgFilter class.

    Input
    Observational data provided in Pandas dataframe with index datetime
    as YYYY.fraction and the observation series in the first column.

    Result
    A dataframe with index datetime containing in the columns the
    GrowthRate, Function, Poly, SmoothCurve, Trend, Cycle, Residual,
    Detrended the interpolated sampleInterval
    """

    gap = 0
    debug = True
    filt = ccgfilt.ccgFilter(time, meas, shortTerm, longTerm, sampleInterval,
                             numPolyterms, numHarmonics, timeZero, gap, debug)

    # Get x,y data for plotting
    x0 = filt.xinterp
    y1 = filt.getFunctionValue(x0)
    y2 = filt.getPolyValue(x0)
    y3 = filt.getSmoothValue(x0)
    y4 = filt.getTrendValue(x0)
    y5 = y3 - y4

    # Seasonal Cycle
    # x and y are original data points
    trend = filt.getTrendValue(time)
    detrend = meas - trend
    harmonics = filt.getHarmonicValue(x0)
    smooth_cycle = harmonics + filt.smooth - filt.trend
    # residuals from the function
    resid_from_func = filt.resid
    # smoothed residuals
    resid_smooth = filt.smooth
    # trend of residuals
    resid_trend = filt.trend
    # residuals about the smoothed line
    resid_from_smooth = filt.yp - filt.getSmoothValue(meas.index)
    deriv = filt.deriv

    return pd.DataFrame({'GrowthRate': deriv, 'Function': y1, 'Poly': y2,
                         'SmoothCurve': y3, 'Trend': y4, 'Cycle': smooth_cycle,
                         'Residual': resid_trend, 'Detrended': y5},
                        index=pd.Index(x0, name='datetime'))
