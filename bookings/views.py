import json
from datetime import datetime, date, timedelta
from decimal import Decimal

import razorpay
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Counsellor, Client
from therapists.models import CounsellorAvailability
from .models import Booking, Payment


def _parse_time_slot(time_str: str):
    """Parse HH:MM formatted strings safely."""
    try:
        return datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
        return None


def _validate_session_date(date_str: str):
    try:
        parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None

    if parsed_date < date.today():
        return None

    return parsed_date


@login_required
@require_POST
def create_booking(request):
    if not hasattr(request.user, 'client'):
        return JsonResponse({'success': False, 'error': 'Only clients can book sessions.'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid payload.'}, status=400)

    counsellor_id = payload.get('counsellor_id')
    session_date = _validate_session_date(payload.get('session_date'))
    session_time = _parse_time_slot(payload.get('session_time'))
    duration = payload.get('session_duration') or 50
    client_notes = payload.get('client_notes', '').strip()

    if not counsellor_id or not session_date or not session_time:
        return JsonResponse(
            {'success': False, 'error': 'Please select a valid date and time for your session.'},
            status=400,
        )

    min_booking_date = date.today() + timedelta(days=3)
    if session_date < min_booking_date:
        return JsonResponse(
            {'success': False, 'error': 'Appointments must be booked at least 3 days in advance.'},
            status=400,
        )

    try:
        counsellor = Counsellor.objects.get(user_id=counsellor_id, is_active=True, user__is_approved=True)
    except Counsellor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Counsellor not found or inactive.'}, status=404)

    client = request.user.client

    session_fee = counsellor.session_fee or Decimal('0.00')

    try:
        with transaction.atomic():
            try:
                availability_slot = CounsellorAvailability.objects.select_for_update().get(
                    counsellor=counsellor,
                    date=session_date,
                    start_time=session_time,
                )
            except CounsellorAvailability.DoesNotExist:
                return JsonResponse(
                    {'success': False, 'error': 'This counsellor is not available at the selected time.'},
                    status=400,
                )

            if availability_slot.is_booked:
                return JsonResponse(
                    {'success': False, 'error': 'This slot has already been booked. Please choose another time.'},
                    status=409,
                )

            duration = availability_slot.duration_minutes or duration

            booking = Booking.objects.create(
                client=client,
                counsellor=counsellor,
                session_date=session_date,
                session_time=session_time,
                session_duration=duration,
                session_fee=session_fee,
                client_notes=client_notes,
                google_meet_link=counsellor.google_meet_link,
                availability_slot=availability_slot,
            )

            payment = Payment.objects.create(
                booking=booking,
                amount=session_fee,
                currency='INR',
                payment_method=Payment.METHOD_RAZORPAY,
            )

            availability_slot.is_booked = True
            availability_slot.save(update_fields=['is_booked', 'updated_at'])

            razorpay_client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            
            # Ensure amount is at least 1 INR (100 paise) for Razorpay
            amount_in_paise = int(session_fee * 100)
            if amount_in_paise < 100:
                return JsonResponse(
                    {'success': False, 'error': 'Minimum payment amount is ₹1.00'},
                    status=400,
                )
            
            order = razorpay_client.order.create({
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": booking.booking_reference,
                "notes": {
                "booking_reference": booking.booking_reference,
                "client": client.user.get_full_name(),
                "counsellor": counsellor.user.get_full_name(),
                },
            })
            



            payment.razorpay_order_id = order.get('id')
            payment.save(update_fields=['razorpay_order_id', 'updated_at'])
            
            # Log order creation for debugging
            print(f"Razorpay order created: {order.get('id')} for booking {booking.booking_reference}, amount: {amount_in_paise} paise")

    except razorpay.errors.BadRequestError as exc:
        print(f"Razorpay BadRequestError: {str(exc)}")
        return JsonResponse(
            {'success': False, 'error': 'Unable to initialise payment. Please try again later.', 'details': str(exc)},
            status=502,
        )
    except razorpay.errors.ServerError as exc:
        print(f"Razorpay ServerError: {str(exc)}")
        return JsonResponse(
            {'success': False, 'error': 'Payment gateway error. Please try again later.', 'details': str(exc)},
            status=502,
        )
    except Exception as exc:  # pragma: no cover - general safeguard
        print(f"Unexpected error creating booking: {str(exc)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)

    return JsonResponse(
        {
            'success': True,
            'booking': {
                'reference': booking.booking_reference,
                'session_date': booking.session_date.isoformat(),
                'session_time': booking.session_time.strftime('%H:%M'),
                'session_fee': str(booking.session_fee),
            },
            'order': {
                'id': order.get('id'),
                'amount': order.get('amount'),
                'currency': order.get('currency'),
            },
            'razorpay_key': settings.RAZORPAY_KEY_ID,
            'client': {
                'name': client.user.get_full_name(),
                'email': client.user.email,
                'phone': client.user.phone,
            },
        }
    )


@login_required
@require_POST
def verify_payment(request):
    if not hasattr(request.user, 'client'):
        return JsonResponse({'success': False, 'error': 'Only clients can verify payments.'}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid payload.'}, status=400)

    booking_reference = payload.get('booking_reference')
    razorpay_order_id = payload.get('razorpay_order_id')
    razorpay_payment_id = payload.get('razorpay_payment_id')
    razorpay_signature = payload.get('razorpay_signature')

    if not all([booking_reference, razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return JsonResponse({'success': False, 'error': 'Incomplete payment details.'}, status=400)

    try:
        payment = Payment.objects.select_related('booking', 'booking__client').get(
            booking__booking_reference=booking_reference,
            booking__client=request.user.client,
        )
    except Payment.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Payment record not found.'}, status=404)

    # Verify signature
    try:
        razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError as e:
        payment.mark_failed(f'Signature verification failed: {str(e)}')
        payment.booking.payment_status = Booking.PAYMENT_FAILED
        payment.booking.save(update_fields=['payment_status', 'updated_at'])
        return JsonResponse({'success': False, 'error': 'Payment verification failed. Please contact support.'}, status=400)
    except Exception as e:
        payment.mark_failed(f'Verification error: {str(e)}')
        payment.booking.payment_status = Booking.PAYMENT_FAILED
        payment.booking.save(update_fields=['payment_status', 'updated_at'])
        return JsonResponse({'success': False, 'error': 'Payment verification error. Please contact support.'}, status=500)

    with transaction.atomic():
        payment.mark_success(razorpay_payment_id, razorpay_signature, payload)
        payment.booking.payment_status = Booking.PAYMENT_PAID
        payment.booking.status = Booking.STATUS_CONFIRMED
        payment.booking.confirmed_at = timezone.now()
        payment.booking.save(update_fields=['payment_status', 'status', 'confirmed_at', 'updated_at'])

        # Increment counters for client and counsellor
        client = payment.booking.client
        counsellor = payment.booking.counsellor

        Client.objects.filter(pk=client.pk).update(
            total_sessions=F('total_sessions') + 1,
            last_session_date=payment.booking.session_datetime,
        )

        has_existing_paid_session = Booking.objects.filter(
            counsellor=counsellor,
            client=client,
            payment_status=Booking.PAYMENT_PAID,
        ).exclude(pk=payment.booking.pk).exists()

        counsellor_updates = {'total_sessions': F('total_sessions') + 1}
        if not has_existing_paid_session:
            counsellor_updates['total_clients'] = F('total_clients') + 1

        Counsellor.objects.filter(pk=counsellor.pk).update(**counsellor_updates)

    return JsonResponse({'success': True, 'message': 'Payment verified successfully.'})


@login_required
@require_POST
def payment_failed(request):
    """Capture failures reported by Razorpay Checkout so support can follow-up."""
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid payload.'}, status=400)

    booking_reference = payload.get('booking_reference')
    error = payload.get('error', {})

    if not booking_reference:
        return JsonResponse({'success': False, 'error': 'Missing booking reference.'}, status=400)

    try:
        payment = Payment.objects.select_related('booking').get(booking__booking_reference=booking_reference)
    except Payment.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Payment record not found.'}, status=404)

    error_description = error.get('description') if isinstance(error, dict) else str(error)
    error_code = error.get('code') if isinstance(error, dict) else None
    error_source = error.get('source') if isinstance(error, dict) else None
    error_step = error.get('step') if isinstance(error, dict) else None
    error_reason = error.get('reason') if isinstance(error, dict) else None
    
    # Log detailed error information
    print(f"Payment failed for booking {booking_reference}:")
    print(f"  Description: {error_description}")
    print(f"  Code: {error_code}")
    print(f"  Source: {error_source}")
    print(f"  Step: {error_step}")
    print(f"  Reason: {error_reason}")
    print(f"  Full error: {error}")
    
    payment.mark_failed(error_description or 'Payment failed.')
    payment.booking.payment_status = Booking.PAYMENT_FAILED
    payment.booking.save(update_fields=['payment_status', 'updated_at'])

    slot = payment.booking.availability_slot
    if slot and slot.is_booked and payment.booking.payment_status != Booking.PAYMENT_PAID:
        slot.is_booked = False
        slot.save(update_fields=['is_booked', 'updated_at'])

    return JsonResponse({'success': True})

