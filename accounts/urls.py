from django.urls import path
from . import views


urlpatterns = [
    path('register/', views.register_page, name='register'),
    path('register/create/', views.register_user, name='register_user'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),

    path('verify-email/<str:token>/', views.verify_email_page, name='verify_email_page'),
    path('api/verify-email/<str:token>/', views.verify_email_api, name='verify_email_api'), 
    
    
    path('check-verification/', views.check_verification_status, name='check_verification'),


    path('email_verify/', views.email_verify_view, name='email_verify'),
    path('login/', views.login_view, name='login'),
    path('login/user/', views.login_user, name='login_user'),
    path('logout/', views.logout_user, name='logout'),


    path('password-reset-request/', views.password_reset_request, name='password_reset_request'),
    path('reset-password/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('reset-password-complete/', views.password_reset_complete, name='password_reset_complete'),
    

    path('admin/background-verification/resend-email/<int:verification_id>/', views.resend_single_verification_email, name='resend_single_verification_email'),
]



