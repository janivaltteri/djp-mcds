import pandas

from time import sleep

from celery import shared_task

from django.contrib.auth.models import User

from .datareaders import (
    read_fieldform,
    get_series_data_from_ff,
    read_df_licor,
    read_df_egm5,
    read_df_egm4,
    read_df_gasmet,
    read_df_licorsmart
)

from .models import (
    Project,
    WorkerAssignment,
    Dataspec,
    DataspecAssignment,
    Measurements,
    Series,
    Flux,
    Download
)

from .fluxcalc import calculate_flux_value

files_url = '/opt/djpmcds/files/'

@shared_task
def test_task(k):
    value = k * 2
    print("test_task")
    print(value)
    return value

@shared_task
def process_dataset(meas_id):
    meas = Measurements.objects.get(pk=meas_id)

    if meas.processed:
        ##print('task: already processed')
        return 0

    print("task: processing meas " + str(meas_id))

    dspec = Dataspec.objects.get(pk=meas.dataspec.id)

    ##ff_path = files_url + str(meas.fieldform)
    ff_path = str(meas.fieldform)

    ff = read_fieldform(dspec.spec,meas.fieldform,True,True)
    if not ff.get('ok'):
        err_list         = ff.get("err")
        if err_list:
            meas.errors  = "Fieldform read error: " + " - ".join(err_list)
        else:
            meas.errors  = "Fieldform read error: ?" #todo
        meas.fieldstatus = "invalid"
        meas.valid       = False
        meas.processed   = True
        meas.save()
        return 0
    else:
        meas.fieldstatus = "valid"
        meas.save()

    print("task: fieldform read")

    spec   = dspec.spec
    device = spec.get("datafile").get("device")

    print("task: got spec")

    if device == "LI-COR":
        df = read_df_licor(spec,meas.datafile,True)
    elif device == "LI-COR Smartchamber":
        df = read_df_licrosmart(meas.datafile,True)
    elif device == "Gasmet":
        df = read_df_gasmet(spec,meas.datafile,True)
    elif device == "EGM5":
        df = read_df_egm5(meas.datafile,True)
    elif device == "EGM4":
        df = read_df_egm4(meas.datafile,meas.measure_date.year,True)
    else:
        meas.errors     = "dataspec device not identified"
        meas.datastatus = "invalid"
        meas.valid      = False
        meas.processed  = True
        meas.save()
        return 0

    print("task: datafile read")
    
    if not df.get("ok"):
        err_list = df.get("err")
        if err_list:
            meas.errors = "Datafile read error: " +  " - ".join(err_list)
        else:
            meas.errors = "Datafile read error: ?" #todo
        meas.datastatus = "invalid"
        meas.valid      = False
        meas.processed  = True
        meas.save()
        return 0

    data_obj = get_series_data_from_ff(df['df'],ff['df'],dspec.spec)
    if data_obj.get('ok'):
        data = data_obj.get('data')
    else:
        meas.errors    = "Series read error: " + data_obj.get("err")
        meas.valid     = False
        meas.processed = True
        meas.save()
        return 0

    print("task: series data received")

    siteids = []
    all_series_good = True
    series_error_msg = ""
    min_pts = spec.get("durations").get("min")
    max_pts = spec.get("durations").get("max")
    for i in range(len(data)):
        dv = data[i]
        is_valid_min = len(dv.get('values')) >= min_pts
        is_valid_max = len(dv.get('values')) <= max_pts
        is_valid = is_valid_min | is_valid_max
        try:
            newseries = Series(measurements = meas,
                               date       = dv.get('date'),
                               siteid     = dv.get('siteid'),
                               subsiteid  = dv.get('subsiteid'),
                               point      = dv.get('point'),
                               start_time = dv.get('start_time'),
                               end_time   = dv.get('end_time'),
                               start_temp = dv.get('start_temp'),
                               end_temp   = dv.get('end_temp'),
                               area       = dv.get('area'),
                               volume     = dv.get('volume'),
                               gas        = dv.get('gas'),
                               unit       = dv.get('unit'),
                               env        = dv.get('env'),
                               pad_head   = dv.get('pad_head'),
                               pad_tail   = dv.get('pad_tail'),
                               values     = dv.get('values'),
                               valid      = is_valid)
            newseries.save()
        except Exception as e:
            print("Error: could not create series - " + str(e))
            print(data[i])
            series_error_msg = str(e)
            all_series_good = False
        siteids.append(dv.get('siteid'))

    print("task: series generated")

    siteids_list = list(set(siteids))
    meas.siteids = " ".join(str(x) for x in siteids_list)

    if not all_series_good:
        meas.errors    = "Errors creating series - " + series_error_msg
        meas.valid     = False
        meas.processed = True
        meas.save()
        return 0
  
    ## do autotrims
    user = User.objects.filter(username="autotrimmer").first()
    if not user:
        meas.errors    = "autotrimmer user does not exist"
        meas.valid     = False
        meas.processed = True
        meas.save()
        return 0

    series = Series.objects.filter(measurements=meas).all()

    interval = dspec.spec.get("datafile").get("interval")
    if not interval:
        meas.errors    = "could not get interval from dataspec"
        meas.valid     = False
        meas.processed = True
        meas.save()
        return 0

    all_autotrims_good = True

    for s in series:
        try:
            flux = calculate_flux_value(s,interval)
        except Exception as e:
            print("autotrim failed for meas " + str(meas.id) + " series " + str(s.id))
            all_autotrims_good = False
        else:
            newflux = Flux(series    = s,
                           trimmer   = user,
                           slope     = flux['slope'],
                           trim_head = flux['trim_head'],
                           trim_tail = flux['trim_tail'],
                           intercept = flux['intercept'],
                           flux      = flux['lflux'],
                           resid     = flux['resid'],
                           bad       = False)
            newflux.save()

    print("task: fluxes generated")
            
    if not all_autotrims_good:
        meas.errors = "errors calculating autotrims"
    else:
        meas.errors = ""

    meas.fieldstatus = "valid"
    meas.datastatus  = "valid"
    meas.valid       = True
    meas.processed   = True
    meas.save()

    print("task process_dataset done!")
    return 0

@shared_task
def make_download(project_name,user_id,download_id):
    user     = User.objects.get(pk=user_id)
    project  = Project.objects.get(name=project_name)
    meas     = Measurements.objects.filter(project=project).all()
    autouser = User.objects.filter(username="autotrimmer").first()
    download = Download.objects.get(pk=download_id)
    data = []

    for m in meas:
        dataspec = m.dataspec
        series = Series.objects.filter(measurements=m).all()

        for s in series:
            dict = { 'project':    project_name,
                     'date':       s.date,
                     'siteid':     s.siteid,
                     'subsiteid':  s.subsiteid,
                     'point':      s.point,
                     'uploader':   m.measurer.username,
                     'start_time': s.start_time,
                     'end_time':   s.end_time,
                     'gas':        s.gas,
                     'volume':     s.volume,
                     'area':       s.area,
                     'valid':      s.valid }

            env = s.env
            for key, value in env.items():
                dict[key] = value

            aflux = Flux.objects.filter(series=s,trimmer=autouser).all()

            if len(aflux) == 0:
                dict['a_flux'] = 'NA'
            elif len(aflux) > 1:
                dict['a_flux'] = 'error'
            else:
                f = aflux[0]
                dict['a_flux']      = f.flux
                dict['a_resid']     = f.resid
                dict['a_bad']       = f.bad
                dict['a_trim_head'] = f.trim_head
                dict['a_trim_tail'] = f.trim_tail
                dict['a_slope']     = f.slope
                dict['a_intercept'] = f.intercept

            pflux = Flux.objects.filter(series=s,trimmer=user).all()

            if len(pflux) == 0:
                dict['p_flux'] = 'NA'
            elif len(pflux) > 1:
                dict['p_flux'] = 'error'
            else:
                f = pflux[0]
                dict['p_flux']      = f.flux
                dict['p_resid']     = f.resid
                dict['p_bad']       = f.bad
                dict['p_trim_head'] = f.trim_head
                dict['p_trim_tail'] = f.trim_tail
                dict['p_slope']     = f.slope
                dict['p_intercept'] = f.intercept

            data.append(dict)

    df = pandas.DataFrame(data)

    filename = download.file
    print('task make_download writing to ' + str(filename))

    df.to_csv(download.file, index=False)
    download.ready = True
    download.save()

    print('task make_download done!')
