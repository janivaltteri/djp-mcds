from rest_framework import serializers
from .models import Project, WorkerAssignment, Measurements, Series
from django.contrib.auth.models import User

class WorkerAssignmentSerialiser(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.username')
    project_name = serializers.CharField(source='project.name')
    author_name = serializers.CharField(source='author.username')

    class Meta:
        model = WorkerAssignment
        fields = ["id", "worker", "worker_name", "project", "project_name",
                  "author", "author_name", "date", "active"]

class MeasurementsSerialiser(serializers.ModelSerializer):
    measurer_name = serializers.CharField(source='measurer.username')
    project_name = serializers.CharField(source='project.name')

    class Meta:
        model = Measurements
        fields = ["id", "measurer", "measurer_name", "project", "project_name",
                  "date", "measure_date", "status", "comment",
                  "datastatus", "dataorigname", "fieldstatus", "fieldorigname",
                  "siteids", "errors", "processed", "valid"]

class SeriesSerialiser(serializers.ModelSerializer):
    
    class Meta:
        model = Series
        fields = ["id", "measurements", "date", "siteid", "subsiteid", "point", "gas",
                  "start_time", "end_time", "start_temp", "end_temp", "unit", "env",
                  "volume", "area", "pad_head", "pad_tail", "values", "valid"]
