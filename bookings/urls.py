from django.urls import path

from . import views

app_name = 'bookings'

urlpatterns = [
    path('bookings/create/', views.create_booking, name='create_booking'),
    path('bookings/verify/', views.verify_payment, name='verify_payment'),
    path('bookings/payment-failed/', views.payment_failed, name='payment_failed'),
]

