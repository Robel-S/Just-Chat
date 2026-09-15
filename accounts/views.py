from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import generic

from .forms import CustomUserCreationForm, CustomUserChangeForm

class SignupPageView(generic.CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'registration/signup.html'
    
class EditProfilePageView(generic.UpdateView):
    form_class = CustomUserChangeForm
    success_url = reverse_lazy('edit_profile')
    template_name = 'registration/edit_profile.html'

    def get_object(self):
        """Return the authenticated user whose profile is being edited."""
        return self.request.user
