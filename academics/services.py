from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum

from accounts.models import StudentProfile
from .models import (
    Grade,
    PromotionRun,
    StudentYearResult,
    SubjectYearResult,
)


PASS_PERCENTAGE = Decimal("50.00")


def _round_percentage(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def calculate_promotion_results(academic_year, created_by=None):
    students = StudentProfile.objects.select_related(
        "user",
        "classroom",
        "section",
    ).all()

    totals = {
        "total_students": 0,
        "promoted_count": 0,
        "failed_count": 0,
        "needs_review_count": 0,
    }

    for student in students:
        totals["total_students"] += 1

        grades_by_subject = (
            Grade.objects.filter(
                student=student,
                date__gte=academic_year.start_date,
                date__lte=academic_year.end_date,
            )
            .values("subject_id")
            .annotate(
                total_score=Sum("score"),
                total_max_score=Sum("max_score"),
            )
        )

        SubjectYearResult.objects.filter(
            student=student,
            academic_year=academic_year,
        ).delete()

        percentages = []
        failed_subjects_count = 0
        notes = []

        for subject_result in grades_by_subject:
            total_score = subject_result["total_score"] or Decimal("0")
            total_max_score = subject_result["total_max_score"] or Decimal("0")
            subject_id = subject_result["subject_id"]

            if total_max_score <= 0:
                notes.append(
                    f"Subject #{subject_id} ignored because total max score is not valid."
                )
                continue

            percentage = _round_percentage((total_score / total_max_score) * 100)
            is_failed = percentage < PASS_PERCENTAGE

            if is_failed:
                failed_subjects_count += 1

            percentages.append(percentage)

            SubjectYearResult.objects.update_or_create(
                student=student,
                subject_id=subject_id,
                academic_year=academic_year,
                defaults={
                    "average_score": total_score,
                    "max_score": total_max_score,
                    "percentage": percentage,
                    "is_failed": is_failed,
                },
            )

        if not percentages:
            average_percentage = None
            status = StudentYearResult.Status.NEEDS_REVIEW
            notes.append("No valid grades were found for this academic year.")
        else:
            average_percentage = _round_percentage(
                sum(percentages, Decimal("0")) / Decimal(len(percentages))
            )

            if average_percentage < PASS_PERCENTAGE:
                status = StudentYearResult.Status.FAILED
                notes.append("General average is below 50%.")
            elif failed_subjects_count > 2:
                status = StudentYearResult.Status.FAILED
                notes.append("Student failed in more than two subjects.")
            else:
                status = StudentYearResult.Status.PROMOTED
                notes.append("Student meets promotion rules.")

        StudentYearResult.objects.update_or_create(
            student=student,
            academic_year=academic_year,
            defaults={
                "average_percentage": average_percentage,
                "failed_subjects_count": failed_subjects_count,
                "status": status,
                "is_published": False,
                "published_at": None,
                "notes": " ".join(notes),
            },
        )

        if status == StudentYearResult.Status.PROMOTED:
            totals["promoted_count"] += 1
        elif status == StudentYearResult.Status.FAILED:
            totals["failed_count"] += 1
        else:
            totals["needs_review_count"] += 1

    return PromotionRun.objects.create(
        academic_year=academic_year,
        created_by=created_by if getattr(created_by, "is_authenticated", False) else None,
        **totals,
    )
