from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Complaint, ComplaintLog
from .forms import ComplaintForm, StatusUpdateForm, AssignComplaintForm, NewEngineerForm


def is_admin(user):
    return user.is_staff


# ── LOGIN ──────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('dashboard')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'complaints/login.html')


# ── LOGOUT ─────────────────────────────────────────────
def logout_view(request):
    logout(request)
    return redirect('login')


# ── DASHBOARD ──────────────────────────────────────────
@login_required
def dashboard(request):
    status_filter   = request.GET.get('status', '')
    search_query    = request.GET.get('search', '').strip()
    sort_priority   = request.GET.get('sort', '')

    if request.user.is_staff:
        base_qs = Complaint.objects.all().order_by('-created_at')
    else:
        base_qs = Complaint.objects.filter(
            Q(submitted_by=request.user) | Q(assigned_to=request.user)
        ).distinct().order_by('-created_at')

    total      = base_qs.count()
    open_count = base_qs.filter(status='open').count()
    assigned   = base_qs.filter(status='assigned').count()
    resolved   = base_qs.filter(status='resolved').count()
    canceled   = base_qs.filter(status='canceled').count()

    filtered_qs = base_qs
    if status_filter and status_filter != 'all':
        filtered_qs = filtered_qs.filter(status=status_filter)

    if search_query:
        filtered_qs = filtered_qs.filter(
            Q(title__icontains=search_query) | Q(unique_id__icontains=search_query)
        )

    # ── Priority Sorting ──
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    if sort_priority == 'high_to_low':
        filtered_qs = sorted(filtered_qs, key=lambda c: priority_order.get(c.priority, 4))
    elif sort_priority == 'low_to_high':
        filtered_qs = sorted(filtered_qs, key=lambda c: priority_order.get(c.priority, 4), reverse=True)

    paginator   = Paginator(filtered_qs, 8)
    page_number = request.GET.get('page')
    complaints  = paginator.get_page(page_number)

    return render(request, 'complaints/dashboard.html', {
        'complaints':    complaints,
        'total':         total,
        'open_count':    open_count,
        'assigned':      assigned,
        'resolved':      resolved,
        'canceled':      canceled,
        'is_admin':      request.user.is_staff,
        'status_filter': status_filter,
        'search_query':  search_query,
        'sort_priority': sort_priority,
    })


# ── ADD COMPLAINT ──────────────────────────────────────
@login_required
def add_complaint(request):
    if request.method == 'POST':
        form = ComplaintForm(request.POST)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.submitted_by = request.user
            complaint.save()
            ComplaintLog.objects.create(
                complaint=complaint,
                action='Complaint created',
                performed_by=request.user,
                note=f'Complaint raised by {request.user.username}'
            )
            messages.success(request, 'Complaint submitted successfully.')
            return redirect('dashboard')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = ComplaintForm()
    return render(request, 'complaints/add_complaint.html', {'form': form})


# ── UPDATE COMPLAINT (Admin) ───────────────────────────
@login_required
@user_passes_test(is_admin)
def update_complaint(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)

    if request.method == 'POST':
        new_status      = request.POST.get('status')
        new_assigned_id = request.POST.get('assigned_to')
        new_admin_notes = request.POST.get('admin_notes', '')

        old_status      = complaint.status
        old_assigned_to = complaint.assigned_to

        if old_status in ['resolved', 'canceled']:
            messages.error(request, f'This complaint is already {complaint.get_status_display().lower()} and cannot be modified.')
            return redirect('update_complaint', pk=pk)

        new_assigned_to = None
        if new_assigned_id:
            new_assigned_to = User.objects.filter(pk=new_assigned_id, is_staff=False).first()

        was_assigned = old_assigned_to is not None

        if was_assigned and new_assigned_to is None:
            messages.error(request, 'You cannot unassign the engineer once a complaint is assigned.')
            return redirect('update_complaint', pk=pk)

        if was_assigned and new_assigned_to is not None and new_assigned_to.pk == old_assigned_to.pk:
            if new_status == old_status:
                messages.warning(request, f'This complaint is already assigned to {old_assigned_to.username}.')
                return redirect('update_complaint', pk=pk)

        assignee_changed = (
            (new_assigned_to and not old_assigned_to) or
            (not new_assigned_to and old_assigned_to) or
            (new_assigned_to and old_assigned_to and new_assigned_to.pk != old_assigned_to.pk)
        )
        notes_changed = (new_admin_notes != complaint.admin_notes)

        # ── AUTO STATUS LOGIC — runs regardless of what was picked in the dropdown ──
        if new_status == 'canceled':
            final_status = 'canceled'
            complaint.is_canceled = True
        elif new_status == 'resolved':
            final_status = 'resolved'
        elif new_assigned_to is not None:
            # Assigning an engineer ALWAYS forces status to 'assigned',
            # overriding any 'open' selection made in the dropdown
            final_status = 'assigned'
        elif new_assigned_to is None and not was_assigned:
            final_status = 'open'
        else:
            final_status = old_status

        complaint.status      = final_status
        complaint.assigned_to = new_assigned_to
        complaint.admin_notes = new_admin_notes

        status_changed = (complaint.status != old_status)

        if not status_changed and not assignee_changed and not notes_changed:
            messages.warning(request, 'No changes were made to this complaint.')
            return redirect('update_complaint', pk=pk)

        complaint.save()

        if assignee_changed and complaint.assigned_to:
            action_text = f'Assigned to {complaint.assigned_to.username} — status auto-updated to Assigned'
        elif status_changed:
            action_text = f'Status updated to {complaint.get_status_display()}'
        else:
            action_text = 'Notes updated'

        ComplaintLog.objects.create(
            complaint=complaint,
            action=action_text,
            performed_by=request.user,
            assigned_to=complaint.assigned_to,
            note=complaint.admin_notes or ''
        )

        messages.success(request, 'Complaint updated successfully.')
        return redirect('dashboard')

    if complaint.status in ['resolved', 'canceled']:
        messages.warning(request, f'This complaint is {complaint.get_status_display().lower()} and is now locked from further changes.')

    engineers = User.objects.filter(is_staff=False)
    return render(request, 'complaints/update_complaint.html', {
        'complaint': complaint,
        'engineers': engineers,
        'status_choices': Complaint.STATUS_CHOICES,
    })

# ── CANCEL COMPLAINT (Admin) ───────────────────────────
@login_required
@user_passes_test(is_admin)
def cancel_complaint(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)
    complaint.status      = 'canceled'
    complaint.is_canceled = True
    complaint.save()
    ComplaintLog.objects.create(
        complaint=complaint,
        action='Complaint canceled',
        performed_by=request.user,
        note='Complaint marked as canceled by admin'
    )
    messages.success(request, 'Complaint marked as canceled.')
    return redirect('dashboard')


# ── COMPLAINT DETAIL ───────────────────────────────────
@login_required
def complaint_detail(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)
    if not request.user.is_staff and \
       complaint.submitted_by != request.user and \
       complaint.assigned_to != request.user:
        messages.error(request, 'You do not have permission to view this.')
        return redirect('dashboard')
    logs = complaint.logs.all().order_by('timestamp')
    return render(request, 'complaints/detail.html', {
        'complaint': complaint,
        'logs':      logs,
    })


# ── ASSIGN COMPLAINT ───────────────────────────────────
@login_required
def assign_complaint(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)

    if complaint.submitted_by != request.user and complaint.assigned_to != request.user:
        messages.error(request, 'You cannot assign this complaint.')
        return redirect('dashboard')

    # Rule: resolved or canceled complaints cannot be reassigned by anyone
    if complaint.status in ['resolved', 'canceled']:
        messages.error(request, f'This complaint is already {complaint.get_status_display().lower()} and cannot be reassigned.')
        return redirect('dashboard')

    engineers = User.objects.filter(is_staff=False).exclude(pk=request.user.pk)

    if request.method == 'POST':
        new_engineer_id = request.POST.get('assigned_to')

        if not new_engineer_id:
            messages.error(request, 'Please select an engineer.')
            return redirect('assign_complaint', pk=pk)

        try:
            new_engineer = User.objects.get(pk=new_engineer_id, is_staff=False)
        except User.DoesNotExist:
            messages.error(request, 'Selected engineer does not exist.')
            return redirect('assign_complaint', pk=pk)

        previous = complaint.assigned_to

        if previous is not None and new_engineer.pk == previous.pk:
            messages.warning(request, f'This complaint is already assigned to {previous.username}.')
            return redirect('assign_complaint', pk=pk)

        complaint.assigned_to = new_engineer
        complaint.status = 'assigned'
        complaint.save()

        ComplaintLog.objects.create(
            complaint=complaint,
            action=f'Assigned to {new_engineer.username}',
            performed_by=request.user,
            assigned_to=new_engineer,
            note=f'Previously assigned to: {previous.username if previous else "Unassigned"}'
        )

        messages.success(request, f'Complaint assigned to {new_engineer.username}.')
        return redirect('dashboard')

    return render(request, 'complaints/assign_complaint.html', {
        'complaint': complaint,
        'engineers': engineers,
    })

# ── COMPLAINT HISTORY ──────────────────────────────────
@login_required
def complaint_history(request):
    log_complaint_ids = ComplaintLog.objects.filter(
        assigned_to=request.user
    ).values_list('complaint_id', flat=True).distinct()

    all_complaints = Complaint.objects.filter(
        Q(submitted_by=request.user) |
        Q(assigned_to=request.user) |
        Q(id__in=log_complaint_ids)
    ).distinct().order_by('-created_at')

    paginator   = Paginator(all_complaints, 8)
    page_number = request.GET.get('page')
    complaints  = paginator.get_page(page_number)

    return render(request, 'complaints/history.html', {'complaints': complaints})


# ── ADD ENGINEER (Admin) ───────────────────────────────
@login_required
@user_passes_test(is_admin)
def add_engineer(request):
    if request.method == 'POST':
        form = NewEngineerForm(request.POST)
        if form.is_valid():
            User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                is_staff=False
            )
            messages.success(request, f"Engineer '{form.cleaned_data['username']}' created successfully.")
            return redirect('dashboard')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = NewEngineerForm()
    return render(request, 'complaints/add_engineer.html', {'form': form})

# ── Create an export view in Django first: ───────────────────────────────
import csv
from django.http import HttpResponse

@login_required
def export_complaints_csv(request):
    status_filter   = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    search_query    = request.GET.get('search', '').strip()
    date_from       = request.GET.get('date_from', '').strip()
    date_to         = request.GET.get('date_to', '').strip()

    if request.user.is_staff:
        complaints = Complaint.objects.all().order_by('-created_at')
    else:
        complaints = Complaint.objects.filter(
            Q(submitted_by=request.user) | Q(assigned_to=request.user)
        ).distinct().order_by('-created_at')

    if status_filter and status_filter != 'all':
        complaints = complaints.filter(status=status_filter)

    if priority_filter and priority_filter != 'all':
        complaints = complaints.filter(priority=priority_filter)

    if search_query:
        complaints = complaints.filter(
            Q(title__icontains=search_query) | Q(unique_id__icontains=search_query)
        )

    if date_from:
        complaints = complaints.filter(created_at__date__gte=date_from)

    if date_to:
        complaints = complaints.filter(created_at__date__lte=date_to)

    response = HttpResponse(content_type='text/csv')

    suffix_parts = []
    if status_filter and status_filter != 'all':
        suffix_parts.append(status_filter)
    if priority_filter and priority_filter != 'all':
        suffix_parts.append(priority_filter)
    if date_from:
        suffix_parts.append(f"from{date_from}")
    if date_to:
        suffix_parts.append(f"to{date_to}")
    filename_suffix = ("_" + "_".join(suffix_parts)) if suffix_parts else ""

    response['Content-Disposition'] = f'attachment; filename="complaints_report{filename_suffix}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Unique ID', 'Title', 'Description', 'Location', 'Priority',
        'Status', 'Raised By', 'Assigned To', 'Created At', 'Last Updated',
        'Time Taken'
    ])

    def format_duration(seconds):
        days  = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        if days > 0:
            return f"{days} day(s) {hours} hour(s)"
        return f"{hours} hour(s)"

    for c in complaints:
        if c.status == 'resolved':
            diff = (c.updated_at - c.created_at).total_seconds()
            time_taken = f"Resolved in {format_duration(diff)}"
        elif c.status == 'canceled':
            diff = (c.updated_at - c.created_at).total_seconds()
            time_taken = f"Canceled after {format_duration(diff)}"
        elif c.status == 'assigned':
            diff = (c.updated_at - c.created_at).total_seconds()
            time_taken = f"{format_duration(diff)}"
        else:
            time_taken = "Still Open"

        writer.writerow([
            c.unique_id,
            c.title,
            c.description,
            c.location,
            c.get_priority_display(),
            c.get_status_display(),
            c.submitted_by.username,
            c.assigned_to.username if c.assigned_to else 'Unassigned',
            c.created_at.strftime('%d-%m-%Y %H:%M'),
            c.updated_at.strftime('%d-%m-%Y %H:%M'),
            time_taken,
        ])

    return response