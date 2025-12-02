from django.urls import path
from .views import client_dashboard, client_profile, change_password, upload_profile_picture

urlpatterns = [
    path('client/dashboard/', client_dashboard, name='client_dashboard'),
    path('client/profile/', client_profile, name='client_profile'),
    path('client/upload-profile-picture/', upload_profile_picture, name='upload_profile_picture'),
    path('change-password/', change_password, name='change_password'),
]
