# Standard library imports.
from pathlib import Path
from typing import Optional

# Related third party imports.
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Local application/library specific imports.
from icoscp_obspack.config import Config
from icoscp_obspack.utils.ts_filter import ghg_filter_ts


def plot_timeseries_station(
        c: Config,
        icos_df: pd.DataFrame,
        st_id: str = '',
        hgh: int = -1,
        f_name: str = ''
) -> None:
    """Run ccgfilt for Mauna Loa and the chosen station."""
    path_to_png = Path(c.png, f_name)
    try:
        df = ghg_filter_ts(icos_df.JulDate, icos_df.Meas)
        gas_label: str
        if c.gas == 'co2':
            gas_label = 'CO${_2}$'
            unit = '[µmol/mol]'
            limy = [380, 460]
        elif c.gas == 'ch4':
            gas_label = 'CH${_4}$'
            unit = '[nmol/mol]'
            limy = [1800, 2500]
        elif c.gas == 'n2o':
            gas_label = 'N${_2}$O'
            unit = '[nmol/mol]'
            limy = [315, 370]
        else:
            exit(f'Unknown or not implemented gas: {c.gas}.\nAborting...')

        generate_plot(df, c.global_avg_filtered, icos_df, c.global_avg, meas_name=gas_label, unit=unit,
                        station=f'{st_id} {str(hgh)}', png_file=path_to_png, x_lim=[2010, 2025.1],
                        y_lim=limy, do_png=c.do_png, plot=c.plot)
    except (AttributeError, KeyError, TypeError, ValueError, FileNotFoundError, OSError, NameError,
            IndexError) as plot_exception:
        print(f'Error in time filtering for station {st_id}; plot skipped due to: {plot_exception}')


def generate_plot(df, back, meas, mlo, meas_name: str = '', unit: str = '', station: str = '',
                  png_file: Optional[Path] = None, x_lim: list = [], y_lim: list = [], do_png: bool = True, plot: bool = False):
    """Plot measurements, trend, smoothed curve."""
    l2 = meas.loc[meas.Level == 2]
    ax1 = l2.plot(x='JulDate', y='Meas', fontsize=12, label=station+' L2', linewidth=0, color='green',
                  marker='+', markersize=4, figsize=(15, 8))
    l15 = meas.loc[meas.Level == 15]
    l15.plot(ax=ax1, x='JulDate', y='Meas', label=station+' L1.5', linewidth=0, color='olive', marker='+',
             markersize=4, figsize=(15, 8))
    l1 = meas.loc[meas.Level == 1]
    l1.plot(ax=ax1, x='JulDate', y='Meas', linewidth=0, color='red', marker='+', markersize=4,
            label=station+' NRT')
    l0 = meas.loc[meas.Level == 0]
    l0.plot(ax=ax1, x='JulDate', y='Meas', linewidth=0, color='lightgreen', marker='+', markersize=4,
            label=station+' Hist.')
    ax1.set_facecolor('whitesmoke')
    plt.ylabel(meas_name+' '+unit, fontsize=14)
    sns.set_style("white")
    df.plot(y='Trend', ax=ax1, color='black', label='Trend from '+station)
    if not back.empty:
        back.plot(y='Trend', ax=ax1, color='yellow', linestyle="--", label='Global trend')
    mlo.plot(x='JulDate', y='Meas', ax=ax1, linewidth=0, color='red', marker='+', markersize=3,
             label='Global av.')
    h1, l1 = ax1.get_legend_handles_labels()
    # Remove the top right second legend.
    ax1.get_legend().remove()
    plt.xticks(np.arange(x_lim[0], x_lim[1], step=1))
    ax1.set_title(meas_name+' at '+station+'; measurements, trend and seasonal signal', fontsize=18)
    df.SmoothCurve.plot(ax=ax1, fontsize=12, color='blue', label='Smoothed curve '+station)
    ax1.set_xlabel('Year', fontsize=14)
    ax1.grid(zorder=0, linestyle='-.', color='grey')
    plt.legend(h1, l1, loc=2)
    plt.xlim(x_lim)
    plt.ylim(y_lim)
    if png_file is not None and do_png:
        plt.savefig(png_file, dpi=150)
    if plot:
        plt.show(close=True)
    plt.close()