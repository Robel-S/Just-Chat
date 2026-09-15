from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model =  get_user_model()
        fields = (
            "email",
            "username",
            "prof_pic",
        )
        help_texts = {
            'username': '',
            'email': '',
        }

    def __init__(self, *args, **kwargs):
        """Initialize the form without Django's default password help text."""
        super().__init__(*args, **kwargs)
        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None

class CustomUserChangeForm(UserChangeForm):
    password = None  # Exclude the password field
    class Meta:
        model = get_user_model()
        fields = (
            "prof_pic",
            "username",
            "email",
        )
        help_texts = {
            'username': '',
            'email': '',
        }
