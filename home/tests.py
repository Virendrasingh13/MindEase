from django.test import TestCase
from django.urls import reverse

class HomeViewTests(TestCase):

    def test_home_view_status_code(self):
        url = reverse('home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_home_template_render(self):
        url = reverse('home')
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'home/index.html')

    def test_about_view_status_code(self):
        url = reverse('about')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_about_template_render(self):
        url = reverse('about')
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'about/about.html')
