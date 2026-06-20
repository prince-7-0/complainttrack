from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Complaint(models.Model):
    STATUS_CHOICES = [
        ('open',     'Open'),
        ('assigned', 'Assigned'),
        ('resolved', 'Resolved'),
        ('canceled', 'Canceled'),
    ]
    PRIORITY_CHOICES = [
        ('low',      'Low'),
        ('medium',   'Medium'),
        ('high',     'High'),
        ('critical', 'Critical'),
    ]

    unique_id    = models.CharField(max_length=20, unique=True, blank=True)
    title        = models.CharField(max_length=200)
    description  = models.TextField()
    location     = models.CharField(max_length=200, blank=True)
    priority     = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_complaints')
    assigned_to  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_complaints')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    admin_notes  = models.TextField(blank=True)
    is_canceled  = models.BooleanField(default=False)

    def __str__(self):
        return f"[{self.status.upper()}] {self.title}"

    def save(self, *args, **kwargs):
        if not self.unique_id:
            date_str = timezone.now().strftime('%y%m%d')
            loc_raw  = ''.join(filter(str.isalpha, self.location or 'GEN'))
            loc_code = (loc_raw[:2] if len(loc_raw) >= 2 else loc_raw.ljust(2, 'X')).upper()
            base_id  = f"{date_str}{loc_code}"
            new_id   = base_id
            counter  = 1
            while Complaint.objects.filter(unique_id=new_id).exists():
                new_id = f"{date_str}{loc_code[0]}{counter}"
                counter += 1
            self.unique_id = new_id
        super().save(*args, **kwargs)

class ComplaintLog(models.Model):
    complaint    = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name='logs')
    action       = models.CharField(max_length=255)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    assigned_to  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='log_assignments')
    timestamp    = models.DateTimeField(auto_now_add=True)
    note         = models.TextField(blank=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.complaint.title}] {self.action}"