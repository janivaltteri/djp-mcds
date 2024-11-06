import os
import numpy
import pandas
import datetime

def read_fieldform(dataspec,filepath,return_df,return_dict):

    out = { 'ok': False, 'err': [], 'warn': [] }

    try:
        df = pandas.read_excel(filepath,sheet_name="Measurements",header=0,skiprows=[1])
    except FileNotFoundError as e:
        out['err'].append("file not found on the server filesystem path " + str(filepath))
        return out
    except Exception as e:
        out['err'].append("exception occurred in pandas.read_excel ")
        out['err'].append(str(e))
        return out

    ffspec = dataspec.get("fieldform")
    ffreq = ffspec.get("req")
    ffenv = ffspec.get("env")

    ## get start time column name
    start_time_colname = ffreq.get("start_time").get("column")
    df.dropna(subset=[start_time_colname],inplace=True)
    df.reset_index(drop=True,inplace=True)

    req_names = [key for key in ffreq]

    ## check that required columns exist
    req_cols = [value.get("column") for key, value in ffreq.items()]
    ##req_cols = [rc["column"] for rc in ffspec["req"]]
    env_cols = [ec["column"] for ec in ffenv]
    required_columns = req_cols + env_cols

    missing_columns = False
    for rq in required_columns:
        if not rq in df.columns:
            out['err'].append(rq + ' missing from fieldform')
            missing_columns = True

    if missing_columns:
        return out

    ## check start times
    if "start_time" in req_names:
        start_times_ok = True

        stime_colname = ffreq.get("start_time").get("column")
        start_time_types_ok = df[stime_colname].apply(lambda x: True if
                                                      type(x) == datetime.time
                                                      else False)

        if not start_time_types_ok.all():
            try:
                for i in range(df.shape[0]):
                    if type(df.loc[i,stime_colname]) != datetime.time:
                        df.loc[i,stime_colname] = \
                            pandas.to_datetime(df[stime_colname][i]).time()
            except Exception as e:
                out['err'].append('Error parsing start times')
                out['err'].append(str(e))
                start_times_ok = False

        if not start_times_ok:
            return out

    ## check end times
    if "end_time" in req_names:
        end_times_ok = True

        etime_colname = ffreq.get("end_time").get("column")
        end_time_types_ok = df[etime_colname].apply(lambda x: True if
                                                    type(x) == datetime.time
                                                    else False)

        if not end_time_types_ok.all():
            try:
                for i in range(df.shape[0]):
                    if type(df.loc[i,etime_colname]) != datetime.time:
                        df.loc[i,etime_colname] = \
                            pandas.to_datetime(df[etime_colname][i]).time()
            except Exception as e:
                out['err'].append('Error parsing start times')
                out['err'].append(str(e))
                end_times_ok = False

        if not end_times_ok:
            return out

    ## check measurement durations
    ## todo: use duration limits from dataspec
    if ("end_time" in req_names) and ("start_time" in req_names):
        durations_ok = True

        starts = df[stime_colname].to_list()
        ends = df[etime_colname].to_list()

        if len(starts) != len(ends):
            out['err'].append('start and end times mismatch ')
            durations_ok = False
        else:
            for i in range(len(starts)): # todo: use zip?
                start_t = datetime.datetime.combine(datetime.date.today(),starts[i])
                end_t = datetime.datetime.combine(datetime.date.today(),ends[i])
                duration = (end_t - start_t).total_seconds()
                if duration < 30:
                    out['err'].append('row ' + str(i) + ' has duration < 30 seconds ')
                    durations_ok = False
                elif duration > 1800:
                    out['err'].append('row ' + str(i) + ' has duration > 1800 seconds ')
                    durations_ok = False

        if not durations_ok:
            return out

    ## check that the date column is readable
    if "date" in req_names:
        dates_ok = True

        date_colname = ffreq.get("date").get("column")
        date_dtype = df.dtypes[date_colname]
        
        if date_dtype == "int64":
            ## if date column type is int64 the dashes are probably missing
            ## try to read in as YYYYMMDD
            df[date_colname] = pandas.to_datetime(df[date_colname],
                                                  format='%Y%m%d',errors='coerce')
            if df[date_colname].isnull().any():
                out['err'].append('cannot parse date column (tried parsing as YYYYMMDD)')
                dates_ok = False
            else:
                out['warn'].append('date values were parsed as YYYYMMDD, should be YYYY-MM-DD')
        else:
            df[date_colname] = pandas.to_datetime(df[date_colname],
                                                  format='%Y-%m-%d',errors='coerce')
            if df[date_colname].isnull().any():
                out['err'].append('cannot parse date column (tried parsing as YYYY-MM-DD)')
                dates_ok = False

        if not dates_ok:
            return out

    ## check that site ID is available for all rows
    if "site" in req_names:
        sites_ok = True

        site_colname = ffreq.get("site").get("column")

        # first site id must not be missing
        siteids = df[site_colname].to_list()
        if pandas.isna(siteids[0]):
            out['err'].append('first row site id is missing ')
            sites_ok = False

        # if any subsequent are missing, assume the value is the same as above
        missing = pandas.isna(siteids)
        if any(missing):
            out['warn'].append('some rows are missing site id, assuming the same as above')
            for i in range(1,len(siteids)):
                if pandas.isna(siteids[i]):
                    siteids[i] = siteids[i-1]
            new_siteids = pandas.Series(siteids, index = df.index)
            df[site_colname] = new_siteids

        if not sites_ok:
            return out

    ## check chamber volume and area
    if "chamber_volume" in req_names:
        chambervol_ok = True

        chambervol_colname = ffreq.get("chamber_volume").get("column")

        ## check that a) column type is numeric, b) values are not nan, c) values > 0.0

        if df[chambervol_colname].dtype.kind not in 'iuf':
            ##if df.dtypes[chambervol_colname] == object:
            try:
                df[chambervol_colname] = pandas.to_numeric(
                    df[chambervol_colname].astype(str).str.replace(',','.'))
            except ValueError as e:
                out['err'].append('cannot convert chamber volume to numeric ')
                chambervol_ok = False
            except:
                out['err'].append('cannot parse chamber volume ')
                chambervol_ok = False

        if not chambervol_ok:
            return out

        c_vol_nans = df[chambervol_colname].apply(lambda x: True if numpy.isnan(x) else False)
        if c_vol_nans.any():
            out['err'].append('some chamber volumes are NaN')
            chambervol_ok = False
        else:
            c_vol_pos = df[chambervol_colname].apply(lambda x: True if x > 0.0 else False)
            if not c_vol_pos.all():
                out['err'].append('some chamber volumes are non-positive')
                chambervol_ok = False

        if not chambervol_ok:
            return out

    if "chamber_area" in req_names:
        chamberarea_ok = True

        chamberarea_colname = ffreq.get("chamber_area").get("column")

        if df[chamberarea_colname].dtype.kind not in 'iuf':
            ##if df.dtypes[chamberarea_colname] == object:
            try:
                df[chamberarea_colname] = pandas.to_numeric(
                    df[chamberarea_colname].astype(str).str.replace(',','.'))
            except ValueError as e:
                out['err'].append('cannot convert chamber area to numeric ')
                chamberarea_ok = False
            except:
                out['err'].append('cannot parse chamber area ')
                chamberarea_ok = False

        if not chamberarea_ok:
            return out

        c_area_nans = df[chamberarea_colname].apply(lambda x: True if numpy.isnan(x) else False)
        if c_area_nans.any():
            out['err'].append('some chamber volumes are NaN')
            chamberarea_ok = False
        else:
            c_area_pos = df[chamberarea_colname].apply(lambda x: True if x > 0.0 else False)
            if not c_area_pos.all():
                out['err'].append('some chamber volumes are non-positive')
                chamberarea_ok = False

        if not chamberarea_ok:
            return out

    ## check chamber temps
    if "start_temp" in req_names:
        starttemp_ok = True

        starttemp_colname = ffreq.get("start_temp").get("column")

        if df.dtypes[starttemp_colname] == object:
            try:
                df[starttemp_colname] = pandas.to_numeric(
                    df[starttemp_colname].astype(str).str.replace(',','.'))
            except ValueError as e:
                out['err'].append('cannot convert start temp to numeric ')
                starttemp_ok = False
            except:
                out['ree'].append('cannot parse start temp ')

        if not starttemp_ok:
            return out

    if "end_temp" in req_names:
        endtemp_ok = True

        endtemp_colname = ffreq.get("end_temp").get("column")

        if df.dtypes[endtemp_colname] == object:
            try:
                df[endtemp_colname] = pandas.to_numeric(
                    df[endtemp_colname].astype(str).str.replace(',','.'))
            except ValueError as e:
                out['err'].append('cannot convert end temp to numeric ')
                endtemp_ok = False
            except:
                out['err'].append('cannot parse end temp ')

        if not endtemp_ok:
            return out

    if ("start_temp" in req_names) and ("end_temp" in req_names):
        temps_ok = True
        for i in range(df.shape[0]):
            if numpy.isnan(df.loc[i,starttemp_colname]):
                if numpy.isnan(df.loc[i,endtemp_colname]):
                    temps_ok = False
                else:
                    df.loc[i,starttemp_colname] = df.loc[i,endtemp_colname]
            else:
                if numpy.isnan(df.loc[i,endtemp_colname]):
                    df.loc[i,endtemp_colname] = df.loc[i,starttemp_colname]

        if not temps_ok:
            out['err'].append('numerical values not available for either start temp or end temp ')
            return out
            
        ##startnans = df[starttemp_colname].apply(lambda x: True if numpy.isnan(x) else False)
        ##endnans = df[endtemp_colname].apply(lambda x: True if numpy.isnan(x) else False)
        ##if startnans.any() and endnans.any():
        ##    out['err'].append('numerical values not available for either start temp or end temp ')
        ##    temps_ok = False
        ##    return out

    ## everything ok, exit and return pandas dataframe and/or a dict

    if return_df:
        out['df'] = df

    if return_dict:
        out['nrecords'] = df.shape[0]
        if "site" in req_names:
            out['site'] = df[site_colname].tolist()
        if "start_time" in req_names:
            out['start_time'] = df[stime_colname].tolist()
        if "end_time" in req_names:
            out['end_time'] = df[etime_colname].tolist()

    out['ok'] = True
    
    return out

## not used currently
def check_df_is_licor(filepath):
    is_licor = False
    with open(filepath, "r") as rd:
        line = rd.readline()
        if line[0:6] == "Model:":
            is_licor = True
        elif line[0:6] == "\ufeffModel":
            ## utf-8 byte order mark is present in some files
            is_licor = True
    return is_licor

def read_df_licor(dataspec, filepath: str, return_df: bool):
    out = {'ok': False, 'err': []}

    ## read file
    try:
        df = pandas.read_csv(filepath,sep='\t',skiprows=5)
    except FileNotFoundError as e:
        out["err"].append("read_df_licor: FileNotFoundError ")
        return out
    except Exception as e:
        out["err"].append("read_df_licor: error in pandas.read_csv() ")
        return out
    df = df.drop(0)

    dt_spec = dataspec.get("datafile").get("datetime")

    ## ensure date is readable
    date_format = dt_spec.get("date").get("format")
    try:
        df["Date"] = pandas.to_datetime(df["DATE"],format=date_format).dt.date
    except:
        out["err"].append("read_df_licor: cannot parse DATE column ")
        return out

    ## ensure TIME is datetime
    time_format = dt_spec.get("time").get("format")
    try:
        df["Time"] = pandas.to_datetime(df["TIME"],format=time_format).dt.time
    except:
        out["err"].append("read_df_licor: error in pandas.to_datetime() ")
        return out

    gas_spec = dataspec.get("datafile").get("gases")
    gas_columns = [k.get("column") for k in gas_spec]

    for gc in gas_columns:
        if gc not in df.columns:
            out["err"].append("read_df_licor: gas column " + gc + " not present in datafile")
            return out

    for gc in gas_columns:
        try:
            df[gc] = pandas.to_numeric(df[gc])
        except:
            out["err"].append("read_df_licor: could not read " + gc +
                              " with pandas.to_numeric()")
            return out

    ## fill out obj
    df = df[["Date","Time"] + gas_columns]
    df.dropna(subset=gas_columns, inplace=True) ## tarvitaanko reset_index?
    out['dims'] = df.shape
    out['ok'] = True

    if return_df:
        out['df'] = df

    return out

## this was written for one specific data format from one user in HoliSoils project
## not useable for the general case! licor smart data are variable...
## assumes column names, currently only CO2
def read_df_licorsmart(dataspec, filepath: str, return_df: bool):
    out = {'ok': False, 'err': []}

    ## find lines that do not contain data
    textlines = []
    try:
        with open(filepath.path, "r") as rd:
            i = 0
            for line in rd:
                if not line:
                    break
                elif (line[:1] != "1"): # note: this used to be (line[:2] != "1,")
                    textlines.append(i)
                i += 1
    except Exception as e:
        out['err'].append("read_df_licosmart: error in open() - " + str(e))
        print(e)
        return out

    ## read in file
    try:
        cnames = ['Type','Etime','Date','Tcham','Pressure','H2O','CO2',
                  'Cdry','Tsoil','cell_p','DOY','Hour','cell_t','chamber_p_t','co2_wet',
                  'flow_rate','soilp_c','soilp_m','soilp_t']
        df = pandas.read_csv(filepath.path,sep=None,names=cnames,skiprows=textlines,
                             engine="python")
    except Exception as e:
        out['err'].append("read_df_licorsmart: error in pandas.read_csv() - " + str(e))
        print(e)
        return out

    ## interpret time
    time_format = dataspec.get("datafile").get("datetime").get("time").get("format")
    time_colname = dataspec.get("datafile").get("datetime").get("time").get("column")
    try:
        df["Time"] = pandas.to_datetime(df[time_colname],format=time_format).dt.time
    except:
        out['err'].append("read_df_licorsmart: cannot parse time from Date column ")
        return out

    ## interpret date
    date_format = dataspec.get("datafile").get("datetime").get("date").get("format")
    date_colname = dataspec.get("datafile").get("datetime").get("date").get("column")
    try:
        df["Date"] = pandas.to_datetime(df[date_colname],format=date_format).dt.date
    except:
        out['err'].append('read_df_licorsmart: cannot parse date from Date column ')
        return out

    ## success, fill out object if needed
    df = df[["Date","Time","CO2"]]
    df.dropna(subset="CO2", inplace=True) ## tarvitaanko reset_index?
    out['skiprows'] = textlines
    out['dims'] = df.shape
    out['ok'] = True

    if return_df:
        out['df'] = df

    return out

## TODO: currently only reads CO2, read other gases
def read_df_gasmet(dataspec,filepath: str, return_df: bool):
    out = {'ok': False, 'err': []}

    ## find lines that do not contain data
    textlines = []
    with open(filepath.path, "r") as rd:
        i = 0
        for line in rd:
            if i > 0:
                if not line:
                    break
                elif (line[:4] == "Line"):
                    textlines.append(i)
            i += 1

    ## read file
    try:
        df = pandas.read_csv(filepath.file,sep='\t',skiprows=textlines)
    except FileNotFoundError as e:
        out['err'].append("read_df_gasmet: FileNotFoundError ")
        return out
    except Exception as e:
        out['err'].append("read_df_gasmet: error in pandas.read_csv() ")
        return out

    ## ensure Date is readable
    date_format = dt_spec.get("date").get("format")
    try:
        df["Date"] = pandas.to_datetime(df["Date"],format=date_format).dt.date
    except:
        out['err'].append("read_df_gasmet: cannot parse Date column ")
        return out

    ## ensure Time is datetime
    time_format = dt_spec.get("time").get("format")
    try:
        df["Time"] = pandas.to_datetime(df["Time"],format=time_format).dt.time
    except:
        out['err'].append("read_df_gasmet: cannot parse Time column ")
        return out

    gas_spec = dataspec.get("datafile").get("gases")
    gas_columns = [k.get("column") for k in gas_spec]

    for gc in gas_columns:
        if gc not in df.columns:
            out['err'].append("read_df_gasmet: gas column " + gc + " not present in datafile")
            return out

    for gc in gas_columns:
        try:
            df[gc] = pandas.to_numeric(df[gc])
        except:
            out['err'].append("read_df_gasmet: could not read " + gc +
                              " with pandas.to_numeric()")
            return out

    ## fill out obj
    df = df[["Date","Time"] + gas_columns]
    df.dropna(subset=gas_columns,inplace=True) ## tarvitaanko reset_index?
    out['dims'] = df.shape
    out['ok'] = True

    if return_df:
        out['df'] = df

    return out

## currently only reads one type written by EGM5
def read_df_egm5(dataspec, filepath: str, return_df: bool):
    out = {'ok': False, 'err': []}

    ## find lines that do not contain data
    textlines = [0] ## append to this, always skip header
    with open(filepath.path, "r") as rd:
        i = 0
        for line in rd:
            if not line:
                break
            elif (line[:5] == "Start") | (line[:3] == "End") | (line[:4] == "Zero"):
                textlines.append(i)
            i += 1

    ## read in file
    try:
        ## on EGM5 there may be columns without names on the header
        ## they are named c18-c23 here
        cnames = ['Tag(M3)','Date','Time','Plot No.','Rec No.','CO2','Pressure',
                  'Flow','H2O','Tsen','O2','Error','Aux V','PAR','Tsoil','Tair',
                  'Msoil','c18','c19','c21','c22','c23']
        df = pandas.read_csv(filepath.file,sep=None,names=cnames,skiprows=textlines,
                             engine="python")
    except Exception as e:
        out['err'].append("read_df_egm5: error in pandas.read_csv() - " + str(e))
        return out

    ## interpret date
    date_format = dataspec.get("datafile").get("datetime").get("date").get("format")
    try:
        df["Date"] = pandas.to_datetime(df["Date"],format=date_format).dt.date
    except:
        out["err"].append("read_df_egm5: cannot parse Date column ")
        return out

    ## interpret time
    time_format = dataspec.get("datafile").get("datetime").get("time").get("format")
    try:
        df["Time"] = pandas.to_datetime(df["Time"],format=time_format).dt.time
    except:
        out["err"].append("read_df_egm5: cannot parse Time column ")
        return out

    ## success, fill out object if needed
    df = df[["Date","Time","CO2"]]
    df.dropna(subset=["CO2"],inplace=True) ## tarvitaanko reset_index?
    out['skiprows'] = textlines
    out['dims'] = df.shape
    out['ok'] = True

    if return_df:
        out['df'] = df

    return out

## EGM4 data files do not contain year, thus needs to be sent as parameter
## TODO: fix missing spec
def read_df_egm4(filepath: str, year: int, return_df: bool):
    out = {'ok': False, 'err': []}

    ## find lines that do not contain data
    textlines = []
    with open(filepath.path, "r") as rd:
        i = 0
        for line in rd:
            if not line:
                break
            elif line[:1] == ";":
                textlines.append(i)
            i += 1

    ## read in file
    try:
        cnames = ['Plot','RecNo','Day','Month','Hour','Min','CO2','mb Ref',
                  'mbR Temp','Input A','Input B','Input C','Input D','Input E',
                  'Input F','Input G','Input H','ATMP','Probe Type']
        df = pandas.read_csv(filepath.file,sep='\s+',names=cnames,skiprows=textlines)
    except:
        out['err'].append("read_df_egm4: error in pandas.read_csv() ")
        return out

    ## add record index column
    try:
        recnumbers = df['RecNo'].to_list()
        rec_index = [0] * df.shape[0]
        num_recs = 1
        for i in range(1,df.shape[0]):
            if recnumbers[i] != recnumbers[i-1] + 1:
                num_recs += 1
            rec_index[i] = num_recs - 1
        out['num_records'] = num_recs
        df["rec_index"] = pandas.Series(rec_index, index = df.index)
    except:
        out['err'].append("read_df_egm4: error in processing record indices ")
        return out

    ## add date column
    try:
        months = df['Month'].to_list()
        days = df['Day'].to_list()
        date_objs = [datetime.date(year,i,j) for i,j in zip(months,days)]
        df["Date"] = pandas.Series(date_objs, index = df.index)
    except:
        out['err'].append("read_df_egm4: error in processing date values ")
        return out

    ## add time column
    try:
        hours = df['Hour'].to_list()
        minutes = df['Min'].to_list()
        time_objs = [datetime.time(i,j,0) for i,j in zip(hours,minutes)]
        df["Time"] = pandas.Series(time_objs, index = df.index)
    except:
        out['err'].append("read_df_egm4: error in processing time values ")
        return out

    ## success, fill out object if needed
    out['skiprows'] = textlines
    out['dims'] = df.shape
    out['ok'] = True

    if return_df:
        out['df'] = df

    return out

def add_secs_to_time(timeval, secs_to_add):
    dummy_date = datetime.date(1, 1, 1)
    full_datetime = datetime.datetime.combine(dummy_date, timeval)
    added_datetime = full_datetime + datetime.timedelta(seconds=secs_to_add)
    return added_datetime.time()

def get_series_data_from_ff(df,ff,spec):
    shape = ff.shape
    dfspec = spec.get('datafile')
    dfgases = dfspec.get('gases')
    ffspec = spec.get('fieldform')
    ffreq = ffspec.get('req')
    ffenv = ffspec.get('env')
    num_envs = len(ffenv)

    try:
        pad_secs = int(spec.get("durations").get("pad"))
    except:
        return { 'ok': False, 'err': "Spec durations pad not interpretable as integer" }

    #date_field = next(filter(lambda x: x['name'] == 'date', ffreq))
    #siteid_field = next(filter(lambda x: x['name'] == 'site', ffreq))
    #subsiteid_field = next(filter(lambda x: x['name'] == 'subsite', ffreq))
    #point_field = next(filter(lambda x: x['name'] == 'point', ffreq))
    #starttime_field = next(filter(lambda x: x['name'] == 'start_time', ffreq))
    #endtime_field = next(filter(lambda x: x['name'] == 'end_time', ffreq))
    #area_field = next(filter(lambda x: x['name'] == 'chamber_area', ffreq))
    #volume_field = next(filter(lambda x: x['name'] == 'chamber_volume', ffreq))
    #starttemp_field = next(filter(lambda x: x['name'] == 'start_temp', ffreq))
    #endtemp_field = next(filter(lambda x: x['name'] == 'end_temp', ffreq))

    date_column      = ffreq.get("date").get("column")
    siteid_column    = ffreq.get("site").get("column")
    subsiteid_column = ffreq.get("subsite").get("column")
    point_column     = ffreq.get("point").get("column")
    starttime_column = ffreq.get("start_time").get("column")
    endtime_column   = ffreq.get("end_time").get("column")
    area_column      = ffreq.get("chamber_area").get("column")
    volume_column    = ffreq.get("chamber_volume").get("column")
    starttemp_column = ffreq.get("start_temp").get("column")
    endtemp_column   = ffreq.get("end_temp").get("column")

    ## renamed df datetime columns to "Date" and "Time" on all reader functions
    ##data_datetime = dfspec.get("datetime")
    date_col_name = "Date"
    time_col_name = "Time"

    out = []
    for i in range(shape[0]):
        row = ff.iloc[i]

        envs = {}
        for i in range(num_envs):
            env_name       = ffenv[i].get('name')
            env_column     = ffenv[i].get('column')
            envs[env_name] = str(row.get(env_column))

        for j in range(len(dfgases)):
            gas_name   = dfgases[j].get('name')
            gas_column = dfgases[j].get('column')
            gas_unit   = dfgases[j].get('unit')
            date       = row.get(date_column)
            start_time = row.get(starttime_column)
            end_time   = row.get(endtime_column)
            start_temp = row.get(starttemp_column)
            end_temp   = row.get(endtemp_column)
            ch_area    = row.get(area_column)
            ch_volume  = row.get(volume_column)

            st0 = datetime.datetime.combine(datetime.date.today(), start_time)
            et0 = datetime.datetime.combine(datetime.date.today(), end_time)
            duration = (et0 - st0).total_seconds()

            try:
                part = df[(df[date_col_name] == date.date()) &
                          (df[time_col_name] >= start_time) &
                          (df[time_col_name] <= end_time)]

                gas_values = part.get(gas_column).to_list()
            except:
                print("Error extracting slice from data")
                print("date_col_name: " + date_col_name)
                print("time_col_name: " + time_col_name)
                return { 'ok': False, 'err': "Error extracting slice from data" }

            try:
                pad_pre_time = add_secs_to_time(start_time,-pad_secs)
                pad_post_time = add_secs_to_time(end_time,pad_secs)

                pad_pre_part = df[(df[date_col_name] == date.date()) &
                                  (df[time_col_name] >= pad_pre_time) &
                                  (df[time_col_name] < start_time)]

                pad_post_part = df[(df[date_col_name] == date.date()) &
                                   (df[time_col_name] > end_time) &
                                   (df[time_col_name] <= pad_post_time)]

                gas_pre_values = pad_pre_part.get(gas_column).to_list()
                gas_post_values = pad_post_part.get(gas_column).to_list()

                pad_head = len(gas_pre_values)
                pad_tail = len(gas_post_values)

                full_values = gas_pre_values + gas_values + gas_post_values
            except:
                return { 'ok': False, 'err': "Error extracting padded slice from data" }

            out.append({'date': date.date(),
                        'siteid': row.get(siteid_column),
                        'subsiteid': row.get(subsiteid_column),
                        'point': str(row.get(point_column)),
                        'start_time': start_time,
                        'end_time': end_time,
                        'start_temp': start_temp,
                        'end_temp': end_temp,
                        'area': ch_area,
                        'volume': ch_volume,
                        'duration': duration,
                        'gas': gas_name,
                        'unit': gas_unit,
                        'pad_head': pad_head,
                        'pad_tail': pad_tail,
                        'values': full_values,
                        'env': envs})

    return { 'ok': True, 'data': out, 'err': "" }

## ds is the spec as a dict
## todo: should also check the contents and types of values
def validate_dataspec(ds):
    errors = []

    main_keys = ["datafile","fieldform","durations","chamber","soil","info"]
    for k in main_keys:
        if k not in ds:
            errors.append("dataspec does not contain key " + k)
            return { 'ok': False, 'err': errors }

    datafile = ds.get("datafile")
    datafile_keys = ["device","gases","datetime","interval"]
    for k in datafile_keys:
        if k not in datafile:
            errors.append("datafile spec does not contain key " + k)
            return { 'ok': False, 'err': errors }

    if not isinstance(datafile.get("interval"), (int, float)):
        errors.append("datafile interval is not numeric")
        return { 'ok': False, 'err': errors }

    fieldform = ds.get("fieldform")
    fieldform_keys = ["req","env"]
    for k in fieldform_keys:
        if k not in fieldform:
            errors.append("fieldform spec does not contain key " + k)
            return { 'ok': False, 'err': errors }

    req = fieldform.get("req")
    req_keys = ["date","site","subsite","point","start_time","end_time",
                "start_temp","end_temp","chamber_area","chamber_volume"]
    for k in req_keys:
        if k not in req:
            errors.append("fieldform req spec does not contain key " + k)
            return { 'ok': False, 'err': errors }

    durations = ds.get("durations")
    durations_keys = ["min","max","pad"]
    for k in durations_keys:
        if k not in durations:
            errors.append("durations spec does not contain key " + k)
            return { 'ok': False, 'err': errors }

    if not isinstance(durations.get("min"), (int, float)):
        errors.append("durations min is not numeric")
        return { 'ok': False, 'err': errors }
    if not isinstance(durations.get("max"), (int, float)):
        errors.append("durations max is not numeric")
        return { 'ok': False, 'err': errors }
    if not isinstance(durations.get("pad"), (int, float)):
        errors.append("durations pad is not numeric")
        return { 'ok': False, 'err': errors }

    ## chamber and soil not used currently

    info = ds.get("info")
    info_keys = ["author","date","description"]
    for k in info_keys:
        if k not in info:
            errors.append("info spec does not contain key " + k)
            return { 'ok': False, 'err': errors }

    device = ds.get("datafile").get("device")
    devices_list = ["LI-COR","LI-COR Smartchamber","Gasmet","EGM5","EGM4"]
    if device not in devices_list:
        errors.append("device " + device + " not supported")
        return { 'ok': False, 'err': errors }

    ## licor smartchamber and egms only support co2 currently
    gas_spec = ds.get("datafile").get("gases")
    gases = [k.get("name") for k in gas_spec]
    if device == "LI-COR Smartchamber":
        if len(gases) != 1:
            errors.append("LI-COR Smartchamber currently only supports co2")
            return { 'ok': False, 'err': errors }
        if gases[0] != "co2":
            errors.append("LI-COR Smartchamber currently only supports co2")
            return { 'ok': False, 'err': errors }
    elif device == "EGM5":
        if len(gases) != 1:
            errors.append("EGM5 currently only supports co2")
            return { 'ok': False, 'err': errors }
        if gases[0] != "co2":
            errors.append("EGM5 currently only supports co2")
            return { 'ok': False, 'err': errors }
    elif device == "EGM4":
        if len(gases) != 1:
            errors.append("EGM4 currently only supports co2")
            return { 'ok': False, 'err': errors }
        if gases[0] != "co2":
            errors.append("EGM4 currently only supports co2")
            return { 'ok': False, 'err': errors }

    return { 'ok': True }
