"""Module to handle exoplanet vetters."""
import exovetter.sweet as sweet
from exovetter import odd_even
from exovetter import lpp
from exovetter import transit_coverage
from abc import ABC, abstractmethod
from astropy import units as u
from exovetter import const as exo_const
from exovetter import lightkurve_utils


__all__ = ['BaseVetter', 'Lpp', 'Sweet', 'OddEven', 'TransitPhaseCoverage']


class BaseVetter(ABC):
    """Base class for vetters.
    Each vetting test should be a subclass of this class.

    Parameters
    ----------
    kwargs : dict
        Store the configuration parameters common to all
        Threshold Crossing Events (TCEs).
        For example, for the Odd-even test, it might specify the significance
        of the depth difference that causes a TCE to fail.

    """
    @abstractmethod
    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def run(self, tce, lightcurve):
        """Run the vetter on the specified Threshold Crossing Event (TCE)
        and lightcurve to obtain metric.

        Parameters
        ----------
        tce : `~exovetter.tce.Tce`
            TCE.

        lightcurve : obj
            ``lightkurve`` object that contains the detrended lightcurve's
            time and flux arrays.

        Returns
        -------
        result : dict
            A dictionary of metric values.

        """
        pass

    def plot(self):  # pragma: no cover
        """Generate a diagnostic plot."""
        pass


class Lpp(BaseVetter):
    """Class to handle LPP Vetter functionality.

    Parameters
    ----------
    map_filename : str or `None`
        Full path to a LPP ``.mat`` file.
        See `~exovetter.lpp.Loadmap`.

    lc_name : str
        Name of the flux array in the ``lightkurve`` object.

    Attributes
    ----------
    map_info : `~exovetter.lpp.Loadmap`
        Map info from ``map_filename``.

    lc_name : str
        Input ``lc_name``.

    tce, lc
        Inputs to :meth:`run`. TCE for this vetter should also
        contain ``snr`` estimate.

    lpp_data : `exovetter.lpp.Lppdata`
        Populated by :meth:`run`.

    raw_lpp : float
        Raw LPP value, populated by :meth:`run`.

    norm_lpp : float
        LPP value normalized by period and SNR, populated by :meth:`run`.

    plot_data : dict
        The folded, binned transit prior to the LPP transformation,
        populated by :meth:`run`.

    """

    def __init__(self, map_filename=None, lc_name="flux"):
        self.map_info = lpp.Loadmap(filename=map_filename)
        self.lc_name = lc_name
        self.tce = None
        self.lc = None
        self.norm_lpp = None
        self.raw_lpp = None
        self.plot_data = None

    def run(self, tce, lightcurve):
        self.tce = tce
        self.lc = lightcurve

        self.lpp_data = lpp.Lppdata(self.tce, self.lc, self.lc_name)

        self.norm_lpp, self.raw_lpp, self.plot_data = lpp.compute_lpp_Transitmetric(self.lpp_data, self.map_info)  # noqa: E501

        # TODO: Do we really need to return anything if everything is stored as
        # instance attributes anyway?
        return {
            'raw_lpp': self.raw_lpp,
            'norm_lpp': self.norm_lpp,
            'plot_data': self.plot_data}

    def plot(self):  # pragma: no cover
        if self.plot_data is None:
            raise ValueError(
                'LPP plot data is empty. Execute self.run(...) first.')

        # target is populated in TCE, assume it already exists.
        target = self.tce.get('target_name', 'Target')
        lpp.plot_lpp_diagnostic(self.plot_data, target, self.norm_lpp)


class OddEven(BaseVetter):
    """Odd-even Metric"""

    def __init__(self, lc_name="flux"):
        self.lc_name = lc_name
        self.odd_depth = None
        self.even_depth = None
        self.sigma = None

    def run(self, tce, lightcurve, dur_frac=0.3):
        self.time, self.flux, time_offset_str = \
            lightkurve_utils.unpack_lk_version(lightcurve, self.lc_name)

        self.dur_frac = dur_frac

        time_offset_q = getattr(exo_const, time_offset_str)

        self.period = tce['period'].to_value(u.day)
        self.duration = tce['duration'].to_value(u.day)
        self.epoch = tce.get_epoch(time_offset_q).to_value(u.day)

        self.oe_sigma, self.odd_depth, self.even_depth = \
            odd_even.calc_odd_even(self.time, self.flux, self.period,
                                   self.epoch, self.duration, ingress=None,
                                   dur_frac=self.dur_frac)

    def plot(self):  # pragma: no cover
        odd_even.diagnostic_plot(self.time, self.flux, self.period,
                                 self.epoch, self.duration * self.dur_frac,
                                 self.odd_depth, self.even_depth)


class TransitPhaseCoverage(BaseVetter):
    """Transit Phase Coverage Vetter

    Attributes
    ----------
    tce : tce object
        tce object is a dictionary that contains information about the tce
        to vet, like period, epoch, duration, depth

    lc : lightkurve object
       lightkurve object with the time and flux of the data to use for vetting.

    nbins : integer
       number bins to divide-up the in transit points. default is 10, giving
       an accuracy of 0.1.

    ndur : float
      the code considers a phase that cover ndur * transit_duration as
      "in transit"

    tp_cover : float
        fraction of coverage

    """

    def __init__(self, lc_name="flux"):
        self.lc_name = lc_name

    def run(self, tce, lc, nbins=10, ndur=2):

        time, flux, time_offset_str = \
            lightkurve_utils.unpack_lk_version(lc, self.lc_name)  # noqa: E50

        p_day = tce['period'].to_value(u.day)
        dur_hour = tce['duration'].to_value(u.hour)

        time_offset_q = getattr(exo_const, time_offset_str)
        epoch = tce.get_epoch(time_offset_q).to_value(u.day)

        self.tp_cover, self.hist, self.bins = \
            transit_coverage.calc_coverage(time, p_day, epoch, dur_hour,
                                           ndur=ndur, nbins=nbins)

    def plot(self):  # pragma: no cover
        transit_coverage.plot_coverage(self.hist, self.bins)


class Sweet(BaseVetter):
    """Class to handle SWEET Vetter functionality.

    Parameters
    ----------
    threshold_sigma : float
        Threshold for comparing signal to transit period.

    Attributes
    ----------
    tce : tce object
        tce object is a dictionary that contains information about the tce
        to vet, like period, epoch, duration, depth

    lc : lightkurve object
       lightkurve object with the time and flux of the data to use for vetting.

    result : dict
        ``'amp'`` contains the best fit amplitude, its uncertainty, and
        amplitude-to-uncertainty ratio for half-period, period, and
        twice the period. ``'msg'`` contains warnings, if applicable.
        Populated by :meth:`run`.

    lsf : `~exovetter.utils.WqedLSF`
        Least squares fit object, populated by :meth:`run`.

    """

    def __init__(self, lc_name="flux", threshold_sigma=3):
        self.tce = None
        self.lc = None
        self.result = None
        self.sweet_threshold_sigma = threshold_sigma
        self.lc_name = lc_name

    def run(self, tce, lightcurve, plot=False):
        self.tce = tce
        self.lc = lightcurve

        time, flux, time_offset_str = \
            lightkurve_utils.unpack_lk_version(self.lc, self.lc_name)  # noqa: E50

        period_days = tce['period'].to_value(u.day)
        time_offset_q = getattr(exo_const, time_offset_str)
        epoch = tce.get_epoch(time_offset_q).to_value(u.day)
        duration_days = tce['duration'].to_value(u.day)

        self.sweet = sweet.sweet(time, flux,
                                 period_days, epoch, duration_days,
                                 plot=plot
                                 )
        self.sweet = sweet.construct_message(
            self.sweet, self.sweet_threshold_sigma)
        return self.sweet

    def plot(self):  # pragma: no cover
        self.run(self.tce, self.lc, plot=True)
