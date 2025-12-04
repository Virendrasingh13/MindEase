"""
Factory Pattern Implementation for User Account Creation

This module implements the Factory design pattern to handle creation of different
user types (Client and Counsellor) with their specific profiles and relationships.
"""

from abc import ABC, abstractmethod
from django.db import transaction
from django.core.files.storage import FileSystemStorage
from .models import (
    User, Client, Counsellor, Certification,
    Specialization, TherapyApproach, Language, AgeGroup
)


class UserProfileFactory(ABC):
    """
    Abstract Factory for creating user profiles.
    Defines the interface for creating different types of user accounts.
    """
    
    @abstractmethod
    def create_user(self, **kwargs):
        """Create and return a User instance"""
        pass
    
    @abstractmethod
    def create_profile(self, user, **kwargs):
        """Create and return a profile (Client or Counsellor) for the user"""
        pass
    
    @abstractmethod
    def setup_relationships(self, profile, **kwargs):
        """Setup many-to-many relationships for the profile"""
        pass
    
    @transaction.atomic
    def create_account(self, **kwargs):
        """
        Template method that orchestrates the account creation process.
        This ensures all steps are executed in the correct order within a transaction.
        """
        user = self.create_user(**kwargs)
        profile = self.create_profile(user, **kwargs)
        self.setup_relationships(profile, **kwargs)
        return user, profile


class ClientFactory(UserProfileFactory):
    """
    Concrete Factory for creating Client accounts.
    Handles all client-specific account creation logic.
    """
    
    def create_user(self, **kwargs):
        """Create a User instance with client role"""
        user = User.objects.create_user(
            username=kwargs.get('username'),
            email=kwargs.get('email'),
            password=kwargs.get('password'),
            first_name=kwargs.get('first_name'),
            last_name=kwargs.get('last_name'),
            phone=kwargs.get('phone'),
            gender=kwargs.get('gender'),
            role='client'
        )
        
        # User is initially inactive until email verification
        user.is_active = False
        
        # Handle profile picture if provided
        if 'profile_picture' in kwargs and kwargs['profile_picture']:
            user.profile_picture = kwargs['profile_picture']
        
        user.save()
        return user
    
    def create_profile(self, user, **kwargs):
        """Create a Client profile for the user"""
        client = Client.objects.create(
            user=user,
            date_of_birth=kwargs.get('date_of_birth'),
            primary_concern=kwargs.get('primary_concern'),
            other_primary_concern=kwargs.get('other_primary_concern', ''),
            about_me=kwargs.get('about_me', ''),
            terms_accepted=kwargs.get('terms_accepted', False)
        )
        return client
    
    def setup_relationships(self, profile, **kwargs):
        """Clients don't have many-to-many relationships to setup"""
        pass


class CounsellorFactory(UserProfileFactory):
    """
    Concrete Factory for creating Counsellor accounts.
    Handles all counsellor-specific account creation logic including
    professional information, documents, and certifications.
    """
    
    def create_user(self, **kwargs):
        """Create a User instance with counsellor role"""
        user = User.objects.create_user(
            username=kwargs.get('username'),
            email=kwargs.get('email'),
            password=kwargs.get('password'),
            first_name=kwargs.get('first_name'),
            last_name=kwargs.get('last_name'),
            phone=kwargs.get('phone'),
            gender=kwargs.get('gender'),
            role='counsellor'
        )
        
        # User is initially inactive until email verification (and background verification for counsellors)
        user.is_active = False
        
        # Handle profile picture if provided
        if 'profile_picture' in kwargs and kwargs['profile_picture']:
            user.profile_picture = kwargs['profile_picture']
        
        user.save()
        return user
    
    def create_profile(self, user, **kwargs):
        """Create a Counsellor profile with professional details"""
        counsellor = Counsellor.objects.create(
            user=user,
            # Professional Information
            license_number=kwargs.get('license_number'),
            license_type=kwargs.get('license_type'),
            other_license_type=kwargs.get('other_license_type', ''),
            license_authority=kwargs.get('license_authority'),
            license_expiry=kwargs.get('license_expiry'),
            years_experience=kwargs.get('years_experience'),
            highest_degree=kwargs.get('highest_degree'),
            university=kwargs.get('university'),
            graduation_year=kwargs.get('graduation_year'),
            # Practice Details
            session_fee=kwargs.get('session_fee'),
            google_meet_link=kwargs.get('google_meet_link'),
            professional_experience=kwargs.get('professional_experience'),
            about_me=kwargs.get('about_me', ''),
            # Documents
            license_document=kwargs.get('license_document'),
            degree_certificate=kwargs.get('degree_certificate'),
            id_proof=kwargs.get('id_proof'),
            # Terms and Consent
            terms_accepted=kwargs.get('terms_accepted', False),
            consent_given=kwargs.get('consent_given', False)
        )
        
        # Create certifications if provided
        self._create_certifications(counsellor, kwargs.get('certifications', []))
        
        return counsellor
    
    def setup_relationships(self, profile, **kwargs):
        """Setup many-to-many relationships for counsellor"""
        # Specializations - handle both names and IDs
        if 'specializations' in kwargs:
            specialization_data = kwargs['specializations']
            specializations = self._get_or_create_objects(
                Specialization,
                specialization_data,
                'name',
                {'description': 'Specialization'}
            )
            profile.specializations.set(specializations)
        
        # Therapy Approaches - handle both names and IDs
        if 'therapy_approaches' in kwargs:
            approach_data = kwargs['therapy_approaches']
            approaches = self._get_or_create_objects(
                TherapyApproach,
                approach_data,
                'name',
                {'description': 'Therapy approach'}
            )
            profile.therapy_approaches.set(approaches)
        
        # Languages - handle both names and IDs
        if 'languages' in kwargs:
            language_data = kwargs['languages']
            languages = self._get_or_create_objects(
                Language,
                language_data,
                'name',
                {'code': 'CODE'}
            )
            profile.languages.set(languages)
        
        # Age Groups - handle both names and IDs with special mapping
        if 'age_groups' in kwargs:
            age_group_data = kwargs['age_groups']
            age_groups = self._get_or_create_age_groups(age_group_data)
            profile.age_groups.set(age_groups)
    
    def _get_or_create_objects(self, model, data_list, lookup_field, defaults):
        """
        Helper method to get or create objects from a list of names or IDs.
        
        Args:
            model: Django model class
            data_list: List of names or IDs
            lookup_field: Field to use for lookup/creation (e.g., 'name')
            defaults: Default values for creation
            
        Returns:
            QuerySet of model instances
        """
        objects = []
        
        for item in data_list:
            if not item:
                continue
            
            # Try to use as ID first
            try:
                obj = model.objects.get(id=int(item))
                objects.append(obj)
            except (ValueError, model.DoesNotExist):
                # If not an ID, treat as name and get_or_create
                kwargs = {lookup_field: item}
                obj, created = model.objects.get_or_create(**kwargs, defaults=defaults)
                objects.append(obj)
        
        return objects
    
    def _get_or_create_age_groups(self, age_group_data):
        """
        Helper method to handle age group creation with special mapping.
        
        Args:
            age_group_data: List of age group names or IDs
            
        Returns:
            List of AgeGroup instances
        """
        # Map age group names to predefined age ranges
        age_group_map = {
            'Children': {'min_age': 6, 'max_age': 12},
            'Adolescents': {'min_age': 13, 'max_age': 17},
            'Adults': {'min_age': 18, 'max_age': 64},
            'Seniors': {'min_age': 65, 'max_age': 100}
        }
        
        age_groups = []
        
        for item in age_group_data:
            if not item:
                continue
            
            # Try to use as ID first
            try:
                ag = AgeGroup.objects.get(id=int(item))
                age_groups.append(ag)
            except (ValueError, AgeGroup.DoesNotExist):
                # Treat as name
                if item in age_group_map:
                    age_range = age_group_map[item]
                    ag, created = AgeGroup.objects.get_or_create(
                        name=item,
                        defaults={
                            'min_age': age_range['min_age'],
                            'max_age': age_range['max_age'],
                            'description': f'{item} age group'
                        }
                    )
                    age_groups.append(ag)
        
        return age_groups
    
    def _create_certifications(self, counsellor, certifications_data):
        """Helper method to create certifications for the counsellor"""
        for cert_data in certifications_data:
            if isinstance(cert_data, dict) and all(
                key in cert_data for key in ['name', 'organization', 'year_obtained', 'certificate_file']
            ):
                Certification.objects.create(
                    counsellor=counsellor,
                    name=cert_data['name'],
                    organization=cert_data['organization'],
                    year_obtained=cert_data['year_obtained'],
                    certificate_file=cert_data['certificate_file']
                )


class AccountFactory:
    """
    Factory class that provides a unified interface for creating accounts.
    This is the main entry point for account creation.
    """
    
    @staticmethod
    def get_factory(role):
        """
        Factory method that returns the appropriate factory based on role.
        
        Args:
            role: The role of the user ('client' or 'counsellor')
            
        Returns:
            UserProfileFactory: The appropriate factory instance
            
        Raises:
            ValueError: If the role is not supported
        """
        factories = {
            'client': ClientFactory(),
            'counsellor': CounsellorFactory()
        }
        
        factory = factories.get(role)
        if not factory:
            raise ValueError(f"Unsupported role: {role}")
        
        return factory
    
    @staticmethod
    def create_account(role, **kwargs):
        """
        Convenience method to create an account with the specified role.
        
        Args:
            role: The role of the user ('client' or 'counsellor')
            **kwargs: Account creation parameters
            
        Returns:
            tuple: (user, profile) - The created user and profile objects
        """
        factory = AccountFactory.get_factory(role)
        return factory.create_account(**kwargs)