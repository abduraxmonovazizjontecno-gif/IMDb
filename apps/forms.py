from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator

from apps.models import User

phone_regex = RegexValidator(
    regex=r'^\+?[0-9\s\-]{7,20}$',
    message="Telefon raqam noto'g'ri formatda (masalan: +998901234567).",
)


class RatingForm(forms.Form):
    value = forms.IntegerField(min_value=1, max_value=10)


class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Parol'}),
                               label='Parol')
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Parolni takrorlang'}),
                                label='Parolni takrorlang')

    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone_number']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': "To'liq ismingiz"}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email (ixtiyoriy)'}),
            'phone_number': forms.TextInput(attrs={'placeholder': '+998901234567'}),
        }

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            validate_password(password)
        return password

    def clean_password2(self):
        password = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError('Parollar mos kelmadi')
        return password2

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone:
            try:
                phone_regex(phone)
            except Exception as e:
                raise forms.ValidationError(str(e))
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'email', 'avatar']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': "To'liq ismingiz"}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email (ixtiyoriy)'}),
        }
