import tempfile
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from .models import Resources


# Use a temp MEDIA_ROOT so test images don't pollute real media folder
TEST_MEDIA_ROOT = tempfile.mkdtemp()


def create_test_image(name="test.gif"):
    """Return a tiny in-memory GIF file for ImageField."""
    return SimpleUploadedFile(
        name,
        b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
        b"\x00\x00\x00\xFF\xFF\xFF\x21\xF9\x04\x01\x00\x00\x00"
        b"\x00\x2C\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
        b"\x4C\x01\x00\x3B",
        content_type="image/gif",
    )


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ResourcesModelTests(TestCase):
    """Unit tests for Resources model behaviour."""

    def setUp(self):
        self.res1 = Resources.objects.create(
            title="Mindfulness Basics",
            type="Article",
            category="Mindfulness",
            difficulty="beginner",
            image=create_test_image("mindfulness.gif"),
            link="https://example.com/mindfulness",
            description="Intro article",
            duration="5 min",
            rating=4.5,
            featured=True,
            views=150,
        )

        # created slightly earlier and with lower rating/views
        self.res2 = Resources.objects.create(
            title="Deep Dive into CBT",
            type="PDF",
            category="CBT",
            difficulty="advanced",
            image=create_test_image("cbt.gif"),
            link="https://example.com/cbt",
            description="Advanced PDF",
            duration="30 min",
            rating=4.0,
            featured=False,
            views=80,
        )

    def test_str_returns_title(self):
        """__str__ should return the resource title."""
        self.assertEqual(str(self.res1), "Mindfulness Basics")
        self.assertEqual(str(self.res2), "Deep Dive into CBT")

    def test_default_ordering_featured_then_rating_then_created_at(self):
        """
        Model Meta ordering: featured first, then rating, then created_at (newest).
        """
        # Create a third resource with same featured=False but higher rating
        res3 = Resources.objects.create(
            title="Stress Relief Video",
            type="Video",
            category="Stress",
            difficulty="intermediate",
            image=create_test_image("stress.gif"),
            link="https://example.com/stress",
            description="Video resource",
            duration="10 min",
            rating=4.8,
            featured=False,
            views=50,
        )

        items = list(Resources.objects.all())
        # Featured resource (res1) should come first
        self.assertEqual(items[0], self.res1)
        # Among non-featured, higher rating (res3) should come before res2
        self.assertEqual(items[1], res3)
        self.assertEqual(items[2], self.res2)

    def test_defaults_for_views_and_rating(self):
        """If not given, views should default to 0 and rating to 0.0."""
        res = Resources.objects.create(
            title="Default Values Test",
            type="Audio",
            category="General",
            difficulty="beginner",
            image=create_test_image("default.gif"),
            link="https://example.com/default",
            description="Testing defaults",
        )
        self.assertEqual(res.views, 0)
        self.assertEqual(res.rating, 0.0)
        self.assertIsNotNone(res.created_at)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ResourceListViewTests(TestCase):
    """Integration tests for the resource_list view with filters & sorting."""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()

        # Create a mix of resources for filtering/sorting
        cls.r1 = Resources.objects.create(
            title="Anxiety Basics",
            type="Article",
            category="Anxiety",
            difficulty="beginner",
            image=create_test_image("anx.gif"),
            link="https://example.com/anxiety",
            description="Intro to anxiety",
            rating=4.2,
            views=120,
            featured=True,
        )
        cls.r1.created_at = now - timedelta(days=2)
        cls.r1.save(update_fields=["created_at"])

        cls.r2 = Resources.objects.create(
            title="Advanced Depression Video",
            type="Video",
            category="Depression",
            difficulty="advanced",
            image=create_test_image("dep.gif"),
            link="https://example.com/depression",
            description="Video session",
            rating=4.8,
            views=300,
            featured=False,
        )
        cls.r2.created_at = now - timedelta(days=1)
        cls.r2.save(update_fields=["created_at"])

        cls.r3 = Resources.objects.create(
            title="Stress Management PDF",
            type="PDF",
            category="Stress",
            difficulty="intermediate",
            image=create_test_image("stress.gif"),
            link="https://example.com/stress",
            description="Manage stress effectively",
            rating=3.9,
            views=50,
            featured=False,
        )
        cls.r3.created_at = now
        cls.r3.save(update_fields=["created_at"])

    def test_resource_list_status_and_template(self):
        """View should return 200 and render the correct template."""
        url = reverse("resource_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "resources/resources.html")
        self.assertIn("resources", response.context)
        self.assertEqual(response.context["total_resources"], 3)

    def test_search_filters_by_title_description_category(self):
        """Search query should match title/description/category (case-insensitive)."""
        url = reverse("resource_list")
        response = self.client.get(url, {"search": "stress"})
        self.assertEqual(response.status_code, 200)
        resources = list(response.context["resources"])
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].title, "Stress Management PDF")

    def test_filter_by_type(self):
        """Filter by single type should return only that type."""
        url = reverse("resource_list")
        response = self.client.get(url, {"type": "Video"})
        self.assertEqual(response.status_code, 200)
        resources = list(response.context["resources"])
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].type, "Video")

    def test_filter_by_category(self):
        """Filter by category should limit results accordingly."""
        url = reverse("resource_list")
        response = self.client.get(url, {"category": "Anxiety"})
        self.assertEqual(response.status_code, 200)
        resources = list(response.context["resources"])
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].category, "Anxiety")

    def test_filter_by_difficulty(self):
        """Filter by difficulty (ignoring 'any')."""
        url = reverse("resource_list")
        response = self.client.get(url, {"difficulty": "advanced"})
        self.assertEqual(response.status_code, 200)
        resources = list(response.context["resources"])
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].difficulty, "advanced")

        # difficulty = any → ignore filter, all resources
        response_any = self.client.get(url, {"difficulty": "any"})
        self.assertEqual(response_any.context["total_resources"], 3)

    def test_sort_by_popular_orders_by_views_then_rating(self):
        """When sort=popular, resources are ordered by views then rating."""
        url = reverse("resource_list")
        response = self.client.get(url, {"sort": "popular"})
        resources = list(response.context["resources"])

        # r2 has highest views, then r1, then r3
        self.assertEqual(resources[0], self.r2)
        self.assertEqual(resources[1], self.r1)
        self.assertEqual(resources[2], self.r3)

    def test_sort_by_title_orders_alphabetically(self):
        """sort=title should order resources A→Z by title."""
        url = reverse("resource_list")
        response = self.client.get(url, {"sort": "title"})
        titles = [r.title for r in response.context["resources"]]
        self.assertEqual(titles, sorted(titles))

    def test_pagination_limits_items_per_page(self):
        """View should paginate results with max 9 per page."""
        # Create extra resources to exceed 9
        for i in range(10):
            Resources.objects.create(
                title=f"Extra Resource {i}",
                type="Article",
                category="General",
                difficulty="beginner",
                image=create_test_image(f"extra_{i}.gif"),
                link=f"https://example.com/extra/{i}",
                description="Extra resource",
            )

        url = reverse("resource_list")
        response = self.client.get(url, {"page": 1})
        self.assertEqual(response.status_code, 200)

        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.number, 1)
        # Should show exactly 9 items on first page
        self.assertEqual(len(response.context["resources"]), 9)
        # Total should now be 13
        self.assertEqual(response.context["total_resources"], 13)
