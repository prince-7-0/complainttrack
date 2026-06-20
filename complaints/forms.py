from django import forms
from django.contrib.auth.models import User
from .models import Complaint

class ComplaintForm(forms.ModelForm):
    class Meta:
        model  = Complaint
        fields = ['title', 'description', 'location', 'priority']
        labels = {'location':'department'}
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Brief title of the issue',
                'class': 'form-input'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Describe the issue in detail...',
                'class': 'form-input'
            }),
            'location': forms.TextInput(attrs={
                'placeholder': 'Department (e.g. IT, HR, Maintenance)',
                'class': 'form-input'
            }),
            'priority': forms.Select(attrs={'class': 'form-input'}),
        }


class StatusUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(is_staff=False)

        if self.instance and self.instance.pk and self.instance.assigned_to is not None:
            # Already assigned — remove 'open' status option
            self.fields['status'].choices = [
                choice for choice in Complaint.STATUS_CHOICES if choice[0] != 'open'
            ]
            # Already assigned — make assigned_to required, no blank option
            self.fields['assigned_to'].required = True
            self.fields['assigned_to'].empty_label = None
        else:
            self.fields['assigned_to'].required = False

    class Meta:
        model  = Complaint
        fields = ['status', 'assigned_to', 'admin_notes']
        widgets = {
            'status':      forms.Select(attrs={'class': 'form-input'}),
            'assigned_to': forms.Select(attrs={'class': 'form-input'}),
            'admin_notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Add notes about this complaint...',
                'class': 'form-input'
            }),
        }

class AssignComplaintForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(is_staff=False)
        if current_user:
            qs = qs.exclude(pk=current_user.pk)
        self.fields['assigned_to'].queryset = qs
        self.fields['assigned_to'].required = True

    class Meta:
        model  = Complaint
        fields = ['assigned_to']
        widgets = {
            'assigned_to': forms.Select(attrs={'class': 'form-input'}),
        }


class NewEngineerForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={
        'class': 'form-input', 'placeholder': 'Enter username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-input', 'placeholder': 'Enter password'
    }))
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={
        'class': 'form-input', 'placeholder': 'Confirm password'
    }))

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        if User.objects.filter(username=cleaned.get('username')).exists():
            raise forms.ValidationError('Username already exists.')
        return cleaned