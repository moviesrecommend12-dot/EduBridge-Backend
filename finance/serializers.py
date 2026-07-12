from rest_framework import serializers
from .models import FeeInvoice, Payment, Receipt


class FeeInvoiceSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()

    class Meta:
        model = FeeInvoice
        fields = [
            'id',
            'student',
            'title',
            'description',
            'amount',
            'currency',
            'due_date',
            'status',
            'created_at',
        ]

    def get_student(self, obj):
        return {
            'id': obj.student.id,
            'student_code': obj.student.student_code,
            'name': obj.student.user.get_full_name() or obj.student.user.username,
        }


class PaymentSerializer(serializers.ModelSerializer):
    invoice = FeeInvoiceSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'invoice',
            'amount',
            'currency',
            'status',
            'stripe_checkout_session_id',
            'stripe_payment_intent_id',
            'created_at',
            'paid_at',
        ]


class ReceiptSerializer(serializers.ModelSerializer):
    payment = PaymentSerializer(read_only=True)

    class Meta:
        model = Receipt
        fields = [
            'id',
            'receipt_number',
            'payment',
            'issued_at',
        ]