from django.urls import path

from .views import (
    parent_invoices,
    parent_child_invoices,
    create_checkout_session,
    confirm_checkout_payment,
    parent_payments,
    parent_receipts,
    parent_receipt_detail,
    stripe_webhook,
)

urlpatterns = [
    path(
        'parent/invoices/',
        parent_invoices,
        name='parent-invoices'
    ),
    path(
        'parent/children/<int:student_id>/invoices/',
        parent_child_invoices,
        name='parent-child-invoices'
    ),
    path(
        'parent/invoices/<int:invoice_id>/create-checkout-session/',
        create_checkout_session,
        name='create-checkout-session'
    ),
    path(
        'parent/payments/confirm/',
        confirm_checkout_payment,
        name='confirm-checkout-payment'
    ),
    path(
        'parent/payments/',
        parent_payments,
        name='parent-payments'
    ),
    path(
        'parent/receipts/',
        parent_receipts,
        name='parent-receipts'
    ),
    path(
        'parent/receipts/<int:receipt_id>/',
        parent_receipt_detail,
        name='parent-receipt-detail'
    ),
    path(
        'stripe/webhook/',
        stripe_webhook,
        name='stripe-webhook'
    ),
]