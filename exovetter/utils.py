"""Utility functions."""

import sys
import warnings

import numpy as np

__all__ = ['sine', 'mark_transit_cadences', 'WqedLSF']


def sine(x, order, period=1):
    """Sine function for SWEET vetter."""
    w = 2 * np.pi / period
    if order == 0:
        return np.sin(w * x)
    elif order == 1:
        return np.cos(w * x)
    else:
        raise ValueError("Order should be zero or one")


def estimate_scatter(flux):
    """Estimate the typical scatter in a lightcurve.

    Uses the same method as Marshall vetter (Mullally et al 2017)

    Inputs:
    ----------
    flux
        (np 1d array). Flux to measure scatter of. Need not have
        zero mean.

    Returns:
    ------------
    (float) scatter of data in the same units as in the input ``flux``


    Notes:
    ----------
    Algorithm is reasonably insensitive to outliers. For best results
    uses outlier rejection on your lightcurve before computing scatter.
    Nan's and infs in lightcurve will propegate to the return value.
    """

    flux = flux[np.isfinite(flux)]
    diff = np.diff(flux)

    # Remove egregious outliers. Shouldn't make much difference
    idx = sigmaClip(diff, 5)
    diff = diff[~idx]

    # TODO: should this be a running mean?
    mean = np.mean(diff)
    mad = np.median(np.fabs(diff - mean))
    std = 1.4826 * mad

    # std is the rms of the diff. std on single point
    # is 1/sqrt(2) of that value,
    return float(std / np.sqrt(2))


def mark_transit_cadences(time, period_days, epoch_bkjd, duration_days,
                          num_durations=1, flags=None):
    """Create a logical array indicating which cadences are
    affected by a transit.

    Parameters
    ----------
    time : array_like
        Numpy 1D array of cadence times.

    period_days : float
        Transit period in days.

    epoch_bkjd : float
        Transit epoch.

    duration_days : float
        Duration of transit (start to finish). If you select a duration from
        first to last contact, all cadences affected by transit are selected.
        If you only select 2 to 3 contacts, only the interior region of the
        transit is selected.

    num_durations : int
        How much of the lightcurve on either side of the transit to mark.
        Default means to mark 1/2 the transit duration on either side of the
        transit center.

    flags : array_like or `None`
        If set, must be an array of booleans of length ``time``.
        Cadences where this array is `True` are ignored in the calculation.
        This is useful if some of the entries of time are NaN.

    Returns
    -------
    idx : array_like
        Array of booleans with the same length as ``time``.
        Element set to `True` are affected by transits.

    Raises
    ------
    ValueError
        Invalid input.

    """
    if flags is None:
        flags = np.zeros_like(time, dtype=np.bool_)

    good_time = time[~flags]
    i0 = np.floor((np.min(good_time) - epoch_bkjd) / period_days)
    i1 = np.ceil((np.max(good_time) - epoch_bkjd) / period_days)
    if not np.isfinite(i0) or not np.isfinite(i1):
        raise ValueError('Error bounding transit time')

    transit_times = epoch_bkjd + period_days * np.arange(i0, i1 + 1)
    big_num = sys.float_info.max  # A large value that isn't NaN
    max_diff = 0.5 * duration_days * num_durations

    idx = np.zeros_like(time, dtype=np.bool8)
    for tt in transit_times:
        diff = time - tt
        diff[flags] = big_num
        if not np.all(np.isfinite(diff)):
            raise ValueError('NaN found in diff of transit time')

        idx = np.bitwise_or(idx, np.fabs(diff) < max_diff)

    if not np.any(idx):
        warnings.warn('No cadences found matching transit locations')

    return idx


def median_detrend(flux, nPoints):
    """Quick and dirty median smooth function.
    Not designed to be at all effecient"""

    size = len(flux)
    filtered = np.zeros_like(flux)
    for i in range(size):
        lwr = max(i - nPoints, 0)
        upr = min(lwr + 2 * nPoints, size)
        lwr = upr - 2 * nPoints

        sub = flux[lwr:upr]

        offset = np.median(sub)
        filtered[i] = flux[i] - offset

    return filtered


def sigmaClip(y, nSigma, maxIter=1e4, initialClip=None):
    """Iteratively find and remove outliers

    Find outliers by identifiny all points more than **nSigma** from
    the mean value. The recalculate the mean and std and repeat until
    no more outliers found.

    Inputs
    ------
    y : numpy array
        Array to be cleaned
    nSigma : float
        Threshold to cut at.
        5 is typically a good value for
        most arrays found in practice.

    Optional Inputs
    ---------
    maxIter : int
        Maximum number of iterations

    initialClip : 1d boolean array
        If an element of initialClip is set to True,
        that value is treated as a bad value in the first iteration, and
        not included in the computation of the mean and std.

    Returns
    -------
    1d numpy array. Where set to True, the corresponding element of y
    is an outlier.
    """

    idx = initialClip
    if initialClip is None:
        idx = np.zeros(len(y), dtype=bool)

    if (len(idx) != len(y)):
        raise AssertionError('length of array y not equal to initialClip')

    # x = np.arange(len(y))
    # mp.plot(x, y, 'k.')

    oldNumClipped = np.sum(idx)
    for i in range(int(maxIter)):
        mean = np.nanmean(y[~idx])
        std = np.nanstd(y[~idx])

        newIdx = np.fabs(y - mean) > nSigma * std
        newIdx = np.logical_or(idx, newIdx)
        newNumClipped = np.sum(newIdx)

        # print "Iter %i: %i (%i) clipped points " \
        # %(i, newNumClipped, oldNumClipped)

        if newNumClipped == oldNumClipped:
            return newIdx

        oldNumClipped = newNumClipped
        idx = newIdx
        i += 1
    return idx


class WqedLSF:
    """Least squares fit to an analytic function based on ``lsf.c`` in Wqed,
    which in turn was based on Bevington and Robinson.

    Parameters
    ----------
    x : array_like
        1D numpy array containing ordinate (e.g., time).

    y : array_like
        1D numpy array containing coordinate (e.g., flux).

    s : array_like or float
        A scalar or 1D numpy array containing 1-sigma uncertainties.
        If not given, it is set to unity (default).

    order : int
        How many terms of function to fit. Default is 2.

    func : obj
        The analytic function to fit. Default is :func:`sine`.

    kwargs : dict
        Additional keywords to pass to ``func``.

    Raises
    ------
    ValueError
        Invalid input.

    """

    def __init__(self, x, y, s=None, order=2, func=sine, **kwargs):
        size = len(x)

        if func == sine and 'period' not in kwargs:
            raise ValueError("period must be provided for sine function")

        if size == 0:
            raise ValueError("x is zero length")
        if size != len(y):
            raise ValueError("x and y must have same length")

        if order < 1:
            raise ValueError("Order must be at least 1")
        if order >= size:
            raise ValueError("Length of input must be at least one greater "
                             "than order")

        if not np.all(np.isfinite(x)):
            raise ValueError("Nan or Inf found in x")
        if not np.all(np.isfinite(y)):
            raise ValueError("Nan or Inf found in y")

        if s is None:
            s = np.ones(size)
        elif np.isscalar(s):
            s = np.zeros(size) + s
        elif size != len(s):
            raise ValueError("x and s must have same length")
        elif not np.all(np.isfinite(s)):
            raise ValueError("Nan or Inf found in s")

        self.data_size = size
        self.x = x
        self.y = y
        self.s = s
        self.order = order
        self.func = func
        self.kwargs = kwargs

        self._fit()

    def _fit(self):
        """Fit the function to the data and return the best fit parameters."""

        df = np.empty((self.data_size, self.order))
        for i in range(self.order):
            df[:, i] = self.func(self.x, i, **self.kwargs)
            df[:, i] /= self.s

        A = np.dot(df.T, df)
        covar = np.linalg.inv(A)

        wy = self.y / self.s
        beta = np.dot(wy, df)
        params = np.dot(beta, covar)

        # Store results
        self._param = params
        self._cov = covar

    def get_best_fit_model(self, x=None):
        """Get best fit model to data.

        Parameters
        ----------
        x : array_like
            1D numpy array containing ordinates on which to compute the
            best fit model. If not given, use ordinates used in fit.

        Returns
        -------
        y : array_like
            Best fit model.

        """
        if x is None:
            x = self.x

        par = self.params
        y = np.zeros_like(x)
        for i in range(self.order):
            y += par[i] * self.func(x, i, **self.kwargs)
        return y

    @property
    def params(self):
        """Best fit parameters."""
        return self._param

    @property
    def covariance(self):
        """Covariance matrix for the best fit."""
        return self._cov

    @property
    def residuals(self):
        """Residuals, defined as ``y - best_fit``."""
        return self.y - self.get_best_fit_model()

    @property
    def variance(self):
        """Sum of the squares of the residuals."""
        resid = self.residuals
        return np.sum(resid * resid) / (self.data_size - self.order)

    def compute_amplitude(self):
        """Amplitude from best fit.

        .. note::

            Taken from Appendix 1 of Breger (1999, A&A 349, 225), which was
            written by M Montgomery.

        Returns
        -------
        amp, amp_unc : float
            Amplitude and its uncertainty.

        Raises
        ------
        ValueError
            Fitted function is not sine with order 2.

        """
        if self.func != sine or self.order != 2:
            raise ValueError('Only applicable to sine function with order=2')

        par = self.params
        amp = np.hypot(par[0], par[1])
        amp_unc = np.sqrt(2 * self.variance / self.data_size)

        return amp, amp_unc

    def compute_phase(self):
        """Phase from best fit.

        .. note::

            Taken from Appendix 1 of Breger (1999, A&A 349, 225), which was
            written by M Montgomery.

        Returns
        -------
        phase, phase_unc : float
            Phase and its uncertainty.

        Raises
        ------
        ValueError
            Fitted function is not sine with order 2.

        """
        par = self.params
        amp, amp_unc = self.compute_amplitude()

        # r1 is cos(phase), r2 is -sin(phase) (because fitting wx-phi)
        r1 = par[0] / amp
        r2 = -par[1] / amp

        # Remember the sign of the cos and sin components
        invcos = np.arccos(np.fabs(r1))
        invsin = np.arcsin(np.fabs(r2))

        # Decide what quadrant we're in.
        # First quadrant is no-op: (r1>=0 and r2 >=0)
        if r1 <= 0 and r2 >= 0:  # Second quadrant
            invcos = np.pi - invcos
            invsin = np.pi - invsin
        elif r1 <= 0 and r2 <= 0:  # Third quadrant
            invcos += np.pi
            invsin += np.pi
        elif r1 >= 0 and r2 <= 0:  # Fourth quadrant
            invcos = 2 * np.pi - invcos
            invsin = 2 * np.pi - invsin

        # Choose the average of the two deteminations to
        # reduce effects of roundoff error
        phase = 0.5 * (invcos + invsin)

        return phase, amp_unc / amp
