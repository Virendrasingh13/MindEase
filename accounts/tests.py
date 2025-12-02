from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
import json
from datetime import date

from accounts.models import (
    User, Client as ClientProfile, Counsellor,
    EmailVerification, BackgroundVerification
)
from accounts.views import (
    validate_common_data, validate_client_data, validate_counsellor_data
)

UserModel = get_user_model()


# ------------------------------
# UNIT TESTS — MODELS + VALIDATION
# ------------------------------
class AccountsUnitTests(TestCase):

    def setUp(self):
        self.user = UserModel.objects.create_user(
            email="test@example.com",
            username="test@example.com",
            password="password123",
            first_name="John",
            last_name="Doe",
            phone="9998887777",
            gender="male",
            role="client",
            is_email_verified=True,
            is_active=True
        )
        self.client_profile = ClientProfile.objects.create(
            user=self.user,
            date_of_birth=date(2000, 1, 1),
            primary_concern="anxiety",
            about_me="test",
            terms_accepted=True
        )

    # ---------- Model tests ----------
    def test_client_age_method(self):
        """Ensure age() calculation is correct."""
        age = self.client_profile.age()
        self.assertTrue(20 < age < 60)

    def test_counsellor_license_validity(self):
        """Check if Counsellor license validity is computed correctly."""
        counsellor_user = UserModel.objects.create_user(
            email="coun@example.com",
            username="coun@example.com",
            password="abc12345",
            first_name="Dr",
            last_name="Smith",
            phone="9991112222",
            gender="male",
            role="counsellor",
            is_email_verified=True,
            is_active=True
        )
        counsellor = Counsellor.objects.create(
            user=counsellor_user,
            license_number="ABC123",
            license_type="clinical-psychologist",
            license_authority="Govt",
            license_expiry=timezone.now().date() + timedelta(days=5),
            years_experience=5,
            highest_degree="masters",
            university="XYZ",
            graduation_year=2015,
            session_fee=500.00,
            google_meet_link="https://meet.google.com/xyz",
            professional_experience="5 years exp",
            about_me="test",
            terms_accepted=True,
            consent_given=True
        )
        self.assertTrue(counsellor.is_license_valid())

    def test_email_verification_validity(self):
        """Check validity of EmailVerification token."""
        token = EmailVerification.objects.create(
            user=self.user,
            token="abc123",
            expires_at=timezone.now() + timedelta(hours=1)
        )
        self.assertTrue(token.is_valid())

    # ---------- Validation tests ----------
    def test_validate_common_data(self):
        data = {
            "first_name": "ABC",
            "last_name": "XYZ",
            "email": "valid@gmail.com",
            "phone": "9999999999",
            "gender": "male",
            "password": "12345678"
        }
        self.assertEqual(validate_common_data(data), {})

    def test_validate_common_data_invalid_email(self):
        data = {
            "first_name": "ABC",
            "last_name": "XYZ",
            "email": "invalid-email",
            "phone": "9999999999",
            "gender": "male",
            "password": "12345678"
        }
        errors = validate_common_data(data)
        self.assertIn("email", errors)


# ------------------------------
# INTEGRATION TESTS — END TO END FLOWS
# ------------------------------
class AccountsIntegrationTests(TestCase):

    def setUp(self):
        self.client_django = Client()

    def test_register_client_flow(self):
        """Client registration end-to-end should create user + client profile + send email token."""
        data = {
            "role": "client",
            "first_name": "Himani",
            "last_name": "Shah",
            "email": "client@test.com",
            "phone": "9998887777",
            "gender": "female",
            "password": "password123",
            "date_of_birth": "2000-01-01",
            "primary_concern": "anxiety",
            "about_me": "Test",
            "terms_accepted": "true",
        }

        response = self.client_django.post(reverse("register_user"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserModel.objects.filter(email="client@test.com").exists())
        user = UserModel.objects.get(email="client@test.com")
        self.assertFalse(user.is_active)  # Should activate only after verification email

        # Email token generated?
        self.assertTrue(EmailVerification.objects.filter(user=user).exists())

    def test_email_verification_flow(self):
        """Verify email token should activate user."""
        user = UserModel.objects.create_user(
            email="verify@test.com",
            username="verify@test.com",
            password="abc12345",
            first_name="A",
            last_name="B",
            phone="9999999999",
            gender="female",
            role="client",
            is_email_verified=False
        )
        token = EmailVerification.objects.create(
            user=user,
            token="tok123",
            expires_at=timezone.now() + timedelta(hours=1)
        )

        response = self.client_django.get(reverse("verify_email_api", args=["tok123"]))
        user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.is_email_verified)
        self.assertTrue(user.is_active)

    def test_login_success_after_verification(self):
        user = UserModel.objects.create_user(
            email="login@test.com",
            username="login@test.com",
            password="abc12345",
            first_name="A",
            last_name="B",
            phone="9998887777",
            gender="female",
            role="client",
            is_email_verified=True,
            is_active=True
        )
        response = self.client_django.post(
            reverse("login_user"),
            data=json.dumps({"email": "login@test.com", "password": "abc12345"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

    def test_login_fail_if_not_verified(self):
        user = UserModel.objects.create_user(
            email="notver@test.com",
            username="notver@test.com",
            password="pass12345",
            is_email_verified=False,
            role="client",
            first_name="A",
            last_name="B",
            phone="9998887777",
            gender="male",
        )
        response = self.client_django.post(
            reverse("login_user"),
            data=json.dumps({"email": "notver@test.com", "password": "pass12345"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_logout(self):
        user = UserModel.objects.create_user(
            email="logout@test.com",
            username="logout@test.com",
            password="pass12345",
            is_email_verified=True,
            is_active=True
        )
        self.client_django.force_login(user)
        response = self.client_django.post(reverse("logout"))
        self.assertEqual(response.status_code, 200)
