import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import Client, Counsellor, Language, Review, Specialization, TherapyApproach
from bookings.models import Booking
from therapists.models import CounsellorAvailability

def therapist_list(request):
    therapists = Counsellor.objects.filter(
        is_active=True,
        user__is_approved=True
    ).select_related("user").prefetch_related(
        "specializations",
        "languages",
        "therapy_approaches",
        "age_groups",
    )

    # Search
    q = request.GET.get("search")
    if q:
        therapists = therapists.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(specializations__name__icontains=q)
            | Q(therapy_approaches__name__icontains=q)
            | Q(languages__name__icontains=q)
        ).distinct()

    # Specialization Filter (by id)
    specialization = request.GET.get("specialization")
    if specialization:
        try:
            spec_id = int(specialization)
            therapists = therapists.filter(specializations__id=spec_id)
        except (ValueError, TypeError):
            pass

    # Experience filters
    min_exp = request.GET.get("min_experience")
    max_exp = request.GET.get("max_experience")
    if min_exp:
        try:
            therapists = therapists.filter(years_experience__gte=int(min_exp))
        except ValueError:
            pass
    if max_exp:
        try:
            therapists = therapists.filter(years_experience__lte=int(max_exp))
        except ValueError:
            pass

    # Price filters
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    if min_price:
        try:
            therapists = therapists.filter(session_fee__gte=Decimal(min_price))
        except (InvalidOperation, TypeError):
            pass
    if max_price:
        try:
            therapists = therapists.filter(session_fee__lte=Decimal(max_price))
        except (InvalidOperation, TypeError):
            pass

    # Rating filter (minimum rating)
    min_rating = request.GET.get("min_rating")
    if min_rating:
        try:
            therapists = therapists.filter(rating__gte=Decimal(min_rating))
        except (InvalidOperation, TypeError):
            pass

    # Language Filter
    lang = request.GET.get("language")
    if lang:
        therapists = therapists.filter(languages__id=lang)

    # Sorting
    sort = request.GET.get("sort")
    if sort == "price_low" or sort == "lowest_fee":
        therapists = therapists.order_by("session_fee")
    elif sort == "price_high":
        therapists = therapists.order_by("-session_fee")
    elif sort == "experience":
        therapists = therapists.order_by("-years_experience")
    elif sort == "rating" or sort == "highest_rated":
        therapists = therapists.order_by("-rating")
    elif sort == "newest":
        therapists = therapists.order_by("-created_at")
    else:
        therapists = therapists.order_by("user__first_name")

    # Pagination
    paginator = Paginator(therapists, 9)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Provide lists for filter dropdowns / checkboxes
    specializations_list = Specialization.objects.filter(is_active=True).order_by("name")
    languages_list = Language.objects.filter(is_active=True).order_by("name")
    approaches_list = TherapyApproach.objects.filter(is_active=True).order_by("name")

    return render(request, "therapists/therapists.html", {
        "page_obj": page_obj,
        "therapists": page_obj.object_list,
        "specializations_list": specializations_list,
        "languages_list": languages_list,
        "approaches_list": approaches_list,
    })


def counsellor_detail(request, counsellor_id):
    """View for displaying a single counsellor's detailed profile"""
    counsellor = get_object_or_404(
        Counsellor.objects.select_related("user").prefetch_related(
            "specializations",
            "languages",
            "therapy_approaches",
            "age_groups",
            "certifications"
        ),
        user_id=counsellor_id,
        is_active=True,
        user__is_approved=True
    )
    
    # Get reviews for this counsellor
    reviews = Review.objects.filter(
        counsellor=counsellor,
        is_published=True
    ).select_related('client__user').order_by('-created_at')
    
    # Pagination for reviews
    reviews_paginator = Paginator(reviews, 5)
    reviews_page = request.GET.get('reviews_page', 1)
    reviews_page_obj = reviews_paginator.get_page(reviews_page)
    
    # Calculate rating distribution
    rating_distribution = {
        5: reviews.filter(rating=5).count(),
        4: reviews.filter(rating=4).count(),
        3: reviews.filter(rating=3).count(),
        2: reviews.filter(rating=2).count(),
        1: reviews.filter(rating=1).count(),
    }
    
    total_reviews = reviews.count()
    rating_percentages = {}
    for rating, count in rating_distribution.items():
        if total_reviews > 0:
            rating_percentages[rating] = round((count / total_reviews) * 100)
        else:
            rating_percentages[rating] = 0
    
    # Check if current user has already reviewed this counsellor
    user_has_reviewed = False
    user_review = None
    if request.user.is_authenticated and hasattr(request.user, 'client'):
        try:
            user_review = Review.objects.get(
                counsellor=counsellor,
                client=request.user.client
            )
            user_has_reviewed = True
        except Review.DoesNotExist:
            pass
    
    booking_lead_time_days = 3
    return render(request, "therapists/counsellor_detail.html", {
        "counsellor": counsellor,
        "reviews": reviews_page_obj,
        "rating_distribution": rating_distribution,
        "rating_percentages": rating_percentages,
        "total_reviews": total_reviews,
        "user_has_reviewed": user_has_reviewed,
        "user_review": user_review,
        "min_booking_date": date.today() + timedelta(days=booking_lead_time_days),
        "booking_lead_time_days": booking_lead_time_days,
    })


@login_required
def submit_review(request, counsellor_id):
    """View for submitting a review for a counsellor"""
    if request.method != 'POST':
        return redirect('counsellor_detail', counsellor_id=counsellor_id)
    
    # Check if user is a client
    if not hasattr(request.user, 'client'):
        messages.error(request, 'Only clients can submit reviews.')
        return redirect('counsellor_detail', counsellor_id=counsellor_id)
    
    # Get the counsellor
    counsellor = get_object_or_404(Counsellor, user_id=counsellor_id)
    
    # Check if user has already reviewed this counsellor
    existing_review = Review.objects.filter(
        counsellor=counsellor,
        client=request.user.client
    ).first()
    
    if existing_review:
        messages.warning(request, 'You have already submitted a review for this counsellor.')
        return redirect('counsellor_detail', counsellor_id=counsellor_id)
    
    # Get form data
    rating = request.POST.get('rating')
    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()
    
    # Validate data
    errors = []
    if not rating:
        errors.append('Please select a rating.')
    else:
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                errors.append('Rating must be between 1 and 5.')
        except ValueError:
            errors.append('Invalid rating value.')
    
    if not title:
        errors.append('Please enter a review title.')
    elif len(title) > 200:
        errors.append('Title must be less than 200 characters.')
    
    if not content:
        errors.append('Please write your review.')
    elif len(content) < 10:
        errors.append('Review must be at least 10 characters long.')
    
    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect('counsellor_detail', counsellor_id=counsellor_id)
    
    # Create the review
    review = Review.objects.create(
        counsellor=counsellor,
        client=request.user.client,
        rating=rating,
        title=title,
        content=content,
        is_verified=False,  # Admin needs to verify
        is_published=True   # Publish immediately, but mark as unverified
    )
    
    # Update counsellor's rating and review count
    update_counsellor_rating(counsellor)
    
    messages.success(request, 'Thank you for your review! It has been submitted successfully.')
    return redirect('counsellor_detail', counsellor_id=counsellor_id)


@login_required
def edit_review(request, review_id):
    """View for editing an existing review"""
    if request.method != 'POST':
        return redirect('therapists')
    
    # Get the review
    review = get_object_or_404(Review, id=review_id)
    
    # Check if the user is the owner of the review
    if not hasattr(request.user, 'client') or review.client != request.user.client:
        messages.error(request, 'You do not have permission to edit this review.')
        return redirect('counsellor_detail', counsellor_id=review.counsellor.user_id)
    
    # Get form data
    rating = request.POST.get('rating')
    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()
    
    # Validate data
    errors = []
    if not rating:
        errors.append('Please select a rating.')
    else:
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                errors.append('Rating must be between 1 and 5.')
        except ValueError:
            errors.append('Invalid rating value.')
    
    if not title:
        errors.append('Please enter a review title.')
    elif len(title) > 200:
        errors.append('Title must be less than 200 characters.')
    
    if not content:
        errors.append('Please write your review.')
    elif len(content) < 10:
        errors.append('Review must be at least 10 characters long.')
    
    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect('counsellor_detail', counsellor_id=review.counsellor.user_id)
    
    # Update the review
    review.rating = rating
    review.title = title
    review.content = content
    review.is_verified = False  # Reset verification status
    review.save()
    
    # Update counsellor's rating
    update_counsellor_rating(review.counsellor)
    
    messages.success(request, 'Your review has been updated successfully.')
    return redirect('counsellor_detail', counsellor_id=review.counsellor.user_id)


@login_required
def delete_review(request, review_id):
    """View for deleting a review"""
    if request.method != 'POST':
        return redirect('therapists')
    
    # Get the review
    review = get_object_or_404(Review, id=review_id)
    
    # Check if the user is the owner of the review
    if not hasattr(request.user, 'client') or review.client != request.user.client:
        messages.error(request, 'You do not have permission to delete this review.')
        return redirect('counsellor_detail', counsellor_id=review.counsellor.user_id)
    
    counsellor = review.counsellor
    counsellor_id = counsellor.user_id
    
    # Delete the review
    review.delete()
    
    # Update counsellor's rating
    update_counsellor_rating(counsellor)
    
    messages.success(request, 'Your review has been deleted successfully.')
    return redirect('counsellor_detail', counsellor_id=counsellor_id)


def update_counsellor_rating(counsellor):
    """Helper function to update counsellor's average rating and review count"""
    reviews = Review.objects.filter(
        counsellor=counsellor,
        is_published=True
    )
    
    total_reviews = reviews.count()
    
    if total_reviews > 0:
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
        counsellor.rating = round(avg_rating, 2)
        counsellor.total_reviews = total_reviews
    else:
        counsellor.rating = 0.00
        counsellor.total_reviews = 0
    
    counsellor.save()



@login_required
def counsellor_dashboard(request, counsellor_id=None):
    """Render a counsellor dashboard. If `counsellor_id` is not provided, use the logged-in counsellor."""
    # determine the counsellor
    if counsellor_id:
        counsellor = get_object_or_404(Counsellor, user_id=counsellor_id, is_active=True, user__is_approved=True)
    else:
        if not hasattr(request.user, 'counsellor'):
            messages.error(request, 'You must be a counsellor to access the dashboard.')
            return redirect('therapists')
        counsellor = request.user.counsellor

    # Basic stats (use model fields where available)
    session_fee = counsellor.session_fee or Decimal('0.00')
    total_sessions = getattr(counsellor, 'total_sessions', 0) or 0
    total_clients = getattr(counsellor, 'total_clients', 0) or 0

    bookings_qs = counsellor.bookings.select_related('client__user')
    paid_sessions_qs = bookings_qs.filter(payment_status=Booking.PAYMENT_PAID)

    today = date.today()
    total_earnings = paid_sessions_qs.aggregate(total=Sum('session_fee'))['total'] or Decimal('0.00')
    month_start = today.replace(day=1)
    earnings_this_month = (
        paid_sessions_qs.filter(session_date__gte=month_start).aggregate(total=Sum('session_fee'))['total']
        or Decimal('0.00')
    )
    sessions_this_month = paid_sessions_qs.filter(session_date__gte=month_start).count()
    average_session_value = paid_sessions_qs.aggregate(avg=Avg('session_fee'))['avg'] or session_fee

    # Today's sessions and upcoming sessions
    todays_sessions_count = 0
    todays_sessions = []
    upcoming_sessions = []
    try:
        todays_qs = bookings_qs.filter(session_date=today).order_by('session_time')
        todays_sessions_count = todays_qs.count()
        todays_sessions = todays_qs[:6]

        upcoming_qs = bookings_qs.filter(session_date__gt=today).order_by('session_date', 'session_time')
        upcoming_sessions = upcoming_qs[:8]
        print(upcoming_sessions)
    except Exception:
        todays_sessions_count = 0
        todays_sessions = []
        upcoming_sessions = []

    pending_sessions_count = bookings_qs.filter(
        status=Booking.STATUS_PENDING,
        session_date__gte=today,
    ).count()

    satisfaction_percent = 0
    if counsellor.rating and counsellor.rating > 0:
        try:
            satisfaction_percent = int((Decimal(counsellor.rating) / Decimal('5')) * 100)
        except Exception:
            satisfaction_percent = 0

    context = {
        'counsellor': counsellor,
        'total_earnings': total_earnings,
        'total_sessions': total_sessions,
        'total_clients': total_clients,
        'todays_sessions_count': todays_sessions_count,
        'todays_sessions': todays_sessions,
        'upcoming_sessions': upcoming_sessions,
        'pending_sessions_count': pending_sessions_count,
        'earnings_summary': {
            'monthly': earnings_this_month,
            'average': average_session_value,
            'monthly_sessions': sessions_this_month,
        },
        'satisfaction_percent': satisfaction_percent,
    }

    return render(request, 'therapists/counsellor_dashboard.html', context)


@login_required
def counsellor_profile(request):
    """
    Display and allow editing of counsellor's own profile information.
    Only accessible by counsellors.
    """
    # Check if user is a counsellor
    if not hasattr(request.user, 'counsellor'):
        messages.error(request, 'Only counsellors can access this page.')
        return redirect('home')
    
    # Fetch counsellor with related objects for efficiency
    counsellor = (
        Counsellor.objects.select_related('user')
        .prefetch_related(
            'specializations',
            'therapy_approaches',
            'languages',
            'age_groups',
            'certifications'
        )
        .get(user_id=request.user.id)
    )

    # Background verification (may not exist yet)
    background_verification = getattr(counsellor, 'background_verification', None)

    # Compute a simple satisfaction percentage (rating out of 5)
    satisfaction_percent = 0
    if counsellor.rating and counsellor.rating > 0:
        try:
            satisfaction_percent = int((counsellor.rating / 5) * 100)
        except Exception:
            satisfaction_percent = 0

    context = {
        'counsellor': counsellor,
        'user': request.user,
        'background_verification': background_verification,
        'certifications': counsellor.certifications.all(),
        'satisfaction_percent': satisfaction_percent,
        'specializations': counsellor.specializations.all(),
        'therapy_approaches': counsellor.therapy_approaches.all(),
        'languages': counsellor.languages.all(),
        'age_groups': counsellor.age_groups.all(),
    }

    return render(request, 'therapists/counsellor_profile.html', context)


@login_required
@require_http_methods(["POST"])
def upload_counsellor_profile_picture(request):
    """
    Handle profile picture upload for counsellors via AJAX.
    """
    # Check if user is a counsellor
    if not hasattr(request.user, 'counsellor'):
        return JsonResponse({
            'success': False, 
            'error': 'Only counsellors can upload profile pictures.'
        }, status=403)
    
    # Check if file was uploaded
    if 'profile_picture' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'No file uploaded.'
        }, status=400)
    
    uploaded_file = request.FILES['profile_picture']
    
    # Validate file type
    allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    file_extension = uploaded_file.name.split('.')[-1].lower()
    
    if file_extension not in allowed_extensions:
        return JsonResponse({
            'success': False,
            'error': f'Invalid file type. Allowed types: {", ".join(allowed_extensions)}'
        }, status=400)
    
    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5MB in bytes
    if uploaded_file.size > max_size:
        return JsonResponse({
            'success': False,
            'error': 'File size too large. Maximum size is 5MB.'
        }, status=400)
    
    try:
        # Delete old profile picture if it exists
        if request.user.profile_picture:
            old_picture_path = request.user.profile_picture.path
            if os.path.exists(old_picture_path):
                os.remove(old_picture_path)
        
        # Save the new profile picture
        request.user.profile_picture = uploaded_file
        request.user.save(update_fields=['profile_picture', 'updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': 'Profile picture updated successfully!',
            'profile_picture_url': request.user.profile_picture.url
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to upload profile picture: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def update_counsellor_profile(request):
    """
    Handle counselor profile information updates via AJAX.
    """
    # Check if user is a counsellor
    if not hasattr(request.user, 'counsellor'):
        return JsonResponse({
            'success': False, 
            'error': 'Only counsellors can update their profile.'
        }, status=403)
    
    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data.'
        }, status=400)
    
    try:
        user = request.user
        counsellor = user.counsellor
        
        # Update user fields
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        phone = data.get('phone', '').strip()
        
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if phone:
            user.phone = phone
        
        user.save(update_fields=['first_name', 'last_name', 'phone', 'updated_at'])
        
        # Update counsellor fields
        session_fee = data.get('session_fee')
        meet_link = data.get('meet_link', '').strip()
        professional_bio = data.get('professional_bio', '').strip()
        
        if session_fee is not None:
            try:
                session_fee_decimal = Decimal(str(session_fee))
                if session_fee_decimal >= 0:
                    counsellor.session_fee = session_fee_decimal
            except (ValueError, InvalidOperation):
                pass
        
        if meet_link:
            counsellor.google_meet_link = meet_link
        
        if professional_bio:
            # Update both fields to maintain consistency
            counsellor.professional_experience = professional_bio
            counsellor.about_me = professional_bio
        
        counsellor.save(update_fields=[
            'session_fee', 
            'google_meet_link', 
            'professional_experience',
            'about_me',
            'updated_at'
        ])
        
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully!',
            'data': {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'session_fee': str(counsellor.session_fee),
                'meet_link': counsellor.google_meet_link,
                'professional_bio': counsellor.professional_experience or counsellor.about_me
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to update profile: {str(e)}'
        }, status=500)


def _parse_iso_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _parse_time_value(value):
    if not value:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def _serialize_slot(slot):
    return {
        "id": slot.id,
        "date": slot.date.isoformat(),
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M"),
        "is_booked": slot.is_booked,
    }


@login_required
@require_http_methods(["GET", "POST"])
def counsellor_availability_api(request):
    if not hasattr(request.user, 'counsellor'):
        return JsonResponse({'success': False, 'error': 'Only counsellors can manage availability.'}, status=403)

    counsellor = request.user.counsellor

    if request.method == "GET":
        range_start = _parse_iso_date(request.GET.get("start"))
        range_end = _parse_iso_date(request.GET.get("end"))

        slots_qs = counsellor.availability_slots.all()
        if range_start:
            slots_qs = slots_qs.filter(date__gte=range_start)
        if range_end:
            slots_qs = slots_qs.filter(date__lte=range_end)

        slots_data = [_serialize_slot(slot) for slot in slots_qs]
        return JsonResponse({
            "success": True,
            "slots": slots_data,
            "session_duration": counsellor.default_session_duration,
            "break_duration": counsellor.default_break_duration,
            "profile_visible": counsellor.is_available,
            "start_time": counsellor.available_from.strftime("%H:%M") if counsellor.available_from else "09:00",
            "end_time": counsellor.available_to.strftime("%H:%M") if counsellor.available_to else "18:00",
        })

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid payload.'}, status=400)

    session_duration = int(payload.get("session_duration") or counsellor.default_session_duration or 45)
    break_duration = int(payload.get("break_duration") or counsellor.default_break_duration or 5)
    profile_visible = bool(payload.get("profile_visible", True))
    slots_payload = payload.get("slots", [])
    range_start = _parse_iso_date(payload.get("range_start"))
    range_end = _parse_iso_date(payload.get("range_end"))

    if not range_start or not range_end:
        if slots_payload:
            dates = [_parse_iso_date(slot.get("date")) for slot in slots_payload if _parse_iso_date(slot.get("date"))]
            if dates:
                range_start = min(dates)
                range_end = max(dates)
        if not range_start or not range_end:
            today = date.today()
            range_start = today
            range_end = today + timedelta(days=7)

    valid_slots = []
    today = date.today()

    for slot in slots_payload:
        slot_date = _parse_iso_date(slot.get("date"))
        slot_start = _parse_time_value(slot.get("start_time"))
        slot_end = _parse_time_value(slot.get("end_time"))

        if not slot_date or not slot_start:
            continue
        if slot_date < today:
            continue

        calculated_end = (datetime.combine(slot_date, slot_start) + timedelta(minutes=session_duration)).time()
        slot_end = slot_end or calculated_end

        valid_slots.append({
            "date": slot_date,
            "start_time": slot_start,
            "end_time": slot_end,
        })

    existing_qs = counsellor.availability_slots.filter(date__gte=range_start, date__lte=range_end)
    existing_map = {(slot.date, slot.start_time): slot for slot in existing_qs}
    incoming_keys = {(slot["date"], slot["start_time"]) for slot in valid_slots}

    for slot in valid_slots:
        slot_obj = existing_map.get((slot["date"], slot["start_time"]))
        if slot_obj:
            updates = []
            if slot_obj.end_time != slot["end_time"]:
                slot_obj.end_time = slot["end_time"]
                updates.append("end_time")
            if slot_obj.duration_minutes != session_duration:
                slot_obj.duration_minutes = session_duration
                updates.append("duration_minutes")
            if updates:
                slot_obj.save(update_fields=updates + ["updated_at"])
        else:
            CounsellorAvailability.objects.create(
                counsellor=counsellor,
                date=slot["date"],
                start_time=slot["start_time"],
                end_time=slot["end_time"],
                duration_minutes=session_duration,
            )

    for key, slot in existing_map.items():
        if key not in incoming_keys and not slot.is_booked:
            slot.delete()

    future_slots = counsellor.availability_slots.filter(date__gte=today).order_by("date", "start_time")
    has_future_availability = future_slots.filter(is_booked=False).exists()

    if future_slots.exists():
        counsellor.available_from = future_slots.first().start_time
        counsellor.available_to = future_slots.last().end_time

    counsellor.default_session_duration = session_duration
    counsellor.default_break_duration = break_duration
    counsellor.is_available = profile_visible and has_future_availability
    counsellor.save(update_fields=[
        "default_session_duration",
        "default_break_duration",
        "available_from",
        "available_to",
        "is_available",
        "updated_at",
    ])

    refreshed_slots = counsellor.availability_slots.filter(date__gte=range_start, date__lte=range_end)
    return JsonResponse({
        "success": True,
        "slots": [_serialize_slot(slot) for slot in refreshed_slots],
        "session_duration": counsellor.default_session_duration,
        "break_duration": counsellor.default_break_duration,
        "profile_visible": counsellor.is_available,
        "start_time": counsellor.available_from.strftime("%H:%M") if counsellor.available_from else "09:00",
        "end_time": counsellor.available_to.strftime("%H:%M") if counsellor.available_to else "18:00",
    })


@login_required
def counsellor_manage_slots(request):
    """Render the counsellor weekly availability management page.

    Currently this view only serves the static template containing the front-end logic
    for selecting time slots. Later you can extend it to:
      - Persist selected slots to a model (e.g., Availability / Slot model)
      - Preload existing availability into the template context so JS can mark them
      - Respect counsellor-specific working hours / blackout dates
      - Handle AJAX POST for saving slots instead of the current simulated save
    """
    if not hasattr(request.user, 'counsellor'):
        messages.error(request, 'Only counsellors can manage availability.')
        return redirect('therapists')

    # Placeholder context for future extensions
    context = {
        'counsellor': request.user.counsellor,
        # Example structure you might later fill from DB:
        # 'existing_slots': [
        #     # {'date': '2025-11-25', 'start': '9:00 AM', 'end': '9:45 AM'},
        # ]
    }
    return render(request, 'therapists/counsellor_manage_slots.html', context)


@require_http_methods(["GET"])
def public_counsellor_availability(request, counsellor_id):
    counsellor = get_object_or_404(
        Counsellor,
        user_id=counsellor_id,
        is_active=True,
        user__is_approved=True,
    )

    selected_date = _parse_iso_date(request.GET.get("date"))
    if not selected_date:
        return JsonResponse({'success': False, 'error': 'Please provide a valid date.'}, status=400)

    min_booking_date = date.today() + timedelta(days=3)
    if selected_date < min_booking_date:
        return JsonResponse({'success': False, 'error': 'Appointments must be booked at least 3 days in advance.'}, status=400)

    slots = counsellor.availability_slots.filter(
        date=selected_date,
        is_booked=False,
    ).order_by("start_time")

    return JsonResponse({
        "success": True,
        "slots": [_serialize_slot(slot) for slot in slots],
        "session_duration": counsellor.default_session_duration,
        "min_booking_date": min_booking_date.isoformat(),
    })
