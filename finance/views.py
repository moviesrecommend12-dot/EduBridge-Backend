from decimal import Decimal
import uuid
from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from notifications.models import Notification
from notifications.services import notify_student_and_parents
import stripe
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import ParentProfile, ParentStudentLink
from .models import FeeInvoice, Payment, Receipt
from .serializers import (
    FeeInvoiceSerializer,
    PaymentSerializer,
    ReceiptSerializer,
)

stripe.api_key = settings.STRIPE_SECRET_KEY


def get_parent_profile_or_error(user):
    if user.role != 'PARENT':
        return None, Response(
            {'detail': 'Only parents can access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        return user.parent_profile, None
    except ParentProfile.DoesNotExist:
        return None, Response(
            {'detail': 'Parent profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


def parent_can_access_invoice(parent_profile, invoice):
    return ParentStudentLink.objects.filter(
        parent=parent_profile,
        student=invoice.student
    ).exists()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_invoices(request):
    parent_profile, error = get_parent_profile_or_error(request.user)
    if error:
        return error

    student_ids = ParentStudentLink.objects.filter(
        parent=parent_profile
    ).values_list('student_id', flat=True)

    invoices = FeeInvoice.objects.select_related(
        'student',
        'student__user',
    ).filter(student_id__in=student_ids)

    serializer = FeeInvoiceSerializer(invoices, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_invoices(request, student_id):
    parent_profile, error = get_parent_profile_or_error(request.user)
    if error:
        return error

    allowed = ParentStudentLink.objects.filter(
        parent=parent_profile,
        student_id=student_id,
    ).exists()

    if not allowed:
        return Response(
            {'detail': 'You are not allowed to access this student invoices.'},
            status=status.HTTP_403_FORBIDDEN
        )

    invoices = FeeInvoice.objects.select_related(
        'student',
        'student__user',
    ).filter(student_id=student_id)

    serializer = FeeInvoiceSerializer(invoices, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_checkout_session(request, invoice_id):
    parent_profile, error = get_parent_profile_or_error(request.user)
    if error:
        return error

    try:
        invoice = FeeInvoice.objects.select_related('student', 'student__user').get(id=invoice_id)
    except FeeInvoice.DoesNotExist:
        return Response(
            {'detail': 'Invoice not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not parent_can_access_invoice(parent_profile, invoice):
        return Response(
            {'detail': 'You are not allowed to pay this invoice.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if invoice.status == FeeInvoice.Status.PAID:
        return Response(
            {'detail': 'Invoice is already paid.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not settings.STRIPE_SECRET_KEY or 'put_your_key_here' in settings.STRIPE_SECRET_KEY:
        return Response(
            {'detail': 'Stripe test secret key is not configured.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    amount_cents = int(Decimal(invoice.amount) * 100)

    payment = Payment.objects.create(
        invoice=invoice,
        parent=parent_profile,
        amount=invoice.amount,
        currency=invoice.currency,
        status=Payment.Status.PENDING,
    )

    session = stripe.checkout.Session.create(
        mode='payment',
        payment_method_types=['card'],
        line_items=[
            {
                'price_data': {
                    'currency': invoice.currency,
                    'product_data': {
                        'name': invoice.title,
                        'description': invoice.description or f'Invoice #{invoice.id}',
                    },
                    'unit_amount': amount_cents,
                },
                'quantity': 1,
            }
        ],
        success_url=f"{settings.FRONTEND_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_CANCEL_URL}?invoice_id={invoice.id}",
        metadata={
            'invoice_id': str(invoice.id),
            'payment_id': str(payment.id),
            'parent_id': str(parent_profile.id),
            'student_id': str(invoice.student.id),
        },
    )

    payment.stripe_checkout_session_id = session.id
    payment.save()

    return Response({
        'checkout_session_id': session.id,
        'checkout_url': session.url,
        'payment': PaymentSerializer(payment).data,
    }, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return Response({'detail': 'Invalid payload.'}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response({'detail': 'Invalid signature.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        event = request.data

    if event.get('type') == 'checkout.session.completed':
        session = event['data']['object']
        session_id = session.get('id')
        payment_intent_id = session.get('payment_intent', '')

        try:
            payment = Payment.objects.select_related('invoice').get(
                stripe_checkout_session_id=session_id
            )
        except Payment.DoesNotExist:
            return Response({'detail': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)

        payment.status = Payment.Status.PAID
        payment.stripe_payment_intent_id = payment_intent_id or ''
        payment.paid_at = timezone.now()
        payment.save()

        invoice = payment.invoice
        invoice.status = FeeInvoice.Status.PAID
        invoice.save()

        Receipt.objects.get_or_create(
            payment=payment,
            defaults={
                'receipt_number': f"REC-{uuid.uuid4().hex[:10].upper()}"
            }
        )

    return Response({'received': True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_checkout_payment(request):
    parent_profile, error = get_parent_profile_or_error(request.user)
    if error:
        return error

    session_id = request.data.get('session_id')

    if not session_id:
        return Response(
            {'detail': 'session_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        payment = Payment.objects.select_related(
            'invoice',
            'invoice__student',
        ).get(
            stripe_checkout_session_id=session_id,
            parent=parent_profile
        )
    except Payment.DoesNotExist:
        return Response(
            {'detail': 'Payment not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if payment.status == Payment.Status.PAID:
        receipt = Receipt.objects.filter(payment=payment).first()

        return Response({
            'detail': 'Payment was already confirmed.',
            'payment': PaymentSerializer(payment).data,
            'receipt': {
                'id': receipt.id if receipt else None,
                'receipt_number': receipt.receipt_number if receipt else None,
            }
        })

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError as e:
        return Response(
            {'detail': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

    if session.payment_status != 'paid':
        return Response(
            {
                'detail': 'Payment is not completed yet.',
                'payment_status': session.payment_status,
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    payment.status = Payment.Status.PAID
    payment.stripe_payment_intent_id = session.payment_intent or ''
    payment.paid_at = timezone.now()
    payment.save()

    invoice = payment.invoice
    invoice.status = FeeInvoice.Status.PAID
    invoice.save()

    receipt, created = Receipt.objects.get_or_create(
        payment=payment,
        defaults={
            'receipt_number': f"REC-{uuid.uuid4().hex[:10].upper()}"
        }
    )

    notify_student_and_parents(
        student=invoice.student,
        notification_type=Notification.Type.PAYMENT,
        title='Payment completed',
        message=(
            f'Invoice "{invoice.title}" was paid successfully. '
            f'Amount: {invoice.amount} {invoice.currency.upper()}'
        ),
        related_object_type='Payment',
        related_object_id=payment.id,
        template_key='payment_completed',
        context={
            'invoice_title': invoice.title,
            'amount': invoice.amount,
            'currency': invoice.currency.upper(),
        },
    )

    return Response({
        'detail': 'Payment confirmed successfully.',
        'payment': PaymentSerializer(payment).data,
        'receipt': {
            'id': receipt.id,
            'receipt_number': receipt.receipt_number,
            'issued_at': receipt.issued_at,
        }
    })
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_payments(request):
    parent_profile, error = get_parent_profile_or_error(request.user)
    if error:
        return error

    payments = Payment.objects.select_related(
        'invoice',
        'invoice__student',
        'invoice__student__user',
        'parent',
    ).filter(
        parent=parent_profile
    )

    serializer = PaymentSerializer(payments, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_receipts(request):
    parent_profile, error = get_parent_profile_or_error(request.user)
    if error:
        return error

    receipts = Receipt.objects.select_related(
        'payment',
        'payment__invoice',
        'payment__invoice__student',
        'payment__invoice__student__user',
        'payment__parent',
    ).filter(
        payment__parent=parent_profile
    ).order_by('-issued_at')

    serializer = ReceiptSerializer(receipts, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_receipt_detail(request, receipt_id):
    parent_profile, error = get_parent_profile_or_error(request.user)
    if error:
        return error

    try:
        receipt = Receipt.objects.select_related(
            'payment',
            'payment__invoice',
            'payment__invoice__student',
            'payment__invoice__student__user',
            'payment__parent',
        ).get(
            id=receipt_id,
            payment__parent=parent_profile,
        )
    except Receipt.DoesNotExist:
        return Response(
            {'detail': 'Receipt not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = ReceiptSerializer(receipt)
    return Response(serializer.data)

def payment_success_page(request):
    return render(
        request,
        'finance/payment_success.html',
        {
            'session_id': request.GET.get('session_id', '')
        }
    )


def payment_cancel_page(request):
    return render(
        request,
        'finance/payment_cancel.html',
        {
            'invoice_id': request.GET.get('invoice_id', '')
        }
    )
