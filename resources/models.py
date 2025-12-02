from django.db import models
from accounts import models as accounts
# Create your models here.
class Resources(models.Model):
    TYPE_CHOICES = [
        ('Article', 'Article'),
        ('Video', 'Video'),
        ('PDF', 'PDF'),
        ('Audio', 'Audio'),
    ]

    DIFFICULTY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    Counsellor = models.ForeignKey(accounts.Counsellor, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    category = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=12, choices=DIFFICULTY_CHOICES)
    image = models.ImageField(upload_to='resources/images/', blank=False, null=False)
    link = models.URLField(max_length=200)
    description = models.TextField()
    duration = models.CharField(max_length=50, blank=True)
    rating = models.FloatField(default=0.0)
    featured = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
            ordering = ['-featured', '-rating', '-created_at']  # default ordering

    def __str__(self):
        return self.title
    

