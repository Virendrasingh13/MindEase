from datetime import date, datetime, time, timedelta
from decimal import Decimal

import json
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import (
    Client as DjangoTestClient,
    TestCase,
)
from django.urls import reverse

from accounts.models import (
    Client as ClientProfile,
    Counsellor,
    Language,
    Review,
    Specialization,
    TherapyApproach,
    AgeGroup,
)
from bookings.models import Booking
from therapists.models import CounsellorAvailability
from therapists.views import (
    _parse_iso_date,
    _parse_time_value,
    _serialize_slot,
    update_counsellor_rating,
)

User = get_user_model()


# -------------------------------------------------------------------
# Helper factory functions
# -------------------------------------------------------------------


def create_test_user(
    email: str,
    password: str = "pass12345",
    role: str = "client",
    first_name: str = "Test",
    last_name: str = "User",
):
    """
    Small helper to create a custom User instance with the required fields.
    """
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone="9998887777",
        gender="female",
        role=role,
    )
    user.is_active = True
    user.is_email_verified = True
    # mark as approved so that therapists filters work
    user.is_approved = True
    user.save()
    return user


def create_test_counsellor(user: User) -> Counsellor:
    """
    Helper to create a Counsellor with minimal valid data.
    """
    today = date.today()
    license_expiry = today + timedelta(days=365)

    dummy_file = SimpleUploadedFile("dummy.pdf", b"test-data", content_type="application/pdf")

    counsellor = Counsellor.objects.create(
        user=user,
        license_number="LIC-123",
        license_type="clinical-psychologist",
        other_license_type=None,
        license_authority="Psychology Board",
        license_expiry=license_expiry,
        years_experience=5,
        highest_degree="masters",
        university="Demo University",
        graduation_year=2015,
        session_fee=Decimal("1500.00"),
        google_meet_link="https://meet.google.com/demo",
        professional_experience="5 years of counselling experience",
        about_me="I help clients manage stress and anxiety.",
        license_document=dummy_file,
        degree_certificate=dummy_file,
        id_proof=dummy_file,
        terms_accepted=True,
        consent_given=True,
        is_active=True,
    )

    # attach some M2M data for filters
    spec = Specialization.objects.create(name="Anxiety", description="Anxiety specialist")
    lang = Language.objects.create(name="English", code="EN")
    approach = TherapyApproach.objects.create(name="CBT", description="Cognitive Behaviour Therapy")
    age_group = AgeGroup.objects.create(name="Adults", min_age=18, max_age=64, description="Adult clients")

    counsellor.specializations.add(spec)
    counsellor.languages.add(lang)
    counsellor.therapy_approaches.add(approach)
    counsellor.age_groups.add(age_group)

    return counsellor


def create_test_client(user: User) -> ClientProfile:
    """
    Helper to create a Client profile for a given user.
    """
    return ClientProfile.objects.create(
        user=user,
        date_of_birth=date(2000, 1, 1),
        primary_concern="anxiety",
        about_me="Client about me",
        terms_accepted=True,
    )


# -------------------------------------------------------------------
# Unit tests – Models & Helpers
# -------------------------------------------------------------------


class CounsellorAvailabilityModelTests(TestCase):
    """
    Unit tests for the CounsellorAvailability model.
    """

    def setUp(self):
        self.user = create_test_user("counsellor@example.com", role="counsellor", first_name="Thera")
        self.counsellor = create_test_counsellor(self.user)

    def test_str_returns_human_readable_representation(self):
        """
        __str__ should include counsellor full name, date and start time.
        """
        slot = CounsellorAvailability.objects.create(
            counsellor=self.counsellor,
            date=date.today() + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(10, 45),
            duration_minutes=45,
        )
        text = str(slot)
        self.assertIn("Thera", text)
        self.assertIn(slot.date.isoformat(), text)
        self.assertIn("10:00", text)

    def test_is_future_slot_true_for_future_date(self):
        """
        is_future_slot should return True for a slot scheduled in the future.
        """
        slot = CounsellorAvailability.objects.create(
            counsellor=self.counsellor,
            date=date.today() + timedelta(days=2),
            start_time=time(9, 0),
            end_time=time(9, 45),
            duration_minutes=45,
        )
        self.assertTrue(slot.is_future_slot)

    def test_is_future_slot_false_for_past_date(self):
        """
        is_future_slot should return False for a slot scheduled in the past.
        """
        slot = CounsellorAvailability.objects.create(
            counsellor=self.counsellor,
            date=date.today() - timedelta(days=2),
            start_time=time(9, 0),
            end_time=time(9, 45),
            duration_minutes=45,
        )
        self.assertFalse(slot.is_future_slot)


class TherapistsHelpersUnitTests(TestCase):
    """
    Unit tests for helper functions and the rating update helper.
    """

    def setUp(self):
        self.counsellor_user = create_test_user("counsellor@example.com", role="counsellor")
        self.counsellor = create_test_counsellor(self.counsellor_user)

        client_user = create_test_user("client@example.com", role="client")
        self.client = create_test_client(client_user)

    def test_update_counsellor_rating_with_reviews(self):
        """
        update_counsellor_rating should calculate and persist the average rating
        and total number of published reviews.

        NOTE: Review model allows only one review per (counsellor, client),
        so we create two reviews from two different clients.
        """
        # First review from self.client (created in setUp)
        Review.objects.create(
            counsellor=self.counsellor,
            client=self.client,
            rating=4,
            title="Good",
            content="Helpful session",
            is_published=True,
        )
        
        # Second review from another client
        client_user2 = create_test_user("client2_for_rating@example.com", role="client")
        client2 = create_test_client(client_user2)

        Review.objects.create(
            counsellor=self.counsellor,
            client=client2,
            rating=5,
            title="Great",
            content="Very helpful session",
            is_published=True,
        )

        # Recalculate rating and persist to counsellor
        update_counsellor_rating(self.counsellor)
        self.counsellor.refresh_from_db()

        # (4 + 5) / 2 = 4.5
        self.assertEqual(self.counsellor.total_reviews, 2)
        self.assertEqual(self.counsellor.rating, Decimal("4.50"))

    def test_update_counsellor_rating_without_reviews_sets_zero(self):
        """
        When no published reviews exist, rating and total_reviews should reset to 0.
        """
        update_counsellor_rating(self.counsellor)
        self.counsellor.refresh_from_db()
        self.assertEqual(self.counsellor.total_reviews, 0)
        self.assertEqual(self.counsellor.rating, Decimal("0.00"))

    def test_parse_iso_date_valid_and_invalid(self):
        """
        _parse_iso_date should parse valid yyyy-mm-dd strings and return None otherwise.
        """
        valid = _parse_iso_date("2025-05-01")
        self.assertEqual(valid, date(2025, 5, 1))

        self.assertIsNone(_parse_iso_date(""))
        self.assertIsNone(_parse_iso_date("not-a-date"))
        self.assertIsNone(_parse_iso_date(None))

    def test_parse_time_value_and_serialize_slot(self):
        """
        _parse_time_value should handle HH:MM and HH:MM:SS, and _serialize_slot
        should convert a slot to a simple dict.
        """
        t1 = _parse_time_value("10:30")
        t2 = _parse_time_value("11:45:00")
        self.assertEqual(t1, time(10, 30))
        self.assertEqual(t2, time(11, 45))
        self.assertIsNone(_parse_time_value("bad"))

        slot = CounsellorAvailability.objects.create(
            counsellor=self.counsellor,
            date=date(2025, 5, 1),
            start_time=time(9, 0),
            end_time=time(9, 45),
            duration_minutes=45,
        )
        data = _serialize_slot(slot)
        self.assertEqual(data["id"], slot.id)
        self.assertEqual(data["date"], "2025-05-01")
        self.assertEqual(data["start_time"], "09:00")
        self.assertEqual(data["end_time"], "09:45")
        self.assertFalse(data["is_booked"])
        

# -------------------------------------------------------------------
# Integration tests – Views
# -------------------------------------------------------------------


class TherapistsViewsIntegrationTests(TestCase):
    """
    Integration tests using Django's test client for all therapists views.
    """

    def setUp(self):
        self.client_http = DjangoTestClient()

        # Counsellor + profile
        self.counsellor_user = create_test_user(
            "counsellor@example.com", role="counsellor", first_name="Thera", last_name="Pist"
        )
        self.counsellor = create_test_counsellor(self.counsellor_user)

        # Primary client
        self.client_user = create_test_user("client1@example.com", role="client", first_name="Alice")
        self.client_profile = create_test_client(self.client_user)

        # Second client (used for permission tests on reviews)
        self.other_client_user = create_test_user("client2@example.com", role="client", first_name="Bob")
        self.other_client_profile = create_test_client(self.other_client_user)

        # Non-profile user (neither client nor counsellor)
        self.simple_user = create_test_user("simple@example.com", role="client")
        # Do NOT create ClientProfile for this user – used to test permission paths.

        # Some bookings for dashboard stats
        today = date.today()
        Booking.objects.create(
            client=self.client_profile,
            counsellor=self.counsellor,
            session_date=today,
            session_time=time(9, 0),
            session_duration=50,
            session_fee=Decimal("1500.00"),
            google_meet_link=self.counsellor.google_meet_link,
            status=Booking.STATUS_CONFIRMED,
            payment_status=Booking.PAYMENT_PAID,
        )
        Booking.objects.create(
            client=self.client_profile,
            counsellor=self.counsellor,
            session_date=today + timedelta(days=3),
            session_time=time(10, 0),
            session_duration=50,
            session_fee=Decimal("2000.00"),
            google_meet_link=self.counsellor.google_meet_link,
            status=Booking.STATUS_PENDING,
            payment_status=Booking.PAYMENT_PENDING,
        )

        # One availability slot in the future
        self.slot_future_date = date.today() + timedelta(days=5)
        self.availability_slot = CounsellorAvailability.objects.create(
            counsellor=self.counsellor,
            date=self.slot_future_date,
            start_time=time(10, 0),
            end_time=time(10, 45),
            duration_minutes=45,
        )

    # --------------- Therapist list & detail -----------------

    def test_therapist_list_basic_and_search_filters(self):
        """
        therapist_list should return active/approved counsellors and support search by name.
        """
        url = reverse("therapists")
        resp = self.client_http.get(url)
        self.assertEqual(resp.status_code, 200)
        therapists = resp.context["therapists"]
        self.assertIn(self.counsellor, list(therapists))

        # search by first name
        resp_search = self.client_http.get(url, {"search": "Thera"})
        self.assertEqual(resp_search.status_code, 200)
        therapists_search = resp_search.context["therapists"]
        self.assertIn(self.counsellor, list(therapists_search))

    def test_counsellor_detail_includes_reviews_and_stats(self):
        """
        counsellor_detail should load counsellor, reviews and rating distribution in context.
        """
        Review.objects.create(
            counsellor=self.counsellor,
            client=self.client_profile,
            rating=5,
            title="Excellent",
            content="Very helpful.",
            is_published=True,
        )

        url = reverse("counsellor_detail", args=[self.counsellor_user.id])
        resp = self.client_http.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["counsellor"], self.counsellor)
        # reviews is a paginated page object
        reviews_page = resp.context["reviews"]
        self.assertEqual(reviews_page.paginator.count, 1)
        self.assertEqual(resp.context["total_reviews"], 1)

    # --------------- Reviews: submit, edit, delete ------------

    def test_submit_review_requires_client_profile(self):
        """
        Only users with a Client profile should be allowed to submit a review.
        """
        self.client_http.login(email="simple@example.com", password="pass12345")
        url = reverse("submit_review", args=[self.counsellor_user.id])
        resp = self.client_http.post(
            url,
            {"rating": "5", "title": "Test", "content": "Nice"},
            follow=True,
        )
        # user has no ClientProfile; review must not be created
        self.assertEqual(Review.objects.count(), 0)
        self.assertEqual(resp.status_code, 200)  # redirected with message

    def test_submit_review_success_and_updates_rating(self):
        """
        A valid POST from a client should create a review and update counsellor rating.
        """
        self.client_http.login(email="client1@example.com", password="pass12345")
        url = reverse("submit_review", args=[self.counsellor_user.id])
        resp = self.client_http.post(
            url,
            {"rating": "5", "title": "Great session", "content": "Very helpful session."},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Review.objects.count(), 1)
        self.counsellor.refresh_from_db()
        self.assertEqual(self.counsellor.total_reviews, 1)
        self.assertEqual(self.counsellor.rating, Decimal("5.00"))

    def test_edit_review_only_owner_can_edit(self):
        """
        Only the owner of a review should be able to edit it.
        """
        # owner review
        review = Review.objects.create(
            counsellor=self.counsellor,
            client=self.client_profile,
            rating=3,
            title="Okay",
            content="It was ok.",
            is_published=True,
        )

        # Another client tries to edit
        self.client_http.login(email="client2@example.com", password="pass12345")
        url = reverse("edit_review", args=[review.id])
        resp = self.client_http.post(
            url,
            {"rating": "5", "title": "Hacked", "content": "Not allowed"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.title, "Okay")  # unchanged

        # Owner edits successfully
        self.client_http.login(email="client1@example.com", password="pass12345")
        resp2 = self.client_http.post(
            url,
            {"rating": "4", "title": "Updated", "content": "Better now."},
            follow=True,
        )
        self.assertEqual(resp2.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.title, "Updated")
        self.assertEqual(review.rating, 4)

    def test_delete_review_only_owner_can_delete(self):
        """
        Only the owner of a review should be able to delete it.
        """
        review = Review.objects.create(
            counsellor=self.counsellor,
            client=self.client_profile,
            rating=4,
            title="To delete",
            content="Will be deleted.",
            is_published=True,
        )

        # other client cannot delete
        self.client_http.login(email="client2@example.com", password="pass12345")
        url = reverse("delete_review", args=[review.id])
        resp = self.client_http.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Review.objects.filter(id=review.id).exists())

        # owner deletes
        self.client_http.login(email="client1@example.com", password="pass12345")
        resp2 = self.client_http.post(url, follow=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(Review.objects.filter(id=review.id).exists())

    # --------------- Dashboards & profile views ---------------

    def test_counsellor_dashboard_requires_counsellor(self):
        """
        Non-counsellor users should be redirected away from counsellor_dashboard.
        """
        self.client_http.login(email="client1@example.com", password="pass12345")
        url = reverse("counsellor_dashboard")
        resp = self.client_http.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_counsellor_dashboard_shows_basic_stats(self):
        """
        Logged-in counsellor should see their earnings and session stats.
        """
        self.client_http.login(email="counsellor@example.com", password="pass12345")
        url = reverse("counsellor_dashboard")
        resp = self.client_http.get(url)
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertEqual(ctx["counsellor"], self.counsellor)
        self.assertGreaterEqual(ctx["total_sessions"], 0)
        self.assertGreaterEqual(ctx["total_clients"], 0)
        self.assertIn("earnings_summary", ctx)

    def test_counsellor_profile_permissions_and_success(self):
        """
        counsellor_profile should only be accessible by counsellors.
        """
        # client blocked
        self.client_http.login(email="client1@example.com", password="pass12345")
        resp_client = self.client_http.get(reverse("counsellor_profile"))
        self.assertEqual(resp_client.status_code, 302)

        # counsellor allowed
        self.client_http.login(email="counsellor@example.com", password="pass12345")
        resp_c = self.client_http.get(reverse("counsellor_profile"))
        self.assertEqual(resp_c.status_code, 200)
        self.assertEqual(resp_c.context["counsellor"], self.counsellor)

    # --------------- Profile picture upload & profile update --

    def test_upload_counsellor_profile_picture_permission_and_validation(self):
        """
        upload_counsellor_profile_picture should reject non-counsellors and invalid files.
        """
        url = reverse("upload_counsellor_profile_picture")

        # non-counsellor -> 403
        self.client_http.login(email="client1@example.com", password="pass12345")
        resp_forbidden = self.client_http.post(url)
        self.assertEqual(resp_forbidden.status_code, 403)

        # counsellor: invalid extension -> 400
        self.client_http.login(email="counsellor@example.com", password="pass12345")
        bad_file = SimpleUploadedFile("test.txt", b"not image", content_type="text/plain")
        resp_bad = self.client_http.post(url, {"profile_picture": bad_file})
        self.assertEqual(resp_bad.status_code, 400)
        self.assertFalse(json.loads(resp_bad.content)["success"])

    def test_upload_counsellor_profile_picture_success(self):
        """
        A valid image file should be accepted and stored on the user.
        """
        self.client_http.login(email="counsellor@example.com", password="pass12345")
        url = reverse("upload_counsellor_profile_picture")
        img_file = SimpleUploadedFile("avatar.jpg", b"fake-image-bytes", content_type="image/jpeg")
        resp = self.client_http.post(url, {"profile_picture": img_file})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.counsellor_user.refresh_from_db()
        self.assertTrue(bool(self.counsellor_user.profile_picture))

    def test_update_counsellor_profile_permissions_and_invalid_json(self):
        """
        update_counsellor_profile should require counsellor role and reject invalid JSON.
        """
        url = reverse("update_counsellor_profile")

        # non-counsellor
        self.client_http.login(email="client1@example.com", password="pass12345")
        resp_forbidden = self.client_http.post(url, content_type="application/json")
        self.assertEqual(resp_forbidden.status_code, 403)

        # counsellor + bad JSON
        self.client_http.login(email="counsellor@example.com", password="pass12345")
        resp_bad = self.client_http.post(url, data="not-json", content_type="application/json")
        self.assertEqual(resp_bad.status_code, 400)
        self.assertFalse(json.loads(resp_bad.content)["success"])

    def test_update_counsellor_profile_success_updates_fields(self):
        """
        Valid JSON payload should update user & counsellor fields and return the new data.
        """
        self.client_http.login(email="counsellor@example.com", password="pass12345")
        url = reverse("update_counsellor_profile")
        payload = {
            "first_name": "Updated",
            "last_name": "Name",
            "phone": "1234567890",
            "session_fee": "2000.00",
            "meet_link": "https://meet.google.com/updated",
            "professional_bio": "Updated professional bio.",
        }
        resp = self.client_http.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.counsellor_user.refresh_from_db()
        self.counsellor.refresh_from_db()
        self.assertEqual(self.counsellor_user.first_name, "Updated")
        self.assertEqual(self.counsellor.session_fee, Decimal("2000.00"))
        self.assertEqual(self.counsellor.google_meet_link, "https://meet.google.com/updated")

    # --------------- Availability APIs & manage slots ----------

    def test_counsellor_availability_api_requires_counsellor(self):
        """
        counsellor_availability_api should return 403 for users without a counsellor profile.
        """
        url = reverse("counsellor_availability_api")
        self.client_http.login(email="client1@example.com", password="pass12345")
        resp = self.client_http.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_counsellor_availability_api_get_returns_slots(self):
        """
        GET to counsellor_availability_api should return existing slots and meta information.
        """
        self.client_http.login(email="counsellor@example.com", password="pass12345")
        url = reverse("counsellor_availability_api")
        resp = self.client_http.get(
            url,
            {
                "start": (date.today() + timedelta(days=1)).isoformat(),
                "end": (date.today() + timedelta(days=10)).isoformat(),
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["slots"]), 1)
        self.assertIn("session_duration", data)
        self.assertIn("profile_visible", data)

    def test_counsellor_availability_api_post_creates_and_updates_slots(self):
        """
        POST to counsellor_availability_api should create new slots and update counsellor settings.
        """
        self.client_http.login(email="counsellor@example.com", password="pass12345")
        url = reverse("counsellor_availability_api")

        new_date = date.today() + timedelta(days=7)
        payload = {
            "session_duration": 30,
            "break_duration": 10,
            "profile_visible": True,
            "slots": [
                {
                    "date": new_date.isoformat(),
                    "start_time": "09:00",
                    "end_time": "09:30",
                }
            ],
        }
        resp = self.client_http.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["success"])
        # slot exists
        self.assertTrue(
            CounsellorAvailability.objects.filter(
                counsellor=self.counsellor, date=new_date, start_time=time(9, 0)
            ).exists()
        )
        self.counsellor.refresh_from_db()
        self.assertEqual(self.counsellor.default_session_duration, 30)
        self.assertTrue(self.counsellor.is_available)

    def test_public_counsellor_availability_validations_and_success(self):
        """
        public_counsellor_availability should validate date parameter and min lead time.
        """
        url = reverse("counsellor_public_availability", args=[self.counsellor_user.id])

        # missing/invalid date
        resp_bad = self.client_http.get(url)
        self.assertEqual(resp_bad.status_code, 400)
        self.assertFalse(json.loads(resp_bad.content)["success"])

        # too early date (< 3 days from today)
        too_early = date.today() + timedelta(days=1)
        resp_early = self.client_http.get(url, {"date": too_early.isoformat()})
        self.assertEqual(resp_early.status_code, 400)
        self.assertFalse(json.loads(resp_early.content)["success"])

        # valid future date with available slot
        resp_ok = self.client_http.get(url, {"date": self.slot_future_date.isoformat()})
        self.assertEqual(resp_ok.status_code, 200)
        data_ok = json.loads(resp_ok.content)
        self.assertTrue(data_ok["success"])
        self.assertGreaterEqual(len(data_ok["slots"]), 1)

    def test_counsellor_manage_slots_permissions_and_success(self):
        """
        counsellor_manage_slots should only be accessible by counsellors and render template.
        """
        url = reverse("counsellor_manage_slots")

        # non-counsellor
        self.client_http.login(email="client1@example.com", password="pass12345")
        resp_client = self.client_http.get(url)
        self.assertEqual(resp_client.status_code, 302)

        # counsellor
        self.client_http.login(email="counsellor@example.com", password="pass12345")
        resp_counsellor = self.client_http.get(url)
        self.assertEqual(resp_counsellor.status_code, 200)
        self.assertEqual(resp_counsellor.context["counsellor"], self.counsellor)
