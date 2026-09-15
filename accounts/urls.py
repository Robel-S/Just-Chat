from django.urls import path

from .views import SignupPageView, EditProfilePageView


urlpatterns = [
    path("signup/", SignupPageView.as_view(), name='signup'),
    path("profile/edit/", EditProfilePageView.as_view(), name='edit_profile'),
]