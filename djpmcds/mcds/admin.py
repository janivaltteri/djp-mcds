from django.contrib import admin
from .models import Project, Dataspec, DataspecAssignment, Download

admin.site.register(Project)
admin.site.register(Dataspec)
admin.site.register(DataspecAssignment)
admin.site.register(Download)
