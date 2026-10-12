from django import forms
from .models import SalePayment

class SalePaymentForm(forms.ModelForm):
    class Meta:
        model = SalePayment
        fields = ['amount', 'method', 'reference']
