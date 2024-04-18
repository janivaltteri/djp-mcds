import json
import numpy
import datetime

from django.shortcuts import render
from django.template import loader
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, FileResponse

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

from django.forms.models import model_to_dict

from scipy.stats import linregress

from .datareaders import (
    read_fieldform,
    get_series_data_from_ff,
    read_df_licor,
    validate_dataspec
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

from .forms import (
    ProjectForm, AssignworkerForm, DataspecForm, AssigndataspecForm, MeasurementsForm
)

from .tasks import (
    test_task, process_dataset, make_download
)

from .fluxcalc import (
    calculate_flux_value, get_interval_for_series, FluxCalcException
)

def index(request):
    template = loader.get_template('mcds/index.html')
    context = { 'a': 3 }
    return HttpResponse(template.render(context, request))

@login_required
def main(request):
    current_user = request.user
    uid: int     = current_user.id
    uname: str   = current_user.username
    template = loader.get_template('mcds/main.html')
    projects = Project.objects.all().order_by('-active','-date')
    dataspecs = Dataspec.objects.all().order_by('-active','-date')
    assigned = WorkerAssignment.objects.filter(worker=uid,active=True).all().order_by('-date')
    context  = { 'uname': uname,
                 'projects': projects,
                 'dataspecs': dataspecs,
                 'assigned': assigned }
    return HttpResponse(template.render(context, request))

@login_required
def createproject(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            current_user = request.user
            userid: int  = current_user.id
            uobj = User.objects.get(pk=userid)
            pname: str = request.POST.get("name")
            pcname: str = request.POST.get("contact_name")
            pcemail: str = request.POST.get("contact_email")
            prjs = Project.objects.filter(name=pname).all()
            if len(prjs) == 0:
                newproj = Project(author = uobj,
                                  name = pname,
                                  contact_name = pcname,
                                  contact_email = pcemail)
                newproj.save()
                msg = 'Project ' + pname + ' created'
            else:
                msg = 'Project with name ' + pname + ' already exists!'
            messages.info(request,msg)
            return HttpResponseRedirect('/mcds/createproject/')
        else:
            msg = 'Project creation form invalid!'
            messages.info(request,msg)
            return HttpResponseRedirect('/mcds/createproject/')
    else:
        form = ProjectForm()
        context = { 'form': form }
        template = loader.get_template('mcds/createproject.html')
        return HttpResponse(template.render(context, request))

@login_required
def manageproject(request,project_name):
    project = Project.objects.get(name=project_name)
    workers = WorkerAssignment.objects.filter(project=project.id).all()
    dataspecs = DataspecAssignment.objects.filter(project=project.id).all()
    context = { 'project': project, 'workers': workers, 'dataspecs': dataspecs }
    template = loader.get_template('mcds/manageproject.html')
    return HttpResponse(template.render(context, request))

## switches between active = True and active = False
@login_required
def deactivateproject(request,project_name):
    project = Project.objects.get(name=project_name)
    if project.active:
        project.active = False
        project.save()
        msg = "Project " + project_name + " deactivated"
    else:
        project.active = True
        project.save()
        msg = "Project " + project_name + " activated"
    messages.info(request,msg)
    route = '/mcds/manageproject/' + project_name
    return HttpResponseRedirect(route)

@login_required
def downloadoriginaldf(request,project_name,meas_id):
    meas = Measurements.objects.get(pk=meas_id)
    file = meas.datafile
    return FileResponse(file)

@login_required
def downloadoriginalff(request,project_name,meas_id):
    meas = Measurements.objects.get(pk=meas_id)
    file = meas.fieldform
    return FileResponse(file)

@login_required
def assignworker(request,project_name):
    project = Project.objects.get(name=project_name)
    if request.method == 'POST':
        form = AssignworkerForm(request.POST)
        if form.is_valid():
            current_user = request.user
            userid: int  = current_user.id
            uobj = User.objects.get(pk=userid)
            workerid = request.POST.get("worker")
            wobj = User.objects.get(pk=workerid)
            pobj = Project.objects.get(pk=project.id)
            aw = WorkerAssignment.objects.filter(project=project.id,
                                                 worker=workerid,
                                                 active=True).all()
            if len(aw) == 0:
                newass = WorkerAssignment(worker = wobj,
                                          project = pobj,
                                          author = uobj)
                newass.save()
                msg = 'Assigned ' + str(wobj.username) + ' to ' + str(pobj.name)
            else:
                msg = 'Assignment ' + str(wobj.username) + ' to ' + str(pobj.name) + \
                    ' already exists and is active!'
            messages.info(request,msg)
            route = '/mcds/manageproject/' + project_name
            return HttpResponseRedirect(route)
        else:
            messages.info(request,'Error')
            route = '/mcds/manageproject/' + project_name
            return HttpResponseRedirect(route)
    else:
        form = AssignworkerForm()
        context = { 'form': form, 'project': project }
        template = loader.get_template('mcds/assignworker.html')
        return HttpResponse(template.render(context, request))

@login_required
def removeworker(request,project_name,workerassignment_id):
    assignment = WorkerAssignment.objects.get(pk=workerassignment_id)
    if assignment.active:
        assignment.active = False
        assignment.save()
        msg = 'Assignment ' + str(assignment.id) + ' (' + str(assignment.worker) + \
            ' to ' + project_name + ') deactivated'
    else:
        msg = 'Assignment ' + str(assignment.id) + ' (' + str(assignment.worker) + \
            ' to ' + project_name + ') is not active!'
    messages.info(request,msg)
    route = '/mcds/manageproject/' + project_name
    return HttpResponseRedirect(route)

@login_required
def uploaddataspec(request):
    if request.method == 'POST':
        form = DataspecForm(request.POST,request.FILES)

        if form.is_valid():
            current_user = request.user
            userid: int  = current_user.id
            uobj = User.objects.get(pk=userid)
            dsname: str = request.POST.get("name")
            dsfile = request.FILES['jsonfile']

            try:
                dsstring = request.FILES.get('jsonfile').read()
            except Exception as e:
                msg = 'Error reading file: ' + str(e)
                messages.info(request,msg)
                return HttpResponseRedirect('/mcds/uploaddataspec/')

            try:
                dsspec = json.loads(dsstring)
            except Exception as e:
                msg = 'Error parsing json: ' + str(e)
                messages.info(request,msg)
                return HttpResponseRedirect('/mcds/uploaddataspec/')

            ds_valid = validate_dataspec(dsspec)

            if ds_valid.get('ok'):
                newdataspec = Dataspec(author = uobj,
                                       name = dsname,
                                       file = dsfile,
                                       spec = dsspec)
                newdataspec.save()
                msg = 'Uploaded dataspec: ' + dsname
                messages.info(request,msg)
                return HttpResponseRedirect('/mcds/main/')

            else:
                msg = "Errors validating dataspec: " + " ".join(ds_valid.get("err"))
                messages.info(request,msg)
                return HttpResponseRedirect('/mcds/uploaddataspec/')

        else:
            errorlist = []
            for field in form:
                if field.errors:
                    errorlist.append(field.errors)
            msg = "Errors validating form: " + " ".join(errorlist)
            messages.info(request,msg)
            return HttpResponseRedirect('/mcds/uploaddataspec/')
    else:
        form = DataspecForm()
        context = { 'form': form }
        template = loader.get_template('mcds/uploaddataspec.html')
        return HttpResponse(template.render(context, request))

@login_required
def viewdataspec(request,dataspec_id):
    dataspec = Dataspec.objects.get(pk=dataspec_id)
    context = { 'dataspec': dataspec }
    template = loader.get_template('mcds/viewdataspec.html')
    return HttpResponse(template.render(context, request))

@login_required
def assigndataspec(request,project_name):
    project = Project.objects.get(name=project_name)
    if request.method == 'POST':
        form = AssigndataspecForm(request.POST)
        if form.is_valid():
            current_user = request.user
            userid: int  = current_user.id
            uobj = User.objects.get(pk=userid)
            dataspecid = request.POST.get("dataspec")
            dsobj = Dataspec.objects.get(pk=dataspecid)
            pobj = Project.objects.get(pk=project.id)
            ads = DataspecAssignment.objects.filter(project=project.id,
                                                    dataspec=dataspecid,
                                                    active=True).all()
            if len(ads) == 0:
                newass = DataspecAssignment(dataspec = dsobj,
                                            project = pobj,
                                            author = uobj)
                newass.save()
                msg = 'Assigned ' + str(dsobj.name) + ' to ' + str(pobj.name)
            else:
                msg = 'Assignment ' + str(dsobj.name) + ' to ' + str(pobj.name) + \
                    ' already exists and is active!'
            messages.info(request,msg)
            route = '/mcds/manageproject/' + project_name
            return HttpResponseRedirect(route)
        else:
            messages.info(request,'Error: form not valid')
            route = '/mcds/manageproject/' + project_name
            return HttpResponseRedirect(route)
    else:
        form = AssigndataspecForm()
        context = { 'form': form, 'project': project }
        template = loader.get_template('mcds/assigndataspec.html')
        return HttpResponse(template.render(context, request))

@login_required
def removedataspec(request,project_name,dataspecassignment_id):
    assignment = DataspecAssignment.objects.get(pk=dataspecassignment_id)
    if assignment.active:
        assignment.active = False
        assignment.save()
        msg = 'Assignment ' + str(assignment.id) + ' (' + str(assignment.dataspec) + \
            ' to ' + project_name + ') removed'
    else:
        msg = 'Error: Assignment ' + str(assignment.id) + ' (' + str(assignment.dataspec) + \
            ' to ' + project_name + ') is not active'
    messages.info(request,msg)
    route = '/mcds/manageproject/' + project_name
    return HttpResponseRedirect(route)

## switches between active = True and active = False
@login_required
def deactivatedataspec(request,dataspec_id):
    dataspec = Dataspec.objects.get(pk=dataspec_id)
    if dataspec.active:
        dataspec.active = False
        dataspec.save()
        msg = 'Dataspec ' + str(dataspec.id) + ' deactivated'
    else:
        dataspec.active = True
        dataspec.save()
        msg = 'Dataspec ' + str(dataspec.id) + ' activated'
    messages.info(request,msg)
    route = '/mcds/viewdataspec/' + str(dataspec.id)
    return HttpResponseRedirect(route)

@login_required
def viewprojectdata(request, project_name):
    current_user = request.user
    userid: int  = current_user.id
    project      = Project.objects.get(name=project_name)
    measurements = Measurements.objects.filter(project=project).all()
    context      = { 'project': project, 'measurements': measurements }
    template     = loader.get_template('mcds/viewprojectdata.html')
    return HttpResponse(template.render(context, request))

@login_required
def viewpointdata(request, project_name, meas_id):
    project  = Project.objects.get(name=project_name)
    meas     = Measurements.objects.get(pk=meas_id)
    dspec    = Dataspec.objects.get(pk=meas.dataspec.id)
    context  = { 'project': project, 'meas': meas, 'dspec': dspec,
                 'interval': dspec.spec.get("datafile").get("interval"),
                 'xpad': dspec.spec.get("durations").get("pad") }
    template = loader.get_template('mcds/viewpointdata.html')
    return HttpResponse(template.render(context, request))

@login_required
def uploadmeasurements(request, project_name):
    current_user = request.user
    userid: int  = current_user.id
    project      = Project.objects.get(name=project_name)
    if request.method == 'POST':
        form = MeasurementsForm(request.POST,request.FILES,pid=project.id)
        if form.is_valid():
            if request.FILES['datafile'].size > 6000000:
                messages.info(request,'Upload failed, datafile size must be under 6 MB')
                route = '/mcds/uploadmeasurements/' + project_name
                return HttpResponseRedirect(route)
            if request.FILES['fieldform'].size > 6000000:
                messages.info(request,'Upload failed, fieldform size must be under 6 MB')
                route = '/mcds/uploadmeasurements/' + project_name
                return HttpResponseRedirect(route)

            uobj          = User.objects.get(pk=userid)
            pobj          = Project.objects.get(name=project_name)
            md_year: str  = request.POST.get("measure_date_year")
            md_month: str = request.POST.get("measure_date_month")
            md_day: str   = request.POST.get("measure_date_day")
            measdate      = datetime.date(int(md_year), int(md_month), int(md_day))
            comment: str  = request.POST.get("comment", "")

            datafilename  = request.FILES['datafile'].name
            fieldformname = request.FILES['fieldform'].name
            datafile      = request.FILES['datafile']
            fieldform     = request.FILES['fieldform']

            ds_ass_id     = request.POST.get("dataspec")
            ds_ass_obj    = DataspecAssignment.objects.get(pk=ds_ass_id)
            dsobj         = Dataspec.objects.get(pk=ds_ass_obj.dataspec.id)

            accepted_datafile_exts = ['.txt','.TXT','.dat','.DAT','data','DATA',
                                      '.csv','.CSV','text','TEXT']
            accepted_fieldform_exts = ['xlsx','.csv','.CSV']
            if fieldformname[-4:] not in accepted_fieldform_exts:
                messages.info(request, 'Field form file extension must be .xlsx or .csv')
                route = '/mcds/uploadmeasurements/' + project_name
                return HttpResponseRedirect(route)
            if datafilename[-4:] not in accepted_datafile_exts:
                messages.info(request,
                              'Datafile extension must be one of {0}'
                              .format(" ".join(accepted_datafile_exts)))
                route = '/mcds/uploadmeasurements/' + project_name
                return HttpResponseRedirect(route)

            newmeas = Measurements(measurer      = uobj,
                                   project       = pobj,
                                   dataspec      = dsobj,
                                   measure_date  = measdate,
                                   comment       = comment,
                                   datafile      = datafile,
                                   fieldform     = fieldform,
                                   dataorigname  = datafilename,
                                   fieldorigname = fieldformname)
            newmeas.save()

            msg = 'Uploaded Measurements!'
            messages.info(request,msg)
            route = '/mcds/uploadmeasurements/' + project_name
            return HttpResponseRedirect(route)
        else:
            for field in form:
                print("Field Error:", field.name,  field.errors)
            messages.info(request,'Error: form not valid')
            route = '/mcds/uploadmeasurements/' + project_name
            return HttpResponseRedirect(route)
    else:
        form = MeasurementsForm(pid=project.id)
        uploads = Measurements.objects.filter(measurer=userid,project=project).order_by("date").all()
        context = { 'form': form, 'project': project, 'uploads': uploads }
        template = loader.get_template('mcds/uploadmeasurements.html')
        return HttpResponse(template.render(context, request))

@login_required
def checkmeasurements(request,project_name,meas_id):
    current_user = request.user
    userid: int  = current_user.id
    project      = Project.objects.get(name=project_name)
    meas         = Measurements.objects.get(pk=meas_id)
    dspec        = Dataspec.objects.get(pk=meas.dataspec.id)
    process_dataset.delay(meas_id)
    context      = { 'project': project, 'meas': meas, 'dspec': dspec }
    template     = loader.get_template('mcds/checkmeasurements.html')
    return HttpResponse(template.render(context, request))

@login_required
def removemeasurements(request,project_name,meas_id):
    meas = Measurements.objects.get(pk=meas_id)
    if meas.status == 'submitted':
        series = Series.objects.filter(measurements=meas).all()
        for s in series:
            fluxes = Flux.objects.filter(series=s).all()
            for f in fluxes:
                f.delete()
            s.delete()
        meas.datafile.delete()
        meas.fieldform.delete()
        meas.delete()
        messages.info(request,'Removed Measurements ' + str(meas_id))
    elif meas.status == 'accepted':
        messages.info(request,'Accepted measurements cannot be removed')
    elif meas.status == 'retracted':
        messages.info(request,'Retracted measurements cannot be removed')
    route = '/mcds/uploadmeasurements/' + project_name
    return HttpResponseRedirect(route)

@login_required
def acceptmeasurements(request,project_name,meas_id):
    meas = Measurements.objects.get(pk=meas_id)
    if meas.status == 'accepted':
        messages.info(request,'Already accepted')
    else:
        if not meas.valid:
            messages.info(request,'Measurement set has not passed validation')
        elif meas.fieldstatus != 'valid':
            messages.info(request,'Field form has not passed validation')
        elif meas.datastatus != 'valid':
            messages.info(request,'Data file has not passed validation')
        else:
            meas.status = 'accepted'
            meas.save()
            messages.info(request,'Measurement set ' + str(meas.id) + ' accepted')
    route = '/mcds/checkmeasurements/' + project_name + '/' + str(meas.id)
    return HttpResponseRedirect(route)

@login_required
def retractmeasurements(request,project_name,meas_id):
    meas = Measurements.objects.get(pk=meas_id)
    if meas.status == 'accepted':
        meas.status = 'retracted'
        meas.save()
        messages.info(request,'Measurement set ' + str(meas.id) + ' retracted')
    else:
        messages.info(request,'Only accepted measurements can be retracted')
    route = '/mcds/checkmeasurements/' + project_name + '/' + str(meas.id)
    return HttpResponseRedirect(route)

## used by checkmeasurements.html fetch_data() to fill the table with data
## after processed status (from get_processing_status) is changed to yes
@login_required
def checksubmission(request,meas_id):
    meas = Measurements.objects.get(pk=meas_id)
    if meas.processed:
        series = Series.objects.filter(measurements=meas).all()
        data = []
        for s in series:
            starttime = s.start_time
            endtime = s.end_time
            st0 = datetime.datetime.combine(datetime.date.today(), starttime)
            et0 = datetime.datetime.combine(datetime.date.today(), endtime)
            duration = (et0 - st0).total_seconds()
            data.append({ 'date':       s.date,
                          'siteid':     s.siteid,
                          'subsiteid':  s.subsiteid,
                          'point':      s.point,
                          'start_time': starttime,
                          'end_time':   endtime,
                          'start_temp': s.start_temp,
                          'end_temp':   s.end_temp,
                          'duration':   duration,
                          'area':       s.area,
                          'volume':     s.volume,
                          'unit':       s.unit,
                          'gas':        s.gas,
                          'env':        s.env,
                          'values':     s.values,
                          'valid':      s.valid })
        dspec = Dataspec.objects.get(pk=meas.dataspec.id)
        ff    = read_fieldform(dspec.spec,meas.fieldform,False,True)
        meas_dict = { 'valid': str(meas.valid),
                      'status': meas.status,
                      'fieldstatus': meas.fieldstatus,
                      'datastatus': meas.datastatus,
                      'errors': meas.errors }
        out   = { 'ffok': ff['ok'], 'fferr': ff['err'], 'ffwarn': ff['warn'],
                  'meas': meas_dict, 'data': data, 'from': 'database' }
    else:
        print("checksubmission: not processed, should not happen")
        dspec = Dataspec.objects.get(pk=meas.dataspec.id)
        ff    = read_fieldform(dspec.spec,meas.fieldform,True,True)
        ##df    = read_df_licor(meas.datafile,True)
        ##data  = get_series_data_from_ff(df['df'],ff['df'],dspec.spec)
        out   = { 'ffok': ff['ok'], 'fferr': ff['err'], 'ffwarn': ff['warn'],
                  'msg': "checksubmission: not processed, should not happen" }
        ##out   = { 'ffok': ff['ok'], 'fferr': ff['err'], 'ffwarn': ff['warn'],
        ##          'data': data, 'from': 'reader' }
    return JsonResponse(out)

## is this used? the tasks.py version is used
@login_required
def test_process(request,project_name,meas_id):
    meas = Measurements.objects.get(pk=meas_id)
    if meas.processed:
        print('already processed')
        out = { 'processed': meas.processed }
        messages.info(request,'already processed')
        route = '/mcds/checkmeasurements/' + project_name + '/' + str(meas_id)
        return HttpResponseRedirect(route)
    else:
        print('processing now')
        dspec  = Dataspec.objects.get(pk=meas.dataspec.id)
        ff     = read_fieldform(dspec.spec,meas.fieldform,True,True)
        spec   = dspec.spec
        device = spec.get("datafile").get("device")

        if device == "LI-COR":
            df = read_df_licor(spec,meas.datafile,True)

        data = get_series_data_from_ff(df['df'],ff['df'],dspec.spec)

        for i in range(len(data)):
            dv = data[i]
            is_valid = len(dv.get('values')) >= 30
            newseries = Series(measurements = meas,
                               date       = dv.get('date'),
                               siteid     = dv.get('siteid'),
                               subsiteid  = dv.get('subsiteid'),
                               point      = dv.get('point'),
                               start_time = dv.get('start_time'),
                               end_time   = dv.get('end_time'),
                               gas        = dv.get('gas'),
                               unit       = dv.get('unit'),
                               env        = dv.get('env'),
                               pad_head   = dv.get('pad_head'),
                               pad_tail   = dv.get('pad_tail'),
                               trim_head  = dv.get('pad_head'),
                               trim_tail  = dv.get('pad_tail'),
                               values     = dv.get('values'),
                               valid      = is_valid)
            newseries.save()
        meas.processed = True
        meas.save()
        messages.info(request,'processed')
        route = '/mcds/checkmeasurements/' + project_name + '/' + str(meas_id)
        return HttpResponseRedirect(route)

def test_unprocess(request,project_name,meas_id):
    meas = Measurements.objects.get(pk=meas_id)
    if meas.processed:
        print('unprocessing')
        series = Series.objects.filter(measurements=meas).all()
        for s in series:
            fluxes = Flux.objects.filter(series=s).all()
            for f in fluxes:
                f.delete()
            s.delete()
        meas.fieldstatus = "undetermined"
        meas.datastatus = "undetermined"
        meas.processed = False
        meas.errors = ""
        meas.save()
        messages.info(request,"unprocessed " + str(meas.id))
        route = '/mcds/uploadmeasurements/' + project_name
        return HttpResponseRedirect(route)
    else:
        print('already unprocessed')
        series = Series.objects.filter(measurements=meas).all()
        if len(series) > 0:
            print('warning: but contains series')
            for s in series:
                fluxes = Flux.objects.filter(series=s).all()
                for f in fluxes:
                    f.delete()
                s.delete()
        out = { 'processed': meas.processed }
        messages.info(request,'already unprocessed')
        route = '/mcds/uploadmeasurements/' + project_name
        return HttpResponseRedirect(route)

@login_required
def createdownload(request,project_name):
    current_user = request.user
    userid: int  = current_user.id
    user         = User.objects.get(pk=userid)
    project      = Project.objects.get(name=project_name)

    newdownload  = Download(project=project,user=user)
    newdownload.save()

    dl_id = newdownload.id
    newdownload.file = "/opt/djpmcds/files/downloads/" + \
        project_name + "-" + str(dl_id) + ".csv"
    newdownload.save()

    make_download.delay(project_name,userid,dl_id)

    route = '/mcds/downloads/' + project_name + '/' + str(dl_id)
    return HttpResponseRedirect(route)

@login_required
def downloads(request,project_name,download_id):
    project  = Project.objects.get(name=project_name)
    download = Download.objects.get(pk=download_id)

    meas = Measurements.objects.filter(project=project).all()
    series_count = 0
    for m in meas:
        series = Series.objects.filter(measurements=m).all()
        series_count += len(series)

    context  = { 'project': project, 'download': download,
                 'meas_count': len(meas), 'series_count': series_count }

    template = loader.get_template('mcds/downloads.html')
    return HttpResponse(template.render(context, request))

@login_required
def downloaddatafile(request,download_id):
    download = Download.objects.get(pk=download_id)
    file = download.file
    resp = FileResponse(open(file,'rb'))
    return resp

## is this used?
@login_required
def calculate_flux(request,series_id):
    current_user = request.user
    userid: int  = current_user.id
    user         = User.objects.get(pk=userid)
    series       = Series.objects.get(pk=series_id)
    pflux        = Flux.objects.filter(series=series,trimmer=user).all()
    interval     = get_interval_for_series(series)

    flux = {}
    if len(pflux) == 0:
        try:
            flux = calculate_flux_value(series,interval)
        except Exception as e:
            flux['status'] = 'error, could not calculate flux: ' + str(e)
        else:
            newflux = Flux(series    = series,
                           trimmer   = user,
                           slope     = flux['slope'],
                           trim_head = flux['trim_head'],
                           trim_tail = flux['trim_tail'],
                           intercept = flux['intercept'],
                           flux      = flux['lflux'],
                           resid     = flux['resid'],
                           bad       = False)
            newflux.save()
            flux['status'] = 'ok'

    elif len(pflux) == 1:
        flux['status'] = 'error, flux already exists'

    elif len(pflux) > 1:
        flux['status'] = 'error, multiple existing fluxes'

    else:
        flux['status'] = 'error, existing fluxes: ' + str(len(pflux))

    return JsonResponse(flux)

def remove_flux(request,series_id):
    current_user = request.user
    userid: int  = current_user.id
    user         = User.objects.get(pk=userid)
    series       = Series.objects.get(pk=series_id)
    pflux        = Flux.objects.filter(series=series,trimmer=user).all()
    out          = {}
    if len(pflux) > 1:
        out['status'] = 'error, multiple existing fluxes, removed'
        for i in range(len(pflux)):
            pflux[i].delete()
    elif len(pflux) == 1:
        out['status'] = 'ok, removed'
        pflux[0].delete()
    else:
        out['status'] = 'error, no flux'
    return JsonResponse(out)

def trim_flux(request):
    flux = {}
    if request.method == 'POST':

        data = json.loads(request.body.decode('UTF-8'))
        r_series_id = data.get('series_id')
        r_trim_head = data.get('trim_head')
        r_trim_tail = data.get('trim_tail')
        print("trimming " + str(r_series_id) + " head " +
              str(r_trim_head) + " tail " + str(r_trim_tail))

        current_user = request.user
        userid: int  = current_user.id
        user         = User.objects.get(pk=userid)
        series       = Series.objects.get(pk=r_series_id)
        pflux        = Flux.objects.filter(series=series,trimmer=user).all()
        interval     = get_interval_for_series(series)

        if len(pflux) > 1:
            flux['status'] = 'error, multiple existing fluxes'

        elif len(pflux) < 1:
            flux['status'] = 'error, flux does not exist'

        else:
            pf = pflux[0]
            try:
                flux = calculate_flux_value(series,interval,r_trim_head,r_trim_tail)
            except Exception as e:
                flux['trim_head'] = pf.trim_head
                flux['trim_tail'] = pf.trim_tail
                flux['slope']     = pf.slope
                flux['intercept'] = pf.intercept
                flux['lflux']     = pf.flux
                flux['resid']     = pf.resid
                flux['pad_head']  = series.pad_head
                flux['pad_tail']  = series.pad_tail
                flux['status']    = 'error: ' + str(e)
            else:
                pf.trim_head = flux['trim_head']
                pf.trim_tail = flux['trim_tail']
                pf.slope     = flux['slope']
                pf.intercept = flux['intercept']
                pf.flux      = flux['lflux']
                pf.resid     = flux['resid']
                pf.save()
                flux['pad_head'] = series.pad_head
                flux['pad_tail'] = series.pad_tail
                flux['status'] = 'ok'
    else:
        flux['status'] = "error, received GET instead of POST"

    return JsonResponse(flux)

def mark_flux_bad(request,series_id):
    current_user = request.user
    userid: int  = current_user.id
    user         = User.objects.get(pk=userid)
    series       = Series.objects.get(pk=series_id)
    pflux        = Flux.objects.filter(series=series,trimmer=user).all()
    out          = {}
    if len(pflux) > 1:
        out['status'] = 'error, multiple existing fluxes'
    elif len(pflux) == 1:
        if pflux[0].bad:
            out['status'] = 'error, flux already marked bad'
        else:
            pflux[0].bad = True
            pflux[0].save()
            out = model_to_dict(pflux[0])
            out['status'] = 'ok, marking existing flux bad'
    else:
        out['status'] = 'ok, creating new flux and marking it bad'
        newflux = Flux(series    = series,
                       trimmer   = user,
                       slope     = 0.0,
                       intercept = 0.0,
                       flux      = 0.0,
                       resid     = 0.0,
                       bad       = True)
        newflux.save()
    return JsonResponse(out)

def mark_flux_good(request,series_id):
    current_user = request.user
    userid: int  = current_user.id
    user         = User.objects.get(pk=userid)
    series       = Series.objects.get(pk=series_id)
    pflux        = Flux.objects.filter(series=series,trimmer=user).all()
    interval     = get_interval_for_series(series)

    out          = {}

    if len(pflux) > 1:
        out['status'] = 'error, multiple existing fluxes'

    elif len(pflux) == 1:
        if pflux[0].bad:
            pflux[0].bad = False
            pflux[0].save()
            out = model_to_dict(pflux[0])
            out['status'] = 'ok, marking existing flux good'
        else:
            out['status'] = 'error, flux already marked good'

    else:
        try:
            flux = calculate_flux_value(series,interval)
        except Exception as e:
            out['status'] = 'error: ' + str(e)
        else:
            newflux = Flux(series    = series,
                           trimmer   = user,
                           slope     = flux['slope'],
                           trim_head = flux['trim_head'],
                           trim_tail = flux['trim_tail'],
                           intercept = flux['intercept'],
                           flux      = flux['lflux'],
                           resid     = flux['resid'],
                           bad       = False)
            newflux.save()
            out = model_to_dict(newflux)
            out['status'] = 'ok, creating new flux and marking it good'

    return JsonResponse(out)

## called from viewpointdata
def get_series_data(request,meas_id):
    current_user = request.user
    userid: int  = current_user.id
    user = User.objects.get(pk=userid)

    autousers = User.objects.filter(username="autotrimmer").all()
    autouser  = autousers[0] ## todo: handle case user does not exist

    meas = Measurements.objects.get(pk=meas_id)
    dataspec = meas.dataspec
    interval = float(dataspec.spec.get("datafile").get("interval"))

    if meas.processed:
        series = Series.objects.filter(measurements=meas).all()
        data = []
        for s in series:
            obj = { 'id':         s.id,
                    'date':       s.date,
                    'siteid':     s.siteid,
                    'subsiteid':  s.subsiteid,
                    'point':      s.point,
                    'start_time': s.start_time,
                    'end_time':   s.end_time,
                    'unit':       s.unit,
                    'gas':        s.gas,
                    'pad_head':   s.pad_head,
                    'pad_tail':   s.pad_tail,
                    'env':        s.env,
                    'values':     s.values,
                    'volume':     s.volume,
                    'area':       s.area,
                    'valid':      s.valid,
                    'interval':   interval }

            ## todo: additionally, get pfluxes from all users, use newest
            pflux = Flux.objects.filter(series=s,trimmer=user).all()
            if len(pflux) == 0:
                obj['pflux'] = 'none'
            elif len(pflux) == 1:
                obj['pflux'] = model_to_dict(pflux[0])
            else:
                obj['pflux'] = 'error, multiple pfluxes'

            aflux = Flux.objects.filter(series=s,trimmer=autouser).all()
            if len(aflux) == 0:
                obj['aflux'] = 'none'
            elif len(aflux) == 1:
                obj['aflux'] = model_to_dict(aflux[0])
            else:
                obj['aflux'] = 'error, multiple afluxes'
                
            data.append(obj)
            
        out = { 'data': data }
    else:
        out = { 'data': False }
    return JsonResponse(out)

def get_processing_status(request,meas_id):
    meas = Measurements.objects.get(pk=meas_id)
    if meas.processed:
        out = { 'processed': True }
    else:
        out = { 'processed': False }
    return JsonResponse(out)

def get_download_status(request,download_id):
    download = Download.objects.get(pk=download_id)
    if download.ready:
        out = { 'ready': True }
    else:
        out = { 'ready': False }
    return JsonResponse(out)

def get_fluxes(request,meas_id):
    current_user = request.user
    userid: int  = current_user.id
    user = User.objects.get(pk=userid)

    autousers = User.objects.filter(username="autotrimmer").all()
    autouser  = autousers[0] ## todo: handle case user does not exist
    
    meas = Measurements.objects.get(pk=meas_id)
    series = Series.objects.filter(measurements=meas).all()

    out = []

    for s in series:
        obj = { 'sid': s.id }
        pflux = Flux.objects.filter(series=s,trimmer=user).all()
        if len(pflux) == 0:
            obj['pflux'] = 'none'
        elif len(pflux) == 1:
            obj['pflux'] = model_to_dict(pflux[0])
        else:
            obj['pflux'] = 'error, multiple pfluxes'
        aflux = Flux.objects.filter(series=s,trimmer=autouser).all()
        if len(aflux) == 0:
            obj['aflux'] = 'none'
        elif len(aflux) == 1:
            obj['aflux'] = model_to_dict(aflux[0])
        else:
            obj['aflux'] = 'error, multiple afluxes'
        out.append(obj)

    result = { 'data': out }

    return JsonResponse(result)
