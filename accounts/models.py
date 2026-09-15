from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    prof_pic = models.ImageField(upload_to='profile_pics/', default='default.png')

    def __str__(self):
        """Represent the user by their username."""
        return self.username
