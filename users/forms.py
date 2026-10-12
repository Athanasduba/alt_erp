from django import forms
from .models import User

class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        strip=False,
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        strip=False,
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name',
            'email', 'role', 'warehouses', 'is_active'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control select2'}),
            # ✅ multi-select dropdown with Select2
            'warehouses': forms.SelectMultiple(attrs={'class': 'form-control select2-multi'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input ms-2'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        p1 = self.cleaned_data.get("password1")
        if p1:
            user.set_password(p1)
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserUpdateForm(forms.ModelForm):
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        strip=False,
        required=False,
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        strip=False,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name',
            'email', 'role', 'warehouses', 'is_active'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control select2'}),
            # ✅ same widget as create form
            'warehouses': forms.SelectMultiple(attrs={'class': 'form-control select2-multi'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input ms-2'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("new_password1")
        p2 = cleaned_data.get("new_password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("new_password2", "New passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        p1 = self.cleaned_data.get("new_password1")
        if p1:
            user.set_password(p1)
        if commit:
            user.save()
            self.save_m2m()
        return user
