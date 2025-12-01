from django.urls import path
from .views import *

urlpatterns = [
    path('therapists/', therapist_list , name='therapists'),
    path('therapists/<int:counsellor_id>/', counsellor_detail, name='counsellor_detail'),
    path('therapists/<int:counsellor_id>/review/submit/', submit_review, name='submit_review'),
    path('review/<int:review_id>/edit/', edit_review, name='edit_review'),
    path('review/<int:review_id>/delete/', delete_review, name='delete_review'),
    # Counsellor dashboards
    path('therapists/dashboard/', counsellor_dashboard, name='counsellor_dashboard'),
    path('therapists/profile/', counsellor_profile, name='counsellor_profile'),
    path('therapists/profile/upload-picture/', upload_counsellor_profile_picture, name='upload_counsellor_profile_picture'),
    path('therapists/profile/update/', update_counsellor_profile, name='update_counsellor_profile'),
    path('therapists/<int:counsellor_id>/dashboard/', counsellor_dashboard, name='counsellor_dashboard_public'),
    path('therapists/manage-slots/', counsellor_manage_slots, name='counsellor_manage_slots'),
    path('therapists/api/availability/', counsellor_availability_api, name='counsellor_availability_api'),
    path('therapists/<int:counsellor_id>/availability/', public_counsellor_availability, name='counsellor_public_availability'),
]