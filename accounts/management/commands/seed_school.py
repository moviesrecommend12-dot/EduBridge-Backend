import random
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User, StudentProfile, ParentProfile, TeacherProfile, ParentStudentLink
from academics.models import ClassRoom, Section, Subject, TeachingAssignment

PASSWORD = "Passw0rd123"

# الصفوف حسب المنهج السوري (حلقة أولى وثانية من التعليم الأساسي + ثانوي)
CLASSROOMS = [
    "الصف الأول", "الصف الثاني", "الصف الثالث", "الصف الرابع", "الصف الخامس",
    "الصف السادس", "الصف السابع", "الصف الثامن", "الصف التاسع",
    "الصف العاشر", "الصف الحادي عشر", "الصف الثاني عشر",
]
SECTIONS = ["أ", "ب", "ج"]

# مواد المنهج السوري مع معلم مختص لكل مادة
SUBJECTS_AND_TEACHERS = [
    ("اللغة العربية", "TA", [("محمد", "الأحمد"), ("سناء", "المصري")]),
    ("اللغة الإنجليزية", "EN", [("ريم", "العبد الله"), ("سامر", "قاسمية")]),
    ("اللغة الفرنسية", "FR", [("نادين", "شحادة")]),
    ("الرياضيات", "MA", [("أحمد", "الخطيب"), ("ديالا", "حوراني")]),
    ("الفيزياء", "PH", [("خالد", "حمدان")]),
    ("الكيمياء", "CH", [("لمى", "سلوم")]),
    ("علم الأحياء", "BI", [("رنا", "الحلبي")]),
    ("التربية الوطنية والاجتماعية", "CIV", [("محمود", "شاهين")]),
    ("التاريخ", "HIS", [("وائل", "ديب")]),
    ("الجغرافيا", "GEO", [("لينا", "قاسم")]),
    ("التربية الدينية", "REL", [("عبد الرحمن", "نجم")]),
    ("الحاسوب", "CS", [("فادي", "برهوم")]),
    ("التربية الفنية", "ART", [("هبة", "زيدان")]),
    ("التربية الرياضية", "PE", [("طارق", "عودة")]),
]

# أسماء طلاب واقعية (سورية/شامية) مع نسب مرجّح ذكر/أنثى
STUDENT_MALE = ["عمر", "يوسف", "زيد", "كريم", "آدم", "حمزة", "طه", "علاء", "باسل", "أنس", "قصي", "ياسين", "معاذ", "رامي", "فراس"]
STUDENT_FEMALE = ["ليان", "جنى", "مريم", "نور", "تالا", "دانة", "رهف", "لجين", "سيدرا", "ميرا", "جود", "شهد", "روان", "غنى", "يارا"]
FAMILY_NAMES = [
    "الحمصي", "النجار", "درويش", "العلي", "زيدان", "قنديل", "برهوم", "الشريف",
    "حداد", "سلامة", "عودة", "فرح", "الأتاسي", "المالكي", "الزعبي", "الخاني",
    "بيطار", "قباني", "الشماع", "دندشي", "طرابيشي", "الحكيم", "شربجي", "عجلاني",
]
FATHER_NAMES = ["محمد", "علي", "حسين", "إبراهيم", "سامي", "وليد", "فادي", "ماجد", "طارق", "بسام", "رامي", "أنس", "نبيل", "غسان", "فؤاد"]
MOTHER_NAMES = ["فاطمة", "سلمى", "هدى", "رانيا", "منى", "أمل", "سوسن", "غادة", "لبنى", "نجاح", "سهى", "ابتسام"]


class Command(BaseCommand):
    help = "ينشئ بيانات واقعية (مدير، معلمين، طلاب، أهالي) بمواد ومناهج تحاكي النظام السوري"

    def add_arguments(self, parser):
        parser.add_argument("--students-per-section", type=int, default=6, help="عدد الطلاب لكل شعبة")

    @transaction.atomic
    def handle(self, *args, **options):
        per_section = options["students_per_section"]

        # 1) المدير
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin", email="admin@edubridge.com", password=PASSWORD,
                first_name="غياث", last_name="مدير المدرسة", role=User.Role.ADMIN,
            )
            self.stdout.write(self.style.SUCCESS("تم إنشاء المدير: admin"))
        else:
            self.stdout.write("المدير موجود مسبقاً، تم تخطيه")

        # 2) الصفوف والشعب
        classrooms = []
        for cname in CLASSROOMS:
            cr, _ = ClassRoom.objects.get_or_create(name=cname, defaults={"grade_level": cname})
            classrooms.append(cr)
            for sname in SECTIONS:
                Section.objects.get_or_create(classroom=cr, name=sname)

        # 3) المواد + المعلمون
        subject_teacher_map = {}  # subject -> list[TeacherProfile]
        teacher_counter = 1
        for subj_name, code_prefix, teachers in SUBJECTS_AND_TEACHERS:
            subj, _ = Subject.objects.get_or_create(
                name=subj_name, defaults={"code": f"{code_prefix}{random.randint(100, 999)}"}
            )
            profiles = []
            for first, last in teachers:
                username = f"teacher{teacher_counter}"
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(
                        username=username, email=f"{username}@edubridge.com", password=PASSWORD,
                        first_name=first, last_name=last, role=User.Role.TEACHER,
                        phone=f"0991{teacher_counter:06d}",
                    )
                    profile = TeacherProfile.objects.create(
                        user=user, employee_code=f"T-{1000 + teacher_counter}", specialization=subj_name,
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f"معلم: {username} / {PASSWORD} ({first} {last} - {subj_name})"
                    ))
                else:
                    profile = User.objects.get(username=username).teacher_profile
                profiles.append(profile)
                teacher_counter += 1
            subject_teacher_map[subj.id] = (subj, profiles)

        # 4) ربط كل معلم بشعب متعددة من مادته (يدرّس أكثر من صف)
        for subj, profiles in subject_teacher_map.values():
            for cr in classrooms:
                sections = list(cr.sections.all())
                for sec in sections:
                    teacher = random.choice(profiles)
                    TeachingAssignment.objects.get_or_create(
                        teacher=teacher, classroom=cr, section=sec, subject=subj
                    )

        # 5) الطلاب وأولياء الأمور لكل شعبة
        student_num = 1
        parent_num = 1
        for cr in classrooms:
            for sec in cr.sections.all():
                for _ in range(per_section):
                    is_male = random.random() < 0.5
                    first = random.choice(STUDENT_MALE if is_male else STUDENT_FEMALE)
                    last = random.choice(FAMILY_NAMES)

                    s_username = f"student{student_num}"
                    if not User.objects.filter(username=s_username).exists():
                        s_user = User.objects.create_user(
                            username=s_username, email=f"{s_username}@edubridge.com", password=PASSWORD,
                            first_name=first, last_name=last, role=User.Role.STUDENT,
                            phone=f"0993{student_num:06d}",
                        )
                        student_profile = StudentProfile.objects.create(
                            user=s_user, student_code=f"S-{2000 + student_num}",
                            classroom=cr, section=sec, address="دمشق، سوريا",
                        )
                        self.stdout.write(self.style.SUCCESS(
                            f"طالب: {s_username} / {PASSWORD} ({first} {last} - {cr.name}/{sec.name})"
                        ))
                    else:
                        student_profile = User.objects.get(username=s_username).student_profile

                    # ولي أمر (أب أو أم) بنفس اسم العائلة
                    p_username = f"parent{parent_num}"
                    parent_is_father = random.random() < 0.7
                    p_first = random.choice(FATHER_NAMES) if parent_is_father else random.choice(MOTHER_NAMES)
                    relationship = "أب" if parent_is_father else "أم"
                    if not User.objects.filter(username=p_username).exists():
                        p_user = User.objects.create_user(
                            username=p_username, email=f"{p_username}@edubridge.com", password=PASSWORD,
                            first_name=p_first, last_name=last, role=User.Role.PARENT,
                            phone=f"0994{parent_num:06d}",
                        )
                        parent_profile = ParentProfile.objects.create(
                            user=p_user, national_id=f"99{parent_num:08d}", address="دمشق، سوريا",
                        )
                        self.stdout.write(self.style.SUCCESS(
                            f"ولي أمر: {p_username} / {PASSWORD} ({p_first} {last} - {relationship})"
                        ))
                    else:
                        parent_profile = User.objects.get(username=p_username).parent_profile

                    ParentStudentLink.objects.get_or_create(
                        parent=parent_profile, student=student_profile,
                        defaults={"relationship": relationship},
                    )

                    student_num += 1
                    parent_num += 1

        total_students = student_num - 1
        self.stdout.write(self.style.SUCCESS(
            f"\nتم الانتهاء: {len(CLASSROOMS)} صفوف × {len(SECTIONS)} شعب، "
            f"{len(SUBJECTS_AND_TEACHERS)} مادة، {teacher_counter - 1} معلم، "
            f"{total_students} طالب و{total_students} ولي أمر."
        ))
        self.stdout.write(self.style.SUCCESS(f"كلمة السر لكل الحسابات: {PASSWORD}"))