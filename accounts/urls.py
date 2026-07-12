from django.urls import path
from .views import (
    CustomTokenObtainPairView,
    me,
    parent_register,
    student_profile,
    parent_children,
    parent_child_detail,
)

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('me/', me, name='me'),

    path('parent/register/', parent_register, name='parent-register'),
    path('parent/children/', parent_children, name='parent-children'),
    path('parent/children/<int:student_id>/', parent_child_detail, name='parent-child-detail'),

    path('student/profile/', student_profile, name='student-profile'),
]