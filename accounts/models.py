from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import os



# Custom user model extending AbstractUser
class User(AbstractUser):
    ROLE_CHOICES = (
        ('client', 'Client'),
        ('counsellor', 'Counsellor'),
    )
    
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    is_email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For counsellors - additional verification fields
    is_background_verified = models.BooleanField(default=False)
    background_verified_at = models.DateTimeField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Required for AbstractUser
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    def __str__(self):
        return f"{self.email} ({self.role})"
    
    class Meta:
        db_table = 'auth_user'



# Client-specific model
class Client(models.Model):
    PRIMARY_CONCERN_CHOICES = (
        ('anxiety', 'Anxiety & Stress'),
        ('depression', 'Depression'),
        ('relationship', 'Relationship Issues'),
        ('trauma', 'Trauma & PTSD'),
        ('self_improvement', 'Self-Improvement'),
        ('other', 'Other'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    date_of_birth = models.DateField()
    primary_concern = models.CharField(max_length=20, choices=PRIMARY_CONCERN_CHOICES)
    other_primary_concern = models.CharField(max_length=255, blank=True, null=True)
    about_me = models.TextField()
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(auto_now_add=True)
    
    # Additional fields for client management
    is_active = models.BooleanField(default=True)
    last_session_date = models.DateTimeField(null=True, blank=True)
    total_sessions = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Client: {self.user.get_full_name()}"
    
    def age(self):
        """Calculate age from date of birth"""
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    class Meta:
        db_table = 'clients'




# Counsellor-specific models

class Specialization(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'specializations'



class TherapyApproach(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'therapy_approaches'



class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'languages'



class AgeGroup(models.Model):
    name = models.CharField(max_length=50, unique=True)
    min_age = models.PositiveIntegerField()
    max_age = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.min_age}-{self.max_age})"
    
    class Meta:
        db_table = 'age_groups'



# Function for counsellor document upload paths
def counsellor_license_path(instance, filename):
    return f'counsellors/{instance.user.id}/license/{filename}'


def counsellor_degree_path(instance, filename):
    return f'counsellors/{instance.user.id}/degree/{filename}'


def counsellor_id_path(instance, filename):
    return f'counsellors/{instance.user.id}/id_proof/{filename}'



# Counsellor-specific model
class Counsellor(models.Model):
    LICENSE_TYPE_CHOICES = (
        ('clinical-psychologist', 'Clinical Psychologist'),
        ('counselling-psychologist', 'Counselling Psychologist'),
        ('psychiatrist', 'Psychiatrist'),
        ('lmhc', 'Licensed Mental Health Counselor'),
        ('lcsw', 'Licensed Clinical Social Worker'),
        ('other', 'Other'),
    )
    
    HIGHEST_DEGREE_CHOICES = (
        ('phd', 'Ph.D.'),
        ('masters', 'Masters'),
        ('mphil', 'M.Phil.'),
        ('bachelors', 'Bachelors'),
        ('diploma', 'Diploma'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    
    # Professional Information
    license_number = models.CharField(max_length=100)
    license_type = models.CharField(max_length=30, choices=LICENSE_TYPE_CHOICES)
    other_license_type = models.CharField(max_length=100, blank=True, null=True)
    license_authority = models.CharField(max_length=255)
    license_expiry = models.DateField()
    years_experience = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(50)]
    )
    highest_degree = models.CharField(max_length=20, choices=HIGHEST_DEGREE_CHOICES)
    university = models.CharField(max_length=255)
    graduation_year = models.PositiveIntegerField(
        validators=[MinValueValidator(1950), MaxValueValidator(2030)]
    )
    
    # Practice Details
    session_fee = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    google_meet_link = models.URLField()
    professional_experience = models.TextField()
    about_me = models.TextField()
    
    # Many-to-Many Relationships
    specializations = models.ManyToManyField(Specialization, related_name='counsellors')
    therapy_approaches = models.ManyToManyField(TherapyApproach, related_name='counsellors')
    languages = models.ManyToManyField(Language, related_name='counsellors')
    age_groups = models.ManyToManyField(AgeGroup, related_name='counsellors')
    
    # Documents
    license_document = models.FileField(upload_to=counsellor_license_path)
    degree_certificate = models.FileField(upload_to=counsellor_degree_path)
    id_proof = models.FileField(upload_to=counsellor_id_path)
    
    # Terms and Consent
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(auto_now_add=True)
    consent_given = models.BooleanField(default=False)
    consent_given_at = models.DateTimeField(auto_now_add=True)
    
    # Counsellor Status and Metrics
    is_active = models.BooleanField(default=False)  # Will be activated after verification
    is_featured = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, 
                                validators=[MinValueValidator(0), MaxValueValidator(5)])
    total_reviews = models.PositiveIntegerField(default=0)
    total_clients = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    
    # Availability
    is_available = models.BooleanField(default=True)
    available_from = models.TimeField(default='09:00:00')
    available_to = models.TimeField(default='18:00:00')
    default_session_duration = models.PositiveIntegerField(default=45)
    default_break_duration = models.PositiveIntegerField(default=5)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Counsellor: {self.user.get_full_name()}"
    
    def is_license_valid(self):
        """Check if license is still valid"""
        # If license_expiry is not set (None) or not a date, consider it invalid
        if not self.license_expiry:
            return False
        try:
            return self.license_expiry > timezone.now().date()
        except TypeError:
            return False
    
    def experience_level(self):
        """Categorize experience level"""
        if self.years_experience <= 2:
            return "Beginner"
        elif self.years_experience <= 5:
            return "Intermediate"
        elif self.years_experience <= 10:
            return "Experienced"
        else:
            return "Expert"
    
    def can_accept_clients(self):
        """Check if counsellor can accept new clients"""
        return (self.is_active and 
                self.is_background_verified and 
                self.is_email_verified and 
                self.is_available)
    
    class Meta:
        db_table = 'counsellors'



# Certification model for counsellors
class Certification(models.Model):
    counsellor = models.ForeignKey(Counsellor, on_delete=models.CASCADE, related_name='certifications')
    name = models.CharField(max_length=255)
    organization = models.CharField(max_length=255)
    year_obtained = models.PositiveIntegerField(
        validators=[MinValueValidator(1950), MaxValueValidator(2030)]
    )
    
    def certification_file_path(instance, filename):
        return f'counsellors/{instance.counsellor.user.id}/certifications/{filename}'
    
    certificate_file = models.FileField(upload_to=certification_file_path)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.counsellor.user.get_full_name()}"
    
    class Meta:
        db_table = 'certifications'
        unique_together = ['counsellor', 'name', 'organization']



# Email Verification Model
class EmailVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Email verification for {self.user.email}"
    
    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()
    
    class Meta:
        db_table = 'email_verifications'



# Background Verification Model for Counsellors
class BackgroundVerification(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    counsellor = models.OneToOneField(Counsellor, on_delete=models.CASCADE, related_name='background_verification')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='verified_counsellors')
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Verification details
    license_verified = models.BooleanField(default=False)
    degree_verified = models.BooleanField(default=False)
    identity_verified = models.BooleanField(default=False)
    certifications_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Background verification for {self.counsellor.user.get_full_name()}"
    
    def is_complete(self):
        return all([
            self.license_verified,
            self.degree_verified,
            self.identity_verified,
            self.certifications_verified
        ])
    
    class Meta:
        db_table = 'background_verifications'



# Review Model for Counsellors
class Review(models.Model):
    counsellor = models.ForeignKey(Counsellor, on_delete=models.CASCADE, related_name='reviews')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='reviews_given')
    
    # Rating (1-5 stars)
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Review content
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Review status
    is_verified = models.BooleanField(default=False)  # Admin verification
    is_published = models.BooleanField(default=True)
    
    # Helpful votes (future feature)
    helpful_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.client.user.get_full_name()} - {self.counsellor.user.get_full_name()} ({self.rating} stars)"
    
    class Meta:
        db_table = 'reviews'
        unique_together = ['counsellor', 'client']  # One review per client per counsellor
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['counsellor', '-created_at']),
            models.Index(fields=['rating']),
        ]