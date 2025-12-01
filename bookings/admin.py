from django.contrib import admin

from .models import Booking, Payment


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_reference',
        'client',
        'counsellor',
        'session_date',
        'session_time',
        'status',
        'payment_status',
    )
    list_filter = ('status', 'payment_status', 'session_date')
    search_fields = (
        'booking_reference',
        'client__user__first_name',
        'client__user__last_name',
        'counsellor__user__first_name',
        'counsellor__user__last_name',
    )
    ordering = ('-session_date', '-session_time')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'payment_id',
        'booking',
        'amount',
        'status',
        'razorpay_order_id',
        'razorpay_payment_id',
        'created_at',
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('payment_id', 'booking__booking_reference', 'razorpay_order_id')

