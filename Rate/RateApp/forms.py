from django import forms


class RegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'id': 'username',
            'placeholder': 'Придумай логин',
            'class': 'form-input',
            'autocomplete': 'username',
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'id': 'email',
            'placeholder': 'example@mail.com',
            'class': 'form-input',
            'autocomplete': 'email',
        })
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'id': 'password',
            'placeholder': 'Минимум 8 символов',
            'class': 'form-input',
            'autocomplete': 'new-password',
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'id': 'confirm_password',
            'placeholder': 'Повтори пароль',
            'class': 'form-input',
            'autocomplete': 'new-password',
        })
    )

    def clean_username(self):
        from .models import User
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Этот логин уже занят')
        return username

    def clean_email(self):
        from .models import User
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Этот email уже используется')
        return email

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get('password', '')
        cpw = cleaned.get('confirm_password', '')
        if pw and cpw and pw != cpw:
            self.add_error('confirm_password', 'Пароли не совпадают')
        return cleaned


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'id': 'username',
            'placeholder': 'Введи логин',
            'class': 'form-input',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'id': 'password',
            'placeholder': 'Введи пароль',
            'class': 'form-input',
            'autocomplete': 'current-password',
        })
    )
