from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render

from accounts.models import Client
from bookings.models import Booking


@login_required
def client_dashboard(request):
    """
    Display client dashboard with sessions, appointments, and therapists.
    Only accessible by clients.
    """
    # Check if user is a client
    if not hasattr(request.user, 'client'):
        messages.error(request, 'Only clients can access this page.')
        return redirect('home')
    
    client = request.user.client
    
    # Get client statistics
    context = {
        'client': client,
        'user': request.user,
        'total_sessions': client.total_sessions,
    }
    
    # Get upcoming and past appointments (if bookings relation exists)
    bookings_qs = client.bookings.select_related('counsellor__user')
    today = date.today()

    upcoming_qs = bookings_qs.filter(session_date__gte=today).order_by('session_date', 'session_time')
    past_qs = bookings_qs.filter(session_date__lt=today).order_by('-session_date', '-session_time')
    paid_qs = bookings_qs.filter(payment_status=Booking.PAYMENT_PAID)

    total_spent = paid_qs.aggregate(total=Sum('session_fee'))['total'] or Decimal('0.00')
    completed_sessions = bookings_qs.filter(status=Booking.STATUS_COMPLETED).count()
    pending_payments = bookings_qs.filter(payment_status=Booking.PAYMENT_PENDING).count()

    context.update(
        {
            'upcoming_appointments': list(upcoming_qs[:5]),
            'past_appointments': list(past_qs[:5]),
            'next_session': upcoming_qs.first(),
            'upcoming_count': upcoming_qs.count(),
            'past_count': past_qs.count(),
            'completed_sessions': completed_sessions,
            'pending_payments': pending_payments,
            'total_spent': total_spent,
        }
    )
    
    # Get client's therapists (counsellors they've had sessions with)
    try:
        from accounts.models import Counsellor

        counsellor_ids = list(
            set(
                list(client.reviews_given.values_list('counsellor_id', flat=True))
                + list(client.bookings.values_list('counsellor_id', flat=True))
            )
        )
        my_therapists = Counsellor.objects.filter(user_id__in=counsellor_ids).select_related('user')[:3]
        context['my_therapists'] = my_therapists
    except:
        context['my_therapists'] = []
    
    return render(request, 'client_dashboard.html', context)


@login_required
def client_profile(request):
    """
    Display and allow editing of client's profile information.
    Only accessible by clients.
    """
    # Check if user is a client
    if not hasattr(request.user, 'client'):
        messages.error(request, 'Only clients can access this page.')
        return redirect('home')
    
    client = request.user.client
    next_session = None
    upcoming_appointments = []
    last_session_date = client.last_session_date
    total_sessions = client.total_sessions
    
    if request.method == 'POST':
        # Handle profile update
        try:
            user = request.user
            
            # Update user fields
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.phone = request.POST.get('phone', user.phone)
            # Only accept known gender choices
            gender_val = request.POST.get('gender', user.gender)
            if gender_val in dict(user.GENDER_CHOICES):
                user.gender = gender_val
            
            # Handle profile picture upload
            if 'profile_picture' in request.FILES:
                user.profile_picture = request.FILES['profile_picture']
            
            user.save()
            
            # Update client fields
            primary_concern_val = request.POST.get('primary_concern', client.primary_concern)
            if primary_concern_val in dict(client.PRIMARY_CONCERN_CHOICES):
                client.primary_concern = primary_concern_val
            client.about_me = request.POST.get('about_me', client.about_me)
            client.save()
            
            messages.success(request, 'Profile updated successfully!')
            return redirect('client_profile')
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
    
    # Enrich profile context with booking info
    try:
        today = date.today()
        upcoming_appointments = client.bookings.filter(
            session_date__gte=today
        ).select_related('counsellor__user').order_by('session_date', 'session_time')
        next_session = upcoming_appointments.first() if upcoming_appointments else None
    except Exception:
        upcoming_appointments = []
        next_session = None

    context = {
        'client': client,
        'user': request.user,
        'member_since': getattr(request.user, 'created_at', None),
        'total_sessions': total_sessions,
        'last_session_date': last_session_date,
        'next_session': next_session,
    }
    
    return render(request, 'client_profile.html', context)


@login_required
def change_password(request):
    """
    Allow users to change their password.
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validate current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'change_password.html')
        
        # Validate new password
        if len(new_password) < 8:
            messages.error(request, 'New password must be at least 8 characters long.')
            return render(request, 'change_password.html')
        
        # Validate password match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return render(request, 'change_password.html')
        
        # Update password
        try:
            request.user.set_password(new_password)
            request.user.save()
            
            # Keep user logged in after password change
            update_session_auth_hash(request, request.user)
            
            messages.success(request, 'Password changed successfully!')
            
            # Redirect based on user role
            if hasattr(request.user, 'client'):
                return redirect('client_profile')
            elif hasattr(request.user, 'counsellor'):
                return redirect('counsellor_profile')
            else:
                return redirect('home')
        except Exception as e:
            messages.error(request, f'Error changing password: {str(e)}')
    
    return render(request, 'change_password.html')


@login_required
def upload_profile_picture(request):
    """
    Handle profile picture upload via AJAX.
    """
    if request.method == 'POST' and request.FILES.get('profile_picture'):
        try:
            user = request.user
            profile_picture = request.FILES['profile_picture']
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if profile_picture.content_type not in allowed_types:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid file type. Please upload a JPEG, PNG, or GIF image.'
                }, status=400)
            
            # Validate file size (5MB max)
            if profile_picture.size > 5 * 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'error': 'File size must be less than 5MB.'
                }, status=400)
            
            # Save profile picture
            user.profile_picture = profile_picture
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Profile picture uploaded successfully!',
                'image_url': user.profile_picture.url
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error uploading profile picture: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'No file uploaded'
    }, status=400)
