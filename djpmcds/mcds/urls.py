from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('main/', views.main, name='main'),
    path('createproject/', views.createproject, name='createproject'),
    path('manageproject/<str:project_name>',
         views.manageproject, name='manageproject'),
    path('deactivateproject/<str:project_name>',
         views.deactivateproject, name='deactivateproject'),
    path('assignworker/<str:project_name>',
         views.assignworker, name='assignworker'),
    path('removeworker/<str:project_name>/<int:workerassignment_id>',
         views.removeworker, name='removeworker'),
    path('uploaddataspec/',
         views.uploaddataspec, name='uploaddataspec'),
    path('viewdataspec/<int:dataspec_id>',
         views.viewdataspec, name='viewdataspec'),
    path('assigndataspec/<str:project_name>',
         views.assigndataspec, name='assigndataspec'),
    path('removedataspec/<str:project_name>/<int:dataspecassignment_id>',
         views.removedataspec, name='removedataspec'),
    path('deactivatedataspec/<int:dataspec_id>',
         views.deactivatedataspec, name='deactivatedataspec'),
    path('uploadmeasurements/<str:project_name>',
         views.uploadmeasurements, name='uploadmeasurements'),
    path('checkmeasurements/<str:project_name>/<int:meas_id>',
         views.checkmeasurements, name='checkmeasurements'),
    path('removemeasurements/<str:project_name>/<int:meas_id>',
         views.removemeasurements, name='removemeasurements'),
    path('acceptmeasurements/<str:project_name>/<int:meas_id>',
         views.acceptmeasurements, name='acceptmeasurements'),
    path('retractmeasurements/<str:project_name>/<int:meas_id>',
         views.retractmeasurements, name='retractmeasurements'),
    path('downloadoriginaldf/<str:project_name>/<int:meas_id>',
         views.downloadoriginaldf, name='downloadoriginaldf'),
    path('downloadoriginalff/<str:project_name>/<int:meas_id>',
         views.downloadoriginalff, name='downloadoriginalff'),
    path('checksubmission/<int:meas_id>',
         views.checksubmission, name='checksubmission'),
    path('processmeasurements/<str:project_name>/<int:meas_id>',
         views.test_process, name='test_process'),
    path('unprocessmeasurements/<str:project_name>/<int:meas_id>',
         views.test_unprocess, name='test_unprocess'),
    path('get_processing_status/<int:meas_id>',
         views.get_processing_status, name='get_processing_status'),
    path('viewprojectdata/<str:project_name>',
         views.viewprojectdata, name='viewprojectdata'),
    path('viewpointdata/<str:project_name>/<int:meas_id>',
         views.viewpointdata, name='viewpointdata'),
    path('get_series_data/<int:meas_id>',
         views.get_series_data, name='get_series_data'),
    path('get_fluxes/<int:meas_id>',
         views.get_fluxes, name='get_fluxes'),
    path('calculate_flux/<int:series_id>',
         views.calculate_flux, name='calculate_flux'),
    path('remove_flux/<int:series_id>',
         views.remove_flux, name='remove_flux'),
    path('trim_flux/',
         views.trim_flux, name='trim_flux'),
    path('mark_flux_bad/<int:series_id>',
         views.mark_flux_bad, name='mark_flux_bad'),
    path('mark_flux_good/<int:series_id>',
         views.mark_flux_good, name='mark_flux_good'),
    path('createdownload/<str:project_name>',
         views.createdownload, name='createdownload'),
    path('downloads/<str:project_name>/<int:download_id>',
         views.downloads, name='downloads'),
    path('downloaddatafile/<int:download_id>',
         views.downloaddatafile, name='downloaddatafile'),
    path('get_download_status/<int:download_id>',
         views.get_download_status, name='get_download_status'),
    path('api/ping/', views.PingApi.as_view()),
    path('api/workerassignments/', views.WorkerAssignmentApi.as_view()),
    path('api/measurements/<int:project_id>', views.MeasurementsApi.as_view()),
    path('api/series/<int:measurements_id>', views.SeriesApi.as_view()),
    path('api/flux/<int:series_id>', views.FluxApi.as_view()),
    path('api/fluxrecalculate/<int:series_id>', views.FluxRecalculateApi.as_view()),
]
