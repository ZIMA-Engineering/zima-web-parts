from django import forms
from django.forms.widgets import HiddenInput
from django.forms import BaseFormSet, formset_factory
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext as __
from django.db import IntegrityError, transaction
from .models import Directory, PartModel, PartDownload


class PartModelForm(forms.ModelForm):
    class Meta:
        model = PartModel
        fields = ('ds_name', 'dir_path', 'name')
        widgets = {
            'ds_name': HiddenInput(),
            'dir_path': HiddenInput(),
            'name': HiddenInput()
        }
    
    def clean(self):
        data = super(PartModelForm, self).clean()

        self.dir = Directory.from_path(data['ds_name'], data['dir_path'], load=True)

        if not self.dir:
            raise forms.ValidationError('invalid data source or directory')

        self.part = None

        for p in self.dir.parts:
            if p.name == data['name']:
                self.part = p
                break
        else:
            raise forms.ValidationError("part '{}' does not exist".format(data['part']))

        self.instance.part = self.part

        return data

    def save(self, *args, **kwargs):
        # Every part is in the database just once
        try:
            with transaction.atomic():
                super(PartModelForm, self).save(*args, **kwargs)

        except IntegrityError:
            self.instance = PartModel.objects.existing(
                self.instance.hash,
                self.part
            )


class PartDownloadForm(forms.ModelForm):
    download = forms.BooleanField(required=False, initial=False)

    class Meta:
        model = PartDownload
        fields = ()
    
    def __init__(self, data=None, initial={}, *args, **kwargs):
        part_initial = {}

        self.download_batch = initial['batch']
        self.part = initial['part']
        part_initial = {
            'ds_name': self.part.ds.name,    
            'dir_path': self.part.dir.full_path,
            'name': self.part.name,
        }

        initial.update(part_initial)

        if initial['dl']:
            self.dl = initial['dl']
            initial['download'] = True

        else:
            self.dl = None

        self.part_form = PartModelForm(initial=part_initial)

        if data:
            args = list(args)
            args.insert(0, data)

        super(PartDownloadForm, self).__init__(*args, initial=initial, **kwargs)

    def clean(self):
        data = super(PartDownloadForm, self).clean()
        part_data = {}
        
        for f in ['ds_name', 'dir_path', 'name']:
            if data and f in data:
                part_data[f] = data[f]

        self.part_form = PartModelForm(part_data)

        return data
    
    def is_valid(self):
        return self.part_form.is_valid() and super(PartDownloadForm, self).is_valid() 

    def save(self):
        if not self.cleaned_data['download']:
            if self.dl is None:
                # The part is not marked for download and has not been marked before
                return None

            else:
                # The part is not marked for download _now_, but has been marked before
                self.dl.delete()
                return None

        if self.dl:
            # The file is already marked for download, nothing to do
            return None

        with transaction.atomic():
            self.part_form.save()

            self.instance.download_batch = self.download_batch
            self.instance.part_model = self.part_form.instance

            try:
                with transaction.atomic():
                    self.instance.save()

            except IntegrityError as e:
                raise e  # FIXME


class BasePartDownloadFormSet(BaseFormSet):
    def add_fields(self, form, index):
        super(BasePartDownloadFormSet, self).add_fields(form, index)

        for name, f in form.part_form.fields.items():
            form.fields[name] = f

    def save(self):
        with transaction.atomic():
            for form in self.forms:
                form.save()


PartDownloadFormSet = formset_factory(
    PartDownloadForm,
    formset=BasePartDownloadFormSet,
    extra=0
)