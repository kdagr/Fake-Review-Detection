from django import forms

class URLform(forms.Form):
    url = forms.URLField(max_length=250)