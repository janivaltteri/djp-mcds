import numpy
import datetime

from scipy.stats import linregress

from .models import Series

coefs = {
    # 'vm': 0.0224,
    'zerotemp': 273.15,
    'convf': 3600.0, # number of seconds in an hour
    'molmass_co2': 44.0095,
    'molmass_ch4': 16.0425,
    'molmass_n2o': 44.0130
}

class FluxCalcException (Exception):
    pass

def get_interval_for_series(s):
    meas  = s.measurements
    dspec = meas.dataspec
    spec  = dspec.spec
    spec_df = spec.get("datafile")
    if not spec_df:
        print("warning: series " + str(s.id) + " meas " + str(meas.id) +
              " dataspec " + str(dspec.id) +
              " does not contain datafile key")
        return 1.0
    else:
        spec_iv = spec_df.get("interval")
        if not spec_iv:
            print("warning: series " + str(s.id) + " meas " + str(meas.id) +
                  " dataspec " + str(dspec.id) +
                  " does not contain interval, assuming 1.0")
            return 1.0
        else:
            return spec_iv

def calculate_flux_value(s,interval,trimhead=0,trimtail=0):
    out = {}

    if isinstance(s.start_temp, (int,float)):
        if isinstance(s.end_temp, (int,float)):
            temp = (s.start_temp + s.end_temp)/2.0
        else:
            temp = s.start_temp
    elif isinstance(s.end_temp, (int,float)):
        temp = s.end_temp
    else:
        raise FluxCalcException("neither start_temp nor end_temp available")

    volume = s.volume / 1000.0 # dm3 to m3
    area   = s.area / 100.0 # dm2 to m2

    if s.gas == 'co2':
        molmass = coefs['molmass_co2']
    elif s.gas == 'ch4':
        molmass = coefs['molmass_ch4']
    elif s.gas == 'n2o':
        molmass = coefs['molmass_n2o']
    else:
        raise FluxCalcException("series gas not one of co2, ch4, n2o")

    values0 = s.values
    secs0 = numpy.array(range(len(values0)),dtype='d') * interval
    len0 = len(secs0)

    cut_head = s.pad_head + trimhead
    cut_tail = s.pad_tail + trimtail

    if len(secs0) != len(values0):
        raise FluxCalcException("len(secs0) != len(values0)")
    elif cut_head < 0:
        raise FluxCalcException("cut_head < 0")
    elif cut_tail < 0:
        raise FluxCalcException("cut_tail < 0")
    elif cut_head > len(values0):
        raise FluxCalcException("cut_head > len(values0)")
    elif cut_tail > len(values0):
        raise FluxCalcException("cut_tail > len(values0)")
    elif cut_head >= (len0 - cut_tail):
        raise FluxCalcException("cut_head >= len0 - cut_tail")

    values = values0[cut_head:(len0 - cut_tail)]
    secs = secs0[cut_head:(len0 - cut_tail)]

    if len(values) < 5:
        raise FluxCalcException("fewer values than 5")
    elif len(secs) < 5:
        raise FluxCalcException("fewer secs than 5")

    lr = linregress(secs,values)

    if s.unit == "ppm":
        ppconv = 1e-6
    elif s.unit == "ppb":
        ppconv = 1e-9
    else:
        raise FluxCalcException("unit not ppm or ppb")

    lflux = (((101325.0 * lr.slope * ppconv) /
              (8.31446 * (temp + coefs['zerotemp']))) *
             (volume / area) * molmass * coefs['convf'])

    residuals = values - (lr.intercept + lr.slope * secs)
    residual_mean = numpy.mean(numpy.power(residuals,2))

    out['slope']     = lr.slope
    out['intercept'] = lr.intercept
    out['lflux']     = lflux
    out['resid']     = residual_mean
    out['trim_head'] = trimhead
    out['trim_tail'] = trimtail
    out['volume']    = volume
    out['area']      = area

    return out
