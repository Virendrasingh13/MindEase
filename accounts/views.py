import json
import secrets
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from datetime import timedelta
import re
from django.core.cache import cache
import uuid
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import (
    User, Client, Counsellor, Specialization, TherapyApproach, 
    Language, AgeGroup, Certification, EmailVerification, 
    BackgroundVerification
)
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect


from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.http import JsonResponse
import json




class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            str(user.pk) + str(timestamp) + str(user.is_active)
        )

password_reset_token = AccountActivationTokenGenerator()





@staff_member_required
def resend_single_verification_email(request, verification_id):
    """View to resend verification email for a single verification"""
    try:
        verification = BackgroundVerification.objects.get(id=verification_id)
        success, message = send_background_verification_email(
            verification.counsellor,
            verification.status,
            verification.notes
        )
        if success:
            messages.success(request, f"Email resent to {verification.counsellor.user.email}")
        else:
            messages.error(request, f"Failed to resend email: {message}")
    except BackgroundVerification.DoesNotExist:
        messages.error(request, "Background verification not found")
    
    return redirect(request.META.get('HTTP_REFERER', '/admin/'))




@ensure_csrf_cookie
def register_page(request):
    """Serve the registration page"""
    return render(request, 'accounts/register.html')




@require_http_methods(["POST"])
@transaction.atomic
def register_user(request):
    """Handle registration data from JavaScript and create user accounts"""
    try:
        # Print all received data for debugging
        print("\n" + "="*50)
        print("REGISTRATION DATA RECEIVED")
        print("="*50)
        
        # Print POST data
        print("POST DATA:")
        for key, value in request.POST.items():
            print(f"  {key}: {value}")
        
        # Print FILES data
        print("\nFILES DATA:")
        for key, file in request.FILES.items():
            print(f"  {key}: {file.name} ({file.content_type}, {file.size} bytes)")
        
        # Get role
        role = request.POST.get('role')
        print(f"\nROLE: {role}")
        
        # Validate required role
        if not role or role not in ['client', 'counsellor']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or missing role'
            }, status=400)
        
        # Common validation for both roles
        common_errors = validate_common_data(request.POST)
        if common_errors:
            return JsonResponse({
                'success': False,
                'errors': common_errors
            }, status=400)
        
        # Check if email already exists
        email = request.POST.get('email')
        if User.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'error': 'Email already exists'
            }, status=400)
        
        # Create user based on role
        if role == 'client':
            return create_client_account(request)
        elif role == 'counsellor':
            return create_counsellor_account(request)
            
    except Exception as e:
        print(f"Error processing registration: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)




def validate_common_data(post_data):
    """Validate common data for both client and counsellor"""
    errors = {}
    
    # Required fields
    required_fields = ['first_name', 'last_name', 'email', 'phone', 'gender', 'password']
    for field in required_fields:
        if not post_data.get(field):
            errors[field] = f'{field.replace("_", " ").title()} is required'
    
    # Email validation
    email = post_data.get('email')
    if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        errors['email'] = 'Invalid email format'
    
    # Phone validation (basic 10-digit check)
    phone = post_data.get('phone', '')
    if phone and not re.match(r'^\d{10}$', phone.replace(' ', '').replace('-', '')):
        errors['phone'] = 'Phone number must be 10 digits'
    
    # Password validation
    password = post_data.get('password')
    if password and len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters'
    
    return errors




def create_client_account(request):
    """Create a client account"""
    try:
        with transaction.atomic():
            # Validate client-specific data
            client_errors = validate_client_data(request.POST)
            if client_errors:
                return JsonResponse({
                    'success': False,
                    'errors': client_errors
                }, status=400)
            
            # Create User
            user = create_user_from_request(request, 'client')
            
            # Create Client profile
            client = Client.objects.create(
                user=user,
                date_of_birth=request.POST.get('date_of_birth'),
                primary_concern=request.POST.get('primary_concern'),
                other_primary_concern=request.POST.get('other_primary_concern') or None,
                about_me=request.POST.get('about_me'),
                terms_accepted=request.POST.get('terms_accepted') == 'true'
            )
            
            # Handle profile picture
            if 'profile_picture' in request.FILES:
                user.profile_picture = request.FILES['profile_picture']
                user.save()
            
            store_registration_email(request, user.email)

            # Send email verification
            send_verification_email(user)
            
            print(f"Client account created successfully: {user.email}")
            
            return JsonResponse({
                'success': True,
                'message': 'Client account created successfully. Please check your email for verification.',
                'role': 'client',
                'email': user.email
            })
            
    except Exception as e:
        print(f"Error creating client account: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to create client account'
        }, status=500)




def validate_client_data(post_data):
    """Validate client-specific data"""
    errors = {}
    
    # Required fields for client
    required_fields = ['date_of_birth', 'primary_concern', 'about_me']
    for field in required_fields:
        if not post_data.get(field):
            errors[field] = f'{field.replace("_", " ").title()} is required'
    
    # Validate date of birth (must be at least 18 years old)
    date_of_birth = post_data.get('date_of_birth')
    if date_of_birth:
        from datetime import datetime
        try:
            dob = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
            today = timezone.now().date()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 18:
                errors['date_of_birth'] = 'You must be at least 18 years old'
        except ValueError:
            errors['date_of_birth'] = 'Invalid date format'
    
    # Validate terms acceptance
    if post_data.get('terms_accepted') != 'true':
        errors['terms'] = 'You must accept the terms and conditions'
    
    return errors




def create_counsellor_account(request):
    """Create a counsellor account"""
    try:
        with transaction.atomic():
            # Validate counsellor-specific data
            counsellor_errors = validate_counsellor_data(request.POST)
            if counsellor_errors:
                return JsonResponse({
                    'success': False,
                    'errors': counsellor_errors
                }, status=400)
            
            # Create User
            user = create_user_from_request(request, 'counsellor')
            
            # Handle profile picture
            if 'profile_picture' in request.FILES:
                user.profile_picture = request.FILES['profile_picture']
                user.save()
            
            # Create Counsellor profile
            counsellor = create_counsellor_profile(user, request)
            
            # Create certifications
            create_counsellor_certifications(counsellor, request)
            
            # Create background verification record
            BackgroundVerification.objects.create(
                counsellor=counsellor,
                status='pending'
            )
            
            store_registration_email(request, user.email)

            # Send email verification
            send_verification_email(user)
            
            print(f"Counsellor account created successfully: {user.email}")
            
            return JsonResponse({
                'success': True,
                'message': 'Counsellor account created successfully. Please check your email for verification. Your account will be activated after background verification.',
                'role': 'counsellor',
                'email': user.email
            })
            
    except Exception as e:
        print(f"Error creating counsellor account: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to create counsellor account'
        }, status=500)




def validate_counsellor_data(post_data):
    """Validate counsellor-specific data"""
    errors = {}
    
    # Required fields for counsellor
    required_fields = [
        'license_number', 'license_type', 'license_authority', 'license_expiry',
        'years_experience', 'highest_degree', 'university', 'graduation_year',
        'session_fee', 'google_meet_link', 'professional_experience', 'about_me'
    ]
    
    for field in required_fields:
        if not post_data.get(field):
            errors[field] = f'{field.replace("_", " ").title()} is required'
    
    # Validate license expiry
    license_expiry = post_data.get('license_expiry')
    if license_expiry:
        try:
            expiry_date = timezone.datetime.strptime(license_expiry, '%Y-%m-%d').date()
            if expiry_date <= timezone.now().date():
                errors['license_expiry'] = 'License expiry date must be in the future'
        except ValueError:
            errors['license_expiry'] = 'Invalid date format'
    
    # Validate specializations and approaches
    specializations = post_data.getlist('specializations')
    if not specializations:
        errors['specializations'] = 'Please select at least one specialization'
    
    approaches = post_data.getlist('therapy_approaches')
    if not approaches:
        errors['therapy_approaches'] = 'Please select at least one therapy approach'
    
    languages = post_data.getlist('languages')
    if not languages:
        errors['languages'] = 'Please select at least one language'
    
    age_groups = post_data.getlist('age_groups')
    if not age_groups:
        errors['age_groups'] = 'Please select at least one age group'
    
    # Validate terms and consent
    if post_data.get('terms_accepted') != 'true':
        errors['terms'] = 'You must accept the terms and conditions'
    
    if post_data.get('consent_given') != 'true':
        errors['consent'] = 'You must consent to background verification'
    
    return errors




def create_user_from_request(request, role):
    """Create a User instance from request data"""
    user = User.objects.create_user(
        username=request.POST.get('email'),  # Use email as username
        email=request.POST.get('email'),
        password=request.POST.get('password'),
        first_name=request.POST.get('first_name'),
        last_name=request.POST.get('last_name'),
        phone=request.POST.get('phone'),
        gender=request.POST.get('gender'),
        role=role
    )
    
    # User is initially inactive until email verification (and background verification for counsellors)
    user.is_active = False
    user.save()
    
    return user




def create_counsellor_profile(user, request):
    """Create Counsellor profile with all related data"""
    
    # Handle file uploads
    fs = FileSystemStorage()
    
    license_document = None
    degree_certificate = None
    id_proof = None
    
    if 'license_document' in request.FILES:
        license_document = request.FILES['license_document']
    
    if 'degree_certificate' in request.FILES:
        degree_certificate = request.FILES['degree_certificate']
    
    if 'id_proof' in request.FILES:
        id_proof = request.FILES['id_proof']
    
    # Create counsellor instance
    counsellor = Counsellor.objects.create(
        user=user,
        license_number=request.POST.get('license_number'),
        license_type=request.POST.get('license_type'),
        other_license_type=request.POST.get('other_license_type') or None,
        license_authority=request.POST.get('license_authority'),
        license_expiry=request.POST.get('license_expiry'),
        years_experience=int(request.POST.get('years_experience')),
        highest_degree=request.POST.get('highest_degree'),
        university=request.POST.get('university'),
        graduation_year=int(request.POST.get('graduation_year')),
        session_fee=float(request.POST.get('session_fee')),
        google_meet_link=request.POST.get('google_meet_link'),
        professional_experience=request.POST.get('professional_experience'),
        about_me=request.POST.get('about_me'),
        license_document=license_document,
        degree_certificate=degree_certificate,
        id_proof=id_proof,
        terms_accepted=request.POST.get('terms_accepted') == 'true',
        consent_given=request.POST.get('consent_given') == 'true'
    )
    
    # Add many-to-many relationships
    add_many_to_many_relationships(counsellor, request)
    
    return counsellor



def add_many_to_many_relationships(counsellor, request):
    """Add specializations, approaches, languages, and age groups to counsellor"""
    
    # Specializations
    specialization_names = request.POST.getlist('specializations')
    for spec_name in specialization_names:
        specialization, created = Specialization.objects.get_or_create(
            name=spec_name,
            defaults={'description': f'Specialization in {spec_name}'}
        )
        counsellor.specializations.add(specialization)
    
    # Therapy approaches
    approach_names = request.POST.getlist('therapy_approaches')
    for approach_name in approach_names:
        approach, created = TherapyApproach.objects.get_or_create(
            name=approach_name,
            defaults={'description': f'{approach_name} therapy approach'}
        )
        counsellor.therapy_approaches.add(approach)
    
    # Languages
    language_names = request.POST.getlist('languages')
    for lang_name in language_names:
        language, created = Language.objects.get_or_create(
            name=lang_name,
            defaults={'code': lang_name[:3].upper()}
        )
        counsellor.languages.add(language)
    
    # Age groups
    age_group_names = request.POST.getlist('age_groups')
    for age_group_name in age_group_names:
        # Map age group names to predefined age ranges
        age_group_map = {
            'Children': ('Children', 6, 12),
            'Adolescents': ('Adolescents', 13, 17),
            'Adults': ('Adults', 18, 64),
            'Seniors': ('Seniors', 65, 100)
        }
        
        if age_group_name in age_group_map:
            name, min_age, max_age = age_group_map[age_group_name]
            age_group, created = AgeGroup.objects.get_or_create(
                name=name,
                defaults={
                    'min_age': min_age,
                    'max_age': max_age,
                    'description': f'{name} age group'
                }
            )
            counsellor.age_groups.add(age_group)



def create_counsellor_certifications(counsellor, request):
    """Create certification records for counsellor"""
    i = 0
    while True:
        cert_name = request.POST.get(f'certification_name_{i}')
        cert_org = request.POST.get(f'certification_organization_{i}')
        cert_year = request.POST.get(f'certification_year_{i}')
        
        # Stop when no more certifications are found
        if not cert_name or not cert_org or not cert_year:
            break
        
        # Get certification file if exists
        cert_file = None
        if f'certification_file_{i}' in request.FILES:
            cert_file = request.FILES[f'certification_file_{i}']
        
        # Create certification
        Certification.objects.create(
            counsellor=counsellor,
            name=cert_name,
            organization=cert_org,
            year_obtained=int(cert_year),
            certificate_file=cert_file
        )
        
        i += 1



def send_verification_email(user):
    """Send email verification link to user"""
    try:
        # Generate verification token
        token = secrets.token_urlsafe(32)
        
        # Create verification record
        expires_at = timezone.now() + timedelta(hours=24)

        EmailVerification.objects.create(
            user=user,
            token=token,
            expires_at=expires_at
        )
        
        # Build verification URL
        verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}/"
        
        # Email content
        subject = "Verify Your Email - MindEase"
        
        # HTML email template
        html_message = render_to_string('accounts/email_verification.html', {
            'user': user,
            'verification_url': verification_url,
            'expires_hours': 24
        })
        
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        print(f"Verification email sent to {user.email}")
        
    except Exception as e:
        print(f"Error sending verification email: {str(e)}")
        # Don't raise the exception - we don't want to fail registration if email fails





@require_http_methods(["GET"])
def verify_email_page(request, token):
    """Serve the beautiful email verification result page"""
    return render(request, 'accounts/email_verification_result.html', {'token': token})





@require_http_methods(["GET"])
def verify_email_api(request, token):
    """API endpoint to verify email - called by JavaScript"""
    try:
        # Find verification record
        verification = EmailVerification.objects.get(
            token=token,
            expires_at__gt=timezone.now()
        )
        
        # Check if already used
        if verification.is_used:
            user = verification.user
            return JsonResponse({
                'success': False,
                'error': 'Email already verified',
                'user_email': user.email
            }, status=400)
        
        # Mark as used and verify user
        verification.is_used = True
        verification.save()
        
        user = verification.user
        user.is_email_verified = True

        user.is_active = True
        
        user.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Email verified successfully!',
            'role': user.role,
            'user_email': user.email
        })
        
    except EmailVerification.DoesNotExist:
        # Check if there's any user with this token that might be already verified
        try:
            # Look for any verification record with this token (even expired or used)
            verification = EmailVerification.objects.get(token=token)
            user = verification.user
            
            if user.is_email_verified:
                return JsonResponse({
                    'success': False,
                    'error': 'Email already verified',
                    'user_email': user.email
                }, status=400)
            else:
                # Token exists but expired and not verified
                return JsonResponse({
                    'success': False,
                    'error': 'Verification token has expired. Please request a new verification email.'
                }, status=400)
                
        except EmailVerification.DoesNotExist:
            # No verification record found at all
            return JsonResponse({
                'success': False,
                'error': 'Invalid verification token'
            }, status=400)
    
    except Exception as e:
        print(f"Error verifying email: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)




# Check verification status
@require_http_methods(["GET"])
def check_verification_status(request):
    """Check if user's email is verified"""
    try:
        email = request.GET.get('email')
        if not email:
            return JsonResponse({
                'success': False,
                'error': 'Email is required'
            }, status=400)
        
        try:
            user = User.objects.get(email=email)
            return JsonResponse({
                'success': True,
                'is_verified': user.is_email_verified,
                'is_active': user.is_active,
                'role': user.role
            })
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)
            
    except Exception as e:
        print(f"Error checking verification status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)




@require_http_methods(["POST"])
def resend_verification_email(request):
    """Resend verification email to user"""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({
                'success': False,
                'error': 'Email is required'
            }, status=400)
        
        try:
            user = User.objects.get(email=email)
            
            # Check if user is already verified
            if user.is_email_verified:
                return JsonResponse({
                    'success': False,
                    'error': 'Email is already verified'
                }, status=400)
            
            # Check if there's a recent verification attempt (prevent spam)
            recent_verification = EmailVerification.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timedelta(minutes=2)
            ).first()
            
            if recent_verification:
                return JsonResponse({
                    'success': False,
                    'error': 'Please wait 2 minutes before requesting another verification email'
                }, status=400)
            
            # Send new verification email
            send_verification_email(user)
            
            return JsonResponse({
                'success': True,
                'message': 'Verification email sent successfully'
            })
            
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)
            
    except Exception as e:
        print(f"Error resending verification email: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)




def store_registration_email(request, email):
    """Store email in cache with session key"""
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    
    # Store email in cache with 1-hour expiry
    cache_key = f'registration_email_{session_key}'
    cache.set(cache_key, email, 3600)  # 1 hour expiry
    
    return session_key




def get_registration_email(request):
    """Retrieve email from cache using session key"""
    session_key = request.session.session_key
    if not session_key:
        return None
    
    cache_key = f'registration_email_{session_key}'
    return cache.get(cache_key)




@require_http_methods(["GET", "POST"])
def email_verify_view(request):
    """Serve email verification page with stored email"""
    email = None
    
    # If POST request, get email from request body
    if request.method == 'POST':
        email = request.POST.get('email')
        # Store in session for future reference
        if email:
            request.session['registered_email'] = email
    
    # If not in POST, try to get from query parameters (for backward compatibility)
    if not email:
        email = request.GET.get('email')
    
    # If still not found, try cache
    if not email:
        email = get_registration_email(request)
    
    # If still not found, try session (fallback)
    if not email:
        email = request.session.get('registered_email')
    
    context = {
        'email': email or 'your.email@example.com'  # Default fallback
    }
    return render(request, 'accounts/email_verify.html', context)





@require_http_methods(["POST"])
def login_user(request):
    """Handle user login with proper validation for all verification statuses"""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        password = data.get('password')
        remember_me = data.get('remember_me', False)
        
        # Basic validation
        if not email or not password:
            return JsonResponse({
                'success': False,
                'error': 'Email and password are required',
                'error_type': 'validation_error'
            }, status=400)
        
        # First, check if user exists with this email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid email or password',
                'error_type': 'invalid_credentials'
            }, status=400)
        
        # Authenticate user with password
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            # Check email verification for both roles
            if not user.is_email_verified:
                return JsonResponse({
                    'success': False,
                    'error': 'Please verify your email address to continue',
                    'error_type': 'email_not_verified',
                    'role': user.role
                }, status=400)
            
            # For clients: if email verified, they can login
            if user.role == 'client':
                # Log the user in
                auth_login(request, user)
                
                # Set session expiry based on remember me
                if not remember_me:
                    request.session.set_expiry(0)  # Browser session
                else:
                    request.session.set_expiry(1209600)  # 2 weeks
                
                return JsonResponse({
                    'success': True,
                    'message': 'Login successful! Welcome back to MindEase.',
                    'redirect_url': '/client/dashboard/',
                    'role': user.role
                })
            
            # For counsellors: check background verification after email verification
            elif user.role == 'counsellor':
                try:
                    counsellor = Counsellor.objects.get(user=user)
                    background_verification = BackgroundVerification.objects.get(counsellor=counsellor)
                    
                    # If background verification is approved, allow login
                    if background_verification.status == 'approved':
                        # Log the user in
                        auth_login(request, user)
                        
                        # Set session expiry based on remember me
                        if not remember_me:
                            request.session.set_expiry(0)  # Browser session
                        else:
                            request.session.set_expiry(1209600)  # 2 weeks
                        
                        return JsonResponse({
                            'success': True,
                            'message': 'Login successful! Welcome back to MindEase.',
                            'redirect_url': '/counsellor/dashboard/',
                            'role': user.role
                        })
                    # Handle rejected background verification
                    elif background_verification.status == 'rejected':
                        return JsonResponse({
                            'success': False,
                            'error': 'Your background verification has been rejected. Please create a new account with proper documentation to reapply.',
                            'error_type': 'background_verification_rejected'
                        }, status=400)
                    else:
                        # For any background verification status other than approved or rejected (pending, etc.)
                        return JsonResponse({
                            'success': False,
                            'error': 'Your background verification is pending approval. We will notify you via email once your account is activated.',
                            'error_type': 'background_verification_pending'
                        }, status=400)
                        
                except Counsellor.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Counsellor profile not found. Please contact support.',
                        'error_type': 'account_inactive'
                    }, status=400)
                except BackgroundVerification.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Background verification record not found. Please contact support.',
                        'error_type': 'account_inactive'
                    }, status=400)
            
        else:
            # Invalid credentials
            return JsonResponse({
                'success': False,
                'error': 'Invalid email or password',
                'error_type': 'invalid_credentials'
            }, status=400)
            
    except Exception as e:
        print(f"Error during login: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)




from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

@login_required
def logout_user(request):
    """Handle user logout"""
    if request.method == 'POST':
        auth_logout(request)
        return JsonResponse({
            'success': True,
            'message': 'Logged out successfully'
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method'
        }, status=405)




# @login_required
# def logout_user(request):
#     """Handle user logout"""
#     auth_logout(request)
#     return JsonResponse({
#         'success': True,
#         'message': 'Logged out successfully'
#     })




@require_http_methods(["POST"])
def password_reset_request(request):
    """Handle password reset request and send email"""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({
                'success': False,
                'error': 'Email is required'
            }, status=400)
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'No account found with this email address'
            }, status=400)
        
        # Generate password reset token
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = password_reset_token.make_token(user)
        
        # Build reset URL
        current_site = get_current_site(request)
        reset_url = f"http://{current_site.domain}/accounts/reset-password/{uid}/{token}/"
        
        # Send email
        subject = "MindEase - Password Reset Request"
        message = render_to_string('accounts/password_reset_email.html', {
            'user': user,
            'reset_url': reset_url,
            'domain': current_site.domain,
        })
        
        send_mail(
            subject,
            message,
            'noreply@mindease.com',
            [user.email],
            fail_silently=False,
            html_message=message
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Password reset link has been sent to your email'
        })
        
    except Exception as e:
        print(f"Error in password reset request: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please try again.'
        }, status=500)





def password_reset_confirm(request, uidb64, token):
    """Verify password reset token and render reset form"""
    try:
        # Decode user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    # Check if token is valid
    if user is not None and password_reset_token.check_token(user, token):
        context = {
            'valid_token': True,
            'uidb64': uidb64,
            'token': token,
        }
        return render(request, 'accounts/password_reset.html', context)
    else:
        context = {
            'valid_token': False,
            'error_message': 'The password reset link is invalid or has expired. Please request a new password reset.'
        }
        return render(request, 'accounts/password_reset.html', context)





@require_http_methods(["POST"])
def password_reset_complete(request):
    """Handle password reset completion"""
    try:
        data = json.loads(request.body)
        uidb64 = data.get('uidb64')
        token = data.get('token')
        new_password = data.get('new_password')
        
        if not all([uidb64, token, new_password]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        try:
            # Decode user ID
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return JsonResponse({
                'success': False,
                'error': 'Invalid user'
            }, status=400)
        
        # Verify token is still valid
        if not password_reset_token.check_token(user, token):
            return JsonResponse({
                'success': False,
                'error': 'The password reset link has expired. Please request a new password reset.'
            }, status=400)
        
        # Validate password strength
        if len(new_password) < 8:
            return JsonResponse({
                'success': False,
                'error': 'Password must be at least 8 characters long'
            }, status=400)
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Your password has been reset successfully. You can now login with your new password.'
        })
        
    except Exception as e:
        print(f"Error in password reset complete: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while resetting your password. Please try again.'
        }, status=500)





def send_background_verification_email(counsellor, status):
    """Send email notification for background verification status"""
    try:
        user = counsellor.user
        
        if status == 'approved':
            subject = "Background Verification Approved - MindEase"
            html_message = render_to_string('accounts/background_approved_email.html', {
                'user': user,
                'counsellor': counsellor
            })
        else:  # rejected
            subject = "Background Verification Update - MindEase"
            html_message = render_to_string('accounts/background_rejected_email.html', {
                'user': user,
                'counsellor': counsellor
            })
        
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        print(f"Background verification {status} email sent to {user.email}")
        
    except Exception as e:
        print(f"Error sending background verification email: {str(e)}")





@ensure_csrf_cookie
def login_view(request):
    return render(request, 'accounts/login.html')





# @require_http_methods(["POST"])
# @csrf_exempt
# @login_required
# def update_background_verification(request, counsellor_id):
#     """Admin function to update background verification status with detailed verification"""
#     try:
#         if not request.user.is_staff:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Permission denied'
#             }, status=403)
        
#         data = json.loads(request.body)
#         status = data.get('status')
#         notes = data.get('notes', '')
        
#         # Verification details
#         license_verified = data.get('license_verified', False)
#         degree_verified = data.get('degree_verified', False)
#         identity_verified = data.get('identity_verified', False)
#         certifications_verified = data.get('certifications_verified', False)
        
#         if status not in ['pending', 'in_progress', 'approved', 'rejected']:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Invalid status'
#             }, status=400)
        
#         try:
#             counsellor = Counsellor.objects.get(id=counsellor_id)
#             background_verification = BackgroundVerification.objects.get(counsellor=counsellor)
            
#             # Update status and verification details
#             background_verification.status = status
#             background_verification.notes = notes
#             background_verification.license_verified = license_verified
#             background_verification.degree_verified = degree_verified
#             background_verification.identity_verified = identity_verified
#             background_verification.certifications_verified = certifications_verified
            
#             # If approved, set verified_by and verified_at, and activate account
#             if status == 'approved':
#                 background_verification.verified_by = request.user
#                 background_verification.verified_at = timezone.now()
#                 # Activate user account
#                 user = counsellor.user
#                 user.is_active = True
#                 user.save()
            
#             background_verification.save()
            
#             # Send email notification
#             send_background_verification_email(counsellor, status, notes)
            
#             return JsonResponse({
#                 'success': True,
#                 'message': f'Background verification updated to {status} successfully'
#             })
            
#         except (Counsellor.DoesNotExist, BackgroundVerification.DoesNotExist):
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Counsellor not found'
#             }, status=404)
            
#     except Exception as e:
#         print(f"Error updating background verification: {str(e)}")
#         return JsonResponse({
#             'success': False,
#             'error': 'Internal server error'
#         }, status=500)





