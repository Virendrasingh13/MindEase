import uuid
from datetime import datetime
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import Client, Counsellor


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_NO_SHOW = 'no_show'

    PAYMENT_PENDING = 'pending'
    PAYMENT_PAID = 'paid'
    PAYMENT_FAILED = 'failed'
    PAYMENT_REFUNDED = 'refunded'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_NO_SHOW, 'No Show'),
    )

    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_PENDING, 'Pending'),
        (PAYMENT_PAID, 'Paid'),
        (PAYMENT_FAILED, 'Failed'),
        (PAYMENT_REFUNDED, 'Refunded'),
    )

    booking_reference = models.CharField(max_length=50, unique=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='bookings')
    counsellor = models.ForeignKey(Counsellor, on_delete=models.CASCADE, related_name='bookings')
    session_date = models.DateField()
    session_time = models.TimeField()
    session_duration = models.PositiveIntegerField(default=50, help_text='Duration in minutes')
    availability_slot = models.ForeignKey(
        'therapists.CounsellorAvailability',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )
    session_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    google_meet_link = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_PENDING,
    )
    client_notes = models.TextField(blank=True, help_text="Client's notes for the session")
    counsellor_notes = models.TextField(blank=True, help_text="Counsellor's private notes")
    cancellation_reason = models.TextField(blank=True)

    confirmed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bookings'
        ordering = ['-session_date', '-session_time']
        indexes = [
            models.Index(fields=['client', 'session_date']),
            models.Index(fields=['counsellor', 'session_date']),
            models.Index(fields=['status', 'payment_status']),
        ]

    def __str__(self) -> str:
        return f"{self.booking_reference} - {self.client.user.get_full_name()} ➜ {self.counsellor.user.get_full_name()}"

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            self.booking_reference = f"MBK-{uuid.uuid4().hex[:10].upper()}"
        if not self.google_meet_link:
            self.google_meet_link = self.counsellor.google_meet_link
        super().save(*args, **kwargs)

    @property
    def session_datetime(self):
        """Return aware datetime for the session start."""
        return timezone.make_aware(datetime.combine(self.session_date, self.session_time))

    def mark_confirmed(self):
        self.status = self.STATUS_CONFIRMED
        self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at', 'updated_at'])

    def mark_completed(self):
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])


class Payment(models.Model):
    METHOD_RAZORPAY = 'razorpay'

    METHOD_CHOICES = (
        (METHOD_RAZORPAY, 'Razorpay'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Wallet'),
    )

    STATUS_INITIATED = 'initiated'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = (
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
    )

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    payment_id = models.CharField(max_length=100, unique=True, editable=False)
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default='INR')
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_RAZORPAY)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED)
    payment_data = models.JSONField(blank=True, null=True, help_text='Additional payment data from Razorpay')
    error_message = models.TextField(blank=True)

    refund_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
    )
    refund_id = models.CharField(max_length=100, blank=True, null=True)
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(blank=True, null=True)

    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['razorpay_order_id']),
            models.Index(fields=['razorpay_payment_id']),
            models.Index(fields=['status']),
        ]

    def __str__(self) -> str:
        return f"Payment {self.payment_id} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.payment_id:
            self.payment_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    def mark_success(self, razorpay_payment_id, razorpay_signature, payload=None):
        self.status = self.STATUS_SUCCESS
        self.razorpay_payment_id = razorpay_payment_id
        self.razorpay_signature = razorpay_signature
        self.payment_data = payload or self.payment_data
        self.paid_at = timezone.now()
        self.error_message = ''
        self.save(
            update_fields=[
                'status',
                'razorpay_payment_id',
                'razorpay_signature',
                'payment_data',
                'paid_at',
                'error_message',
                'updated_at',
            ]
        )

    def mark_failed(self, error_message, payload=None):
        self.status = self.STATUS_FAILED
        self.error_message = error_message
        self.payment_data = payload or self.payment_data
        self.save(update_fields=['status', 'error_message', 'payment_data', 'updated_at'])

