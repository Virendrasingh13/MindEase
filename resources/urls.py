from django.urls import path
from .views import *

urlpatterns = [
    path('resources/', resource_list, name='resource_list'),
]