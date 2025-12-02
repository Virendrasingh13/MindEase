# client/tests.py

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client as HttpClient
from django.urls import reverse

from accounts.models import Client as ClientProfile


User = get_user_model()


class ClientBaseTestCase(TestCase):
    """Base setup shared across client module tests."""

    def setUp(self):
        # Test HTTP client
        self.http = HttpClient()

        # Main client user
        self.client_user = User.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="Testpass123!",
            first_name="Client",
            last_name="User",
            phone="9998887777",
            gender="female",
            role="client",
        )
        self.client_profile = ClientProfile.objects.create(
            user=self.client_user,
            date_of_birth=date(2000, 1, 1),
            primary_concern="anxiety",
            about_me="Test client profile",
            terms_accepted=True,
            total_sessions=0,
        )

        # Non-client user (e.g. counsellor) for access control tests
        self.other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="Otherpass123!",
            first_name="Other",
            last_name="User",
            phone="8887776666",
            gender="male",
            role="counsellor",
        )

    def login_as_client(self):
        self.http.force_login(self.client_user)

    def login_as_other(self):
        self.http.force_login(self.other_user)


class ClientDashboardViewTests(ClientBaseTestCase):
    """Tests for the client_dashboard view."""

    def test_dashboard_requires_login(self):
        """Anonymous user should be redirected to login page."""
        url = reverse("client_dashboard")
        response = self.http.get(url)
        self.assertEqual(response.status_code, 302)
        # default login_required redirect contains "login" in URL
        self.assertIn("login", response.url)

    def test_dashboard_non_client_redirects_home(self):
        """Logged-in non-client is redirected to home."""
        self.login_as_other()
        url = reverse("client_dashboard")
        response = self.http.get(url)
        # Should redirect (messages + redirect('home'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_context_for_client_with_no_bookings(self):
        """
        Logged-in client sees dashboard with zero counts
        and correct basic stats when no bookings exist.
        """
        self.login_as_client()
        url = reverse("client_dashboard")
        response = self.http.get(url)

        self.assertEqual(response.status_code, 200)
        ctx = response.context

        self.assertEqual(ctx["client"], self.client_profile)
        self.assertEqual(ctx["user"], self.client_user)

        # No bookings yet → all counts and totals zero
        self.assertEqual(ctx["total_sessions"], 0)
        self.assertEqual(ctx["upcoming_count"], 0)
        self.assertEqual(ctx["past_count"], 0)
        self.assertEqual(ctx["completed_sessions"], 0)
        self.assertEqual(ctx["pending_payments"], 0)
        self.assertEqual(ctx["total_spent"], Decimal("0.00"))
        self.assertIsNone(ctx["next_session"])
        self.assertEqual(list(ctx["upcoming_appointments"]), [])
        self.assertEqual(list(ctx["past_appointments"]), [])


class ClientProfileViewTests(ClientBaseTestCase):
    """Tests for the client_profile view."""

    def test_profile_requires_login(self):
        """Anonymous user should be redirected."""
        url = reverse("client_profile")
        response = self.http.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_profile_non_client_redirects_home(self):
        """Non-client user cannot access profile page."""
        self.login_as_other()
        url = reverse("client_profile")
        response = self.http.get(url)
        self.assertEqual(response.status_code, 302)

    def test_profile_get_renders_template_and_context(self):
        """Client can view their profile with correct context."""
        self.login_as_client()
        url = reverse("client_profile")
        response = self.http.get(url)

        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx["client"], self.client_profile)
        self.assertEqual(ctx["user"], self.client_user)
        self.assertEqual(ctx["total_sessions"], 0)
        self.assertEqual(ctx["last_session_date"], self.client_profile.last_session_date)

    def test_profile_post_updates_basic_fields(self):
        """POST should update user + client fields and redirect."""
        self.login_as_client()
        url = reverse("client_profile")

        data = {
            "first_name": "Updated",
            "last_name": "Name",
            "phone": "7776665555",
            "gender": "female",  # valid choice
            "primary_concern": "depression",  # valid choice
            "about_me": "Updated about me",
        }

        response = self.http.post(url, data=data, follow=False)
        # Should redirect back to client_profile on success
        self.assertEqual(response.status_code, 302)

        # Reload from DB
        self.client_user.refresh_from_db()
        self.client_profile.refresh_from_db()

        self.assertEqual(self.client_user.first_name, "Updated")
        self.assertEqual(self.client_user.last_name, "Name")
        self.assertEqual(self.client_user.phone, "7776665555")
        self.assertEqual(self.client_user.gender, "female")

        self.assertEqual(self.client_profile.primary_concern, "depression")
        self.assertEqual(self.client_profile.about_me, "Updated about me")


class ChangePasswordViewTests(ClientBaseTestCase):
    """Tests for change_password view."""

    def test_change_password_get_renders_form(self):
        """GET request should render the change password page."""
        self.login_as_client()
        url = reverse("change_password")
        response = self.http.get(url)
        self.assertEqual(response.status_code, 200)

    def test_change_password_incorrect_current(self):
        """Incorrect current password shows error and does not change password."""
        self.login_as_client()
        url = reverse("change_password")

        response = self.http.post(
            url,
            {
                "current_password": "WrongPassword",
                "new_password": "Newpass123!",
                "confirm_password": "Newpass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        # Password should remain unchanged
        self.assertTrue(self.client_user.check_password("Testpass123!"))

    def test_change_password_mismatch_new_passwords(self):
        """Mismatching new passwords should show error and keep old password."""
        self.login_as_client()
        url = reverse("change_password")

        response = self.http.post(
            url,
            {
                "current_password": "Testpass123!",
                "new_password": "Newpass123!",
                "confirm_password": "Different123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.check_password("Testpass123!"))

    def test_change_password_success_redirects_based_on_role(self):
        """Valid password change should update password and redirect to client_profile."""
        self.login_as_client()
        url = reverse("change_password")

        response = self.http.post(
            url,
            {
                "current_password": "Testpass123!",
                "new_password": "Newpass456!",
                "confirm_password": "Newpass456!",
            },
        )

        # Successful change → redirect (for client) to client_profile
        self.assertEqual(response.status_code, 302)
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.check_password("Newpass456!"))


class UploadProfilePictureViewTests(ClientBaseTestCase):
    """Tests for upload_profile_picture AJAX endpoint."""

    def setUp(self):
        super().setUp()
        self.login_as_client()
        self.url = reverse("upload_profile_picture")

    def test_upload_requires_post_and_file(self):
        """Non-POST or missing file should return 400."""
        # GET
        response_get = self.http.get(self.url)
        self.assertEqual(response_get.status_code, 400)
        self.assertFalse(response_get.json()["success"])

        # POST with no file
        response_post = self.http.post(self.url, {})
        self.assertEqual(response_post.status_code, 400)
        self.assertFalse(response_post.json()["success"])

    def test_upload_rejects_invalid_file_type(self):
        """Only image types (jpeg/png/gif) are allowed."""
        fake_file = SimpleUploadedFile(
            "test.txt", b"not an image", content_type="text/plain"
        )

        response = self.http.post(self.url, {"profile_picture": fake_file})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("Invalid file type", body["error"])

    def test_upload_rejects_too_large_file(self):
        """File larger than 5MB should be rejected."""
        # Create a dummy 5MB+1 byte file
        big_content = b"a" * (5 * 1024 * 1024 + 1)
        big_file = SimpleUploadedFile(
            "big_image.jpg", big_content, content_type="image/jpeg"
        )

        response = self.http.post(self.url, {"profile_picture": big_file})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("File size must be less than 5MB", body["error"])

    def test_upload_valid_image_succeeds(self):
        """Valid image upload should update user's profile_picture."""
        img_content = b"\x47\x49\x46"  # minimal bytes, type doesn't really matter
        image_file = SimpleUploadedFile(
            "avatar.png", img_content, content_type="image/png"
        )

        response = self.http.post(self.url, {"profile_picture": image_file})
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertTrue(body["success"])
        self.assertIn("image_url", body)

        self.client_user.refresh_from_db()
        self.assertIsNotNone(self.client_user.profile_picture)
