from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
from unittest.mock import patch, MagicMock

import razorpay
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, Client as ClientProfile, Counsellor
from therapists.models import CounsellorAvailability
from .models import Booking, Payment


class BookingModelTests(TestCase):
    """Unit tests for the Booking model."""

    def setUp(self):
        # Create a counsellor user and profile
        self.counsellor_user = User.objects.create_user(
            email="counsellor@test.com",
            username="counsellor@test.com",
            password="pass12345",
            first_name="C",
            last_name="Therapist",
            role="counsellor",
            gender="female",
            phone="9999999999",
        )
        self.counsellor_user.is_email_verified = True
        self.counsellor_user.is_active = True
        self.counsellor_user.is_approved = True
        self.counsellor_user.save()

        self.counsellor = Counsellor.objects.create(
            user=self.counsellor_user,
            license_number="LIC-123",
            license_type="clinical-psychologist",
            license_authority="Board",
            license_expiry=date.today() + timedelta(days=365),
            years_experience=5,
            highest_degree="masters",
            university="Uni",
            graduation_year=2018,
            session_fee=Decimal("800.00"),
            google_meet_link="https://meet.google.com/test",
            professional_experience="Some experience",
            about_me="About",
            terms_accepted=True,
            consent_given=True,
            is_active=True,
        )

        # Create client user+profile
        self.client_user = User.objects.create_user(
            email="client@test.com",
            username="client@test.com",
            password="pass12345",
            first_name="Client",
            last_name="One",
            role="client",
            gender="female",
            phone="8888888888",
        )
        self.client_user.is_email_verified = True
        self.client_user.is_active = True
        self.client_user.save()

        self.client_profile = ClientProfile.objects.create(
            user=self.client_user,
            date_of_birth=date(2000, 1, 1),
            primary_concern="anxiety",
            about_me="Test client",
            terms_accepted=True,
        )

    def test_booking_reference_and_meet_link_auto_set(self):
        """Booking should auto-generate booking_reference and default meet link."""
        booking = Booking.objects.create(
            client=self.client_profile,
            counsellor=self.counsellor,
            session_date=date.today() + timedelta(days=5),
            session_time=time(10, 0),
            session_duration=50,
            session_fee=Decimal("800.00"),
            client_notes="Need help",
        )

        self.assertTrue(booking.booking_reference.startswith("MBK-"))
        self.assertEqual(booking.google_meet_link, self.counsellor.google_meet_link)
        self.assertIsNotNone(booking.created_at)

    def test_session_datetime_property(self):
        """session_datetime should combine date and time as an aware datetime."""
        session_date = date.today() + timedelta(days=4)
        session_time = time(15, 30)
        booking = Booking.objects.create(
            client=self.client_profile,
            counsellor=self.counsellor,
            session_date=session_date,
            session_time=session_time,
            session_duration=50,
            session_fee=Decimal("800.00"),
        )

        session_dt = booking.session_datetime
        self.assertEqual(session_dt.date(), session_date)
        self.assertEqual(session_dt.time().hour, session_time.hour)
        self.assertEqual(session_dt.time().minute, session_time.minute)

    def test_mark_confirmed_and_completed(self):
        """mark_confirmed and mark_completed should update status and timestamps."""
        booking = Booking.objects.create(
            client=self.client_profile,
            counsellor=self.counsellor,
            session_date=date.today() + timedelta(days=3),
            session_time=time(11, 0),
            session_duration=50,
            session_fee=Decimal("800.00"),
        )

        booking.mark_confirmed()
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)
        self.assertIsNotNone(booking.confirmed_at)

        booking.mark_completed()
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_COMPLETED)
        self.assertIsNotNone(booking.completed_at)


class PaymentModelTests(TestCase):
    """Unit tests for the Payment model."""

    def setUp(self):
        # Minimal setup reused from Booking model tests
        counsellor_user = User.objects.create_user(
            email="counsellor2@test.com",
            username="counsellor2@test.com",
            password="pass12345",
            first_name="C2",
            last_name="Therapist",
            role="counsellor",
            gender="female",
            phone="9999999999",
        )
        counsellor_user.is_email_verified = True
        counsellor_user.is_active = True
        counsellor_user.is_approved = True
        counsellor_user.save()

        self.counsellor = Counsellor.objects.create(
            user=counsellor_user,
            license_number="LIC-456",
            license_type="clinical-psychologist",
            license_authority="Board",
            license_expiry=date.today() + timedelta(days=365),
            years_experience=7,
            highest_degree="masters",
            university="Uni",
            graduation_year=2017,
            session_fee=Decimal("1000.00"),
            google_meet_link="https://meet.google.com/abc",
            professional_experience="Experience",
            about_me="About",
            terms_accepted=True,
            consent_given=True,
            is_active=True,
        )

        client_user = User.objects.create_user(
            email="client2@test.com",
            username="client2@test.com",
            password="pass12345",
            first_name="Client",
            last_name="Two",
            role="client",
            gender="female",
            phone="7777777777",
        )
        client_user.is_email_verified = True
        client_user.is_active = True
        client_user.save()

        self.client_profile = ClientProfile.objects.create(
            user=client_user,
            date_of_birth=date(1999, 1, 1),
            primary_concern="anxiety",
            about_me="Client2",
            terms_accepted=True,
        )

        self.booking = Booking.objects.create(
            client=self.client_profile,
            counsellor=self.counsellor,
            session_date=date.today() + timedelta(days=6),
            session_time=time(9, 0),
            session_duration=50,
            session_fee=Decimal("1000.00"),
        )

    def test_payment_id_autogenerated(self):
        """Payment should auto-generate payment_id on save."""
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("1000.00"),
        )
        self.assertTrue(payment.payment_id.startswith("PAY-"))

    def test_mark_success_updates_fields(self):
        """mark_success should update status, ids, signature, and timestamps."""
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("1000.00"),
        )

        payload = {"test": "data"}
        payment.mark_success(
            razorpay_payment_id="pay_123",
            razorpay_signature="sig_abc",
            payload=payload,
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_SUCCESS)
        self.assertEqual(payment.razorpay_payment_id, "pay_123")
        self.assertEqual(payment.razorpay_signature, "sig_abc")
        self.assertEqual(payment.payment_data, payload)
        self.assertIsNotNone(payment.paid_at)

    def test_mark_failed_updates_fields(self):
        """mark_failed should mark payment as failed and store error message."""
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("1000.00"),
        )

        payment.mark_failed("Something went wrong", payload={"error": "x"})
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_FAILED)
        self.assertEqual(payment.error_message, "Something went wrong")
        self.assertEqual(payment.payment_data, {"error": "x"})


@override_settings(
    RAZORPAY_KEY_ID="rzp_test_key",
    RAZORPAY_KEY_SECRET="rzp_test_secret",
)
class BookingViewsIntegrationTests(TestCase):
    """Integration tests for booking creation and payment views."""

    def setUp(self):
        self.client = Client()

        # Create client user + profile
        self.client_user = User.objects.create_user(
            email="client_view@test.com",
            username="client_view@test.com",
            password="pass12345",
            first_name="ViewClient",
            last_name="Test",
            role="client",
            gender="female",
            phone="6666666666",
        )
        self.client_user.is_email_verified = True
        self.client_user.is_active = True
        self.client_user.save()

        self.client_profile = ClientProfile.objects.create(
            user=self.client_user,
            date_of_birth=date(1998, 1, 1),
            primary_concern="anxiety",
            about_me="View client",
            terms_accepted=True,
        )

        # Create counsellor user + profile
        self.counsellor_user = User.objects.create_user(
            email="counsellor_view@test.com",
            username="counsellor_view@test.com",
            password="pass12345",
            first_name="ViewCounsellor",
            last_name="Test",
            role="counsellor",
            gender="female",
            phone="5555555555",
        )
        self.counsellor_user.is_email_verified = True
        self.counsellor_user.is_active = True
        self.counsellor_user.is_approved = True
        self.counsellor_user.save()

        self.counsellor = Counsellor.objects.create(
            user=self.counsellor_user,
            license_number="LIC-VIEW",
            license_type="clinical-psychologist",
            license_authority="Board",
            license_expiry=date.today() + timedelta(days=365),
            years_experience=5,
            highest_degree="masters",
            university="Uni",
            graduation_year=2018,
            session_fee=Decimal("900.00"),
            google_meet_link="https://meet.google.com/view",
            professional_experience="Experience",
            about_me="About",
            terms_accepted=True,
            consent_given=True,
            is_active=True,
        )

        # Availability slot for future date
        self.session_date = date.today() + timedelta(days=4)
        self.session_time = time(10, 0)

        self.availability_slot = CounsellorAvailability.objects.create(
            counsellor=self.counsellor,
            date=self.session_date,
            start_time=self.session_time,
            end_time=time(11, 0),
            duration_minutes=50,
            is_booked=False,
        )

        # URLs
        self.create_url = reverse("bookings:create_booking")
        self.verify_url = reverse("bookings:verify_payment")
        self.payment_failed_url = reverse("bookings:payment_failed")

    @patch("bookings.views.razorpay.Client")
    def test_create_booking_success(self, mock_razorpay_client_cls):
        """Happy path: booking + payment + Razorpay order creation."""
        self.client.force_login(self.client_user)

        mock_client_instance = MagicMock()
        mock_client_instance.order.create.return_value = {
            "id": "order_123",
            "amount": 90000,
            "currency": "INR",
        }
        mock_razorpay_client_cls.return_value = mock_client_instance

        payload = {
            "counsellor_id": self.counsellor_user.id,
            "session_date": self.session_date.isoformat(),
            "session_time": "10:00",
            "session_duration": 50,
            "client_notes": "Need help with anxiety",
        }

        response = self.client.post(
            self.create_url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["order"]["id"], "order_123")

        # Booking created and slot booked
        booking = Booking.objects.get(booking_reference=data["booking"]["reference"])
        self.assertEqual(booking.client, self.client_profile)
        self.assertEqual(booking.counsellor, self.counsellor)
        self.availability_slot.refresh_from_db()
        self.assertTrue(self.availability_slot.is_booked)

        # Payment linked with Razorpay order id
        payment = Payment.objects.get(booking=booking)
        self.assertEqual(payment.razorpay_order_id, "order_123")

    def test_create_booking_requires_client_role(self):
        """Non-client users cannot create bookings."""
        # Login as counsellor user (no client profile)
        self.client.force_login(self.counsellor_user)

        payload = {
            "counsellor_id": self.counsellor_user.id,
            "session_date": self.session_date.isoformat(),
            "session_time": "10:00",
        }

        response = self.client.post(
            self.create_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data["success"])

    @patch("bookings.views.razorpay.Client")
    def test_create_booking_enforces_minimum_days(self, mock_razorpay_client_cls):
        """Booking must be at least 3 days in advance."""
        self.client.force_login(self.client_user)

        too_soon_date = date.today() + timedelta(days=1)

        payload = {
            "counsellor_id": self.counsellor_user.id,
            "session_date": too_soon_date.isoformat(),
            "session_time": "10:00",
        }

        response = self.client.post(
            self.create_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("at least 3 days", data["error"])

    def test_create_booking_invalid_payload(self):
        """Invalid JSON body should return 400."""
        self.client.force_login(self.client_user)

        response = self.client.post(
            self.create_url,
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Invalid payload.")

    @patch("bookings.views.razorpay.Client")
    def test_verify_payment_success(self, mock_razorpay_client_cls):
        """Successful payment verification updates booking, payment, and counters."""
        self.client.force_login(self.client_user)

        # Create booking & payment first
        booking = Booking.objects.create(
            client=self.client_profile,
            counsellor=self.counsellor,
            session_date=self.session_date,
            session_time=self.session_time,
            session_duration=50,
            session_fee=Decimal("900.00"),
            availability_slot=self.availability_slot,
        )
        payment = Payment.objects.create(
            booking=booking,
            amount=Decimal("900.00"),
            razorpay_order_id="order_abc",
        )

        mock_client_instance = MagicMock()
        # verify_payment_signature should NOT raise to simulate success
        mock_client_instance.utility.verify_payment_signature.return_value = None
        mock_razorpay_client_cls.return_value = mock_client_instance

        payload = {
            "booking_reference": booking.booking_reference,
            "razorpay_order_id": "order_abc",
            "razorpay_payment_id": "pay_abc",
            "razorpay_signature": "sig_xyz",
        }

        response = self.client.post(
            self.verify_url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        payment.refresh_from_db()
        booking.refresh_from_db()
        self.client_profile.refresh_from_db()
        self.counsellor.refresh_from_db()

        self.assertEqual(payment.status, Payment.STATUS_SUCCESS)
        self.assertEqual(booking.payment_status, Booking.PAYMENT_PAID)
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)
        self.assertIsNotNone(booking.confirmed_at)

        # Client counters updated
        self.assertEqual(self.client_profile.total_sessions, 1)
        self.assertIsNotNone(self.client_profile.last_session_date)

        # Counsellor counters updated
        self.assertEqual(self.counsellor.total_sessions, 1)
        self.assertEqual(self.counsellor.total_clients, 1)

    @patch("bookings.views.razorpay.Client")
    def test_verify_payment_invalid_signature(self, mock_razorpay_client_cls):
        """Invalid Razorpay signature marks payment & booking as failed."""
        self.client.force_login(self.client_user)

        booking = Booking.objects.create(
            client=self.client_profile,
            counsellor=self.counsellor,
            session_date=self.session_date,
            session_time=self.session_time,
            session_duration=50,
            session_fee=Decimal("900.00"),
        )
        payment = Payment.objects.create(
            booking=booking,
            amount=Decimal("900.00"),
            razorpay_order_id="order_abc",
        )

        mock_client_instance = MagicMock()
        mock_client_instance.utility.verify_payment_signature.side_effect = (
            razorpay.errors.SignatureVerificationError("bad signature")
        )
        mock_razorpay_client_cls.return_value = mock_client_instance

        payload = {
            "booking_reference": booking.booking_reference,
            "razorpay_order_id": "order_abc",
            "razorpay_payment_id": "pay_abc",
            "razorpay_signature": "invalid",
        }

        response = self.client.post(
            self.verify_url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])

        payment.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_FAILED)
        self.assertEqual(booking.payment_status, Booking.PAYMENT_FAILED)

    def test_payment_failed_marks_failed_and_releases_slot(self):
        """payment_failed endpoint should mark payment as failed and free slot if unpaid."""
        self.client.force_login(self.client_user)

        booking = Booking.objects.create(
            client=self.client_profile,
            counsellor=self.counsellor,
            session_date=self.session_date,
            session_time=self.session_time,
            session_duration=50,
            session_fee=Decimal("900.00"),
            availability_slot=self.availability_slot,
            payment_status=Booking.PAYMENT_PENDING,
        )
        payment = Payment.objects.create(
            booking=booking,
            amount=Decimal("900.00"),
        )

        # Mark slot as booked initially
        self.availability_slot.is_booked = True
        self.availability_slot.save(update_fields=["is_booked"])

        payload = {
            "booking_reference": booking.booking_reference,
            "error": {
                "description": "Payment failed at bank",
                "code": "BAD_REQ",
                "source": "bank",
                "step": "payment_auth",
                "reason": "declined_by_bank",
            },
        }

        response = self.client.post(
            self.payment_failed_url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        payment.refresh_from_db()
        booking.refresh_from_db()
        self.availability_slot.refresh_from_db()

        self.assertEqual(payment.status, Payment.STATUS_FAILED)
        self.assertEqual(booking.payment_status, Booking.PAYMENT_FAILED)
        self.assertFalse(self.availability_slot.is_booked)
