"""Test trapezoid fit."""

import numpy as np

from exovetter.trapezoid_fit import TrapezoidFit, trapezoid_fit


def test_dave_trapz_fit():
    """Adapted from DAVE test case."""
    # Make some fake data
    dataSpan = 80.0  # in Days
    exposureLength = 1.0 / 48.0  # in Days simulating 48 cadences per day
    nData = int(dataSpan / exposureLength)
    noiseLevel = 40.0  # noise per observation in ppm
    signalDepth = 300.0  # signal depth in ppm
    signalDuration = 5.0 / 24.0  # in Days
    signalDurationHours = signalDuration * 24.0
    signalPeriod = 10.4203  # in Days
    signalEpoch = 5.1  # in Days
    timeSeries = np.linspace(0, int(dataSpan), nData)
    dataSeries = 1.0 + np.random.randn(nData) / 1.0e6 * noiseLevel
    errorSeries = np.full_like(dataSeries, noiseLevel / 1.0e6)
    # Instantiate trp_ioblk class and fill in values
    ioblk = TrapezoidFit()
    ioblk.parm.samplen = 15
    ioblk.parm.cadlen = exposureLength
    ioblk.fitregion = 4.0
    ioblk.normlc = dataSeries
    ioblk.normes = errorSeries
    ioblk.normots = timeSeries
    ioblk.origests.period = signalPeriod
    ioblk.origests.epoch = signalEpoch
    ioblk.origests.duration = signalDurationHours  # input duration is hours
    ioblk.origests.depth = signalDepth
    # setup some more variables
    ioblk.trp_setup()
    ioblk.physvals = np.array([0.0, signalDepth/1.0e6, signalDuration, 0.1])
    # Make a model trapezoid light curve
    ioblk.trapezoid_model()

    # Phase data
    # _ = phase_data(timeSeries, signalPeriod, signalEpoch)
    # Insert signal
    dataSeries = dataSeries * ioblk.modellc

    # Test fitting
    ioblk = trapezoid_fit(
        timeSeries, dataSeries, errorSeries,
        signalPeriod, signalEpoch+0.001, signalDurationHours*0.9,
        signalDepth*1.1,
        fitTrialN=2, fitRegion=4.0, errorScale=1.0, debugLevel=3,
        sampleN=15, showFitInterval=30)

    # test generating model
    newioblk = TrapezoidFit.trapezoid_model_onemodel(
        timeSeries, signalPeriod,
        signalEpoch, signalDepth, signalDurationHours,
        signalDurationHours*0.1, ioblk.parm.samplen)

    # plt.plot(phasedSeries, newioblk.modellc,'.b')
    newioblk = newioblk.trapezoid_model_raw(
        signalEpoch+0.05, signalDepth*1.5,
        signalDurationHours*2.0, signalDurationHours*2.0*0.2)
    # plt.plot(phasedSeries, newioblk.modellc, '.r')
