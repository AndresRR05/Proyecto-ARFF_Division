from django import forms


class ArffUploadForm(forms.Form):
    """Formulario simplificado: solo subir un archivo .arff desde local."""
    arff_file = forms.FileField(required=True, label='Subir archivo (.arff)')
