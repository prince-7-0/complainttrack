from django.contrib import admin
from .models import Complaint

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display   = ('id', 'title', 'submitted_by', 'priority', 'status', 'created_at')
    list_filter    = ('status', 'priority')
    search_fields  = ('title', 'submitted_by__username', 'location')
    list_editable  = ('status',)
    readonly_fields = ('created_at', 'updated_at')