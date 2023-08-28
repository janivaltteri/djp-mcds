from datetime import datetime

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

maxlengths = {
    'project_name': 64,
    'project_contact_name': 64,
    'project_contact_email': 64,
    'dataspec_name': 128,
    'dataspec_file': 128,
    'series_siteid': 64
}

class Project(models.Model):
    name          = models.CharField(max_length=maxlengths['project_name'],unique=True)
    contact_name  = models.CharField(max_length=maxlengths['project_contact_name'])
    contact_email = models.CharField(max_length=maxlengths['project_contact_email'])
    author        = models.ForeignKey(User, on_delete=models.PROTECT,
                                      related_name='authored_projects')
    date          = models.DateTimeField(default=timezone.now)
    active        = models.BooleanField(default=True)

    def __str__(self):
        return '<Project {}>'.format(self.name)

class WorkerAssignment(models.Model):
    worker  = models.ForeignKey(User, on_delete=models.PROTECT,
                                related_name='assignments')
    project = models.ForeignKey(Project, on_delete=models.PROTECT,
                                related_name='assigned_workers')
    author  = models.ForeignKey(User, on_delete=models.PROTECT,
                                related_name='authored_workerassignments')
    date    = models.DateTimeField(default=timezone.now)
    active  = models.BooleanField(default=True)

class Dataspec(models.Model):
    name   = models.CharField(max_length=maxlengths['dataspec_name'],unique=True)
    author = models.ForeignKey(User, on_delete=models.PROTECT,
                               related_name='authored_dataspecs')
    file   = models.FileField(upload_to='dataspecs/',
                              max_length=maxlengths['dataspec_file'],
                              unique=True)
    spec   = models.JSONField()
    date   = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)

    def __str__(self):
        return '{}'.format(self.name)

class DataspecAssignment(models.Model):
    dataspec = models.ForeignKey(Dataspec, on_delete=models.PROTECT,
                                 related_name='assignments')
    project  = models.ForeignKey(Project, on_delete=models.PROTECT,
                                 related_name='assigned_dataspecs')
    author   = models.ForeignKey(User, on_delete=models.PROTECT,
                                 related_name='authored_dataspecassignments')
    date     = models.DateTimeField(default=timezone.now)
    active   = models.BooleanField(default=True)

    def __str__(self):
        return '{}'.format(self.dataspec.name)

class Measurements(models.Model):
    MEAS_STATUS_CHOICES = (
        ('submitted','Submitted'),
        ('accepted','Accepted'),
        ('retracted','Retracted'),
    )
    FILE_STATUS_CHOICES = (
        ('undetermined','Undetermined'),
        ('valid','Valid'),
        ('invalid','Invalid'),
    )
    measurer      = models.ForeignKey(User, on_delete=models.PROTECT, blank=False,
                                      null=False, related_name='submissions')
    project       = models.ForeignKey(Project, on_delete=models.PROTECT, blank=False,
                                      null=False, related_name='submissions')
    dataspec      = models.ForeignKey(Dataspec, on_delete=models.PROTECT, blank=False,
                                      null=False, related_name='submissions')
    date          = models.DateTimeField(default=datetime.utcnow)
    measure_date  = models.DateField()
    status        = models.CharField(max_length=16, choices=MEAS_STATUS_CHOICES,
                                     default='submitted')
    comment       = models.CharField(max_length=256, blank=True, null=True)
    datastatus    = models.CharField(max_length=16, choices=FILE_STATUS_CHOICES,
                                     default='undetermined')
    datafile      = models.FileField(upload_to='datafiles/',
                                     max_length=128, unique=True)
    dataorigname  = models.CharField(max_length=128)
    fieldstatus   = models.CharField(max_length=16, choices=FILE_STATUS_CHOICES,
                                     default='undetermined')
    fieldform     = models.FileField(upload_to='fieldforms/',
                                     max_length=128, unique=True)
    fieldorigname = models.CharField(max_length=128)
    siteids       = models.CharField(max_length=256,default='')
    errors        = models.CharField(max_length=256,default='')
    processed     = models.BooleanField(default=False)
    valid         = models.BooleanField(default=True)

class Series(models.Model):
    measurements = models.ForeignKey(Measurements, on_delete=models.PROTECT,
                                     blank=False, null=False)
    date       = models.DateField()
    siteid     = models.CharField(max_length=maxlengths['series_siteid'])
    subsiteid  = models.CharField(max_length=64)
    point      = models.CharField(max_length=64)
    gas        = models.CharField(max_length=12)
    start_time = models.TimeField()
    end_time   = models.TimeField()
    start_temp = models.FloatField()
    end_temp   = models.FloatField()
    unit       = models.CharField(max_length=16)
    env        = models.JSONField()
    volume     = models.FloatField()
    area       = models.FloatField()
    pad_head   = models.IntegerField()
    pad_tail   = models.IntegerField()
    values     = ArrayField(models.FloatField())
    valid      = models.BooleanField(default=True)

    def __str__(self):
        return '{}'.format(self.start_time)

class Flux(models.Model):
    series    = models.ForeignKey(Series, on_delete=models.PROTECT,
                                  blank=False, null=False)
    trimmer   = models.ForeignKey(User, on_delete=models.PROTECT,
                                  blank=False, null=False)
    datetime  = models.DateField(default=datetime.utcnow)
    trim_head = models.IntegerField(default=0)
    trim_tail = models.IntegerField(default=0)
    slope     = models.FloatField()
    intercept = models.FloatField()
    flux      = models.FloatField()
    resid     = models.FloatField()
    bad       = models.BooleanField(default=False)

class Download(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, blank=False,
                                null=False, related_name='downloads')
    datetime = models.DateTimeField(default=datetime.utcnow)
    user     = models.ForeignKey(User, on_delete=models.PROTECT,
                                 blank=False, null=False)
    file     = models.CharField(max_length=128, null=True, blank=True)
    ready    = models.BooleanField(default=False)
    expired  = models.BooleanField(default=False)
