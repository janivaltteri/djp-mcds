from django import forms

from django.contrib.auth.models import User

from .models import maxlengths, Dataspec, DataspecAssignment

YEARS = [x for x in range(2021,2026)]

class ProjectForm(forms.Form):
    name = forms.CharField(label='name',
                           max_length=maxlengths['project_name'])
    contact_name = forms.CharField(label='contact_name',
                                   max_length=maxlengths['project_contact_name'])
    contact_email = forms.CharField(label='contact_email',
                                    max_length=maxlengths['project_contact_email'])

class AssignworkerForm(forms.Form):
    worker = forms.ModelChoiceField(queryset=User.objects.all())

class DataspecForm(forms.Form):
    name = forms.CharField(label='Dataspec name', max_length=maxlengths['dataspec_name'])
    jsonfile = forms.FileField(label='Dataspec JSON file')

class AssigndataspecForm(forms.Form):
    dataspec = forms.ModelChoiceField(queryset=Dataspec.objects.filter(active=True).all())

class MeasurementsForm(forms.Form):

    def __init__(self, *args, **kwargs):
        pid = kwargs.pop('pid')
        super(MeasurementsForm, self).__init__(*args, **kwargs)
        self.fields['dataspec'].queryset = DataspecAssignment.objects.filter(project=pid).filter(active=True).all()
    
    measure_date = forms.DateField(label='Measurement date', initial="2023-01-01",
                                   widget=forms.SelectDateWidget(years=YEARS))
    datafile     = forms.FileField(label='Data file')
    fieldform    = forms.FileField(label='Field form')
    dataspec     = forms.ModelChoiceField(label='Specification',queryset=DataspecAssignment.objects.none())
    comment      = forms.CharField(label='Comment', max_length=128)
