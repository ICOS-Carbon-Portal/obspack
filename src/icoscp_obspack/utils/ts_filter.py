# Related third party imports.
import pandas as pd

# Local application/library specific imports.
from icoscp_obspack.utils import ccgfilt


def ghg_filter_ts(time, meas, shortTerm=80, longTerm=667, numPolyterms=3,
                  numHarmonics=4, timeZero=2010, sampleInterval=1/24) \
        -> pd.DataFrame:
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