from django.urls import path
from . import views

urlpatterns = [
    path('',                                views.login_view,        name='login'),
    path('login/',                          views.login_view,        name='login'),
    path('logout/',                         views.logout_view,       name='logout'),
    path('dashboard/',                      views.dashboard,         name='dashboard'),
    path('complaint/add/',                  views.add_complaint,     name='add_complaint'),
    path('complaint/<int:pk>/',             views.complaint_detail,  name='complaint_detail'),
    path('complaint/<int:pk>/update/',      views.update_complaint,  name='update_complaint'),
    path('complaint/<int:pk>/cancel/',      views.cancel_complaint,  name='cancel_complaint'),
    path('complaint/<int:pk>/assign/',      views.assign_complaint,  name='assign_complaint'),
    path('complaints/history/',             views.complaint_history, name='complaint_history'),
    path('admin-panel/add-engineer/',       views.add_engineer,      name='add_engineer'),
    path('export/csv/', views.export_complaints_csv, name='export_csv'),
]