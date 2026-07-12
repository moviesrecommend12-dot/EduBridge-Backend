from django.contrib import admin
from .models import FeeInvoice, Payment, Receipt


@admin.register(FeeInvoice)
class FeeInvoiceAdmin(admin.ModelAdmin):
    list_display = ('student', 'title', 'amount', 'currency', 'due_date', 'status', 'created_at')
    list_filter = ('status', 'currency', 'due_date')
    search_fields = ('student__student_code', 'student__user__username', 'title')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'parent', 'amount', 'currency', 'status', 'created_at', 'paid_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = (
        'invoice__title',
        'invoice__student__student_code',
        'parent__user__username',
        'stripe_checkout_session_id',
        'stripe_payment_intent_id',
    )


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'payment', 'issued_at')
    search_fields = ('receipt_number', 'payment__invoice__title')