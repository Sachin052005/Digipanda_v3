import os
import re

CRM_DIR = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'

# 1. Update reports/views.py (admin_dashboard)
reports_path = os.path.join(CRM_DIR, 'reports', 'views.py')
with open(reports_path, 'r', encoding='utf-8') as f:
    code = f.read()

old_block = """    from_date = request.GET.get('from_date', '').strip()
    to_date = request.GET.get('to_date', '').strip()
    period = request.GET.get('period', '').strip()

    if period == 'today':
        from_date = today.strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')
    elif period == 'week':
        start_of_week = today - timedelta(days=today.weekday())
        from_date = start_of_week.strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')
    elif period == 'month':
        start_of_month = today.replace(day=1)
        from_date = start_of_month.strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')
    elif period == 'all':
        from_date = ''
        to_date = ''
    elif from_date or to_date:
        period = 'custom'"""

new_block = """    from leads.utils_date_filter import extract_normalized_date_range
    _date_info = extract_normalized_date_range(request, default_period=None)
    from_date = _date_info['start_date']
    to_date = _date_info['end_date']
    period = _date_info['period']
    if not from_date and not to_date and not request.GET.get('period'):
        period = ''"""

if old_block in code:
    code = code.replace(old_block, new_block, 1)
    print("reports/views.py date extraction patched")
else:
    print("reports/views.py old_block not found directly, checking normalized line endings...")
    old_crlf = old_block.replace('\n', '\r\n')
    new_crlf = new_block.replace('\n', '\r\n')
    if old_crlf in code:
        code = code.replace(old_crlf, new_crlf, 1)
        print("reports/views.py date extraction patched (CRLF)")
    else:
        print("Failed to find block in reports/views.py")

# Add compatibility keys to admin_dashboard context
old_ctx = """        'from_date': from_date,
        'to_date': to_date,
        'period': period,"""

new_ctx = """        'from_date': from_date,
        'to_date': to_date,
        'start_date': from_date,
        'end_date': to_date,
        'date_from': from_date,
        'date_to': to_date,
        'period': period,"""

if old_ctx in code:
    code = code.replace(old_ctx, new_ctx, 1)
    print("reports/views.py context patched")
else:
    old_ctx_crlf = old_ctx.replace('\n', '\r\n')
    new_ctx_crlf = new_ctx.replace('\n', '\r\n')
    if old_ctx_crlf in code:
        code = code.replace(old_ctx_crlf, new_ctx_crlf, 1)
        print("reports/views.py context patched (CRLF)")

with open(reports_path, 'w', encoding='utf-8') as f:
    f.write(code)


# 2. Update telecallers/views.py (telecaller_dashboard)
tc_path = os.path.join(CRM_DIR, 'telecallers', 'views.py')
with open(tc_path, 'r', encoding='utf-8') as f:
    tc_code = f.read()

old_tc = """    period = request.GET.get('period', 'all').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    start_dt, end_dt = None, None
    if period == 'today':
        start_dt = timezone.make_aware(datetime.combine(today, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'week':
        start_of_week = today - timedelta(days=today.weekday())
        start_dt = timezone.make_aware(datetime.combine(start_of_week, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'month':
        start_of_month = today.replace(day=1)
        start_dt = timezone.make_aware(datetime.combine(start_of_month, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'custom' and start_date and end_date:
        try:
            s_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            e_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            start_dt = timezone.make_aware(datetime.combine(s_date, time.min))
            end_dt = timezone.make_aware(datetime.combine(e_date, time.max))
        except ValueError:
            start_dt, end_dt = None, None"""

new_tc = """    from leads.utils_date_filter import extract_normalized_date_range
    _date_info = extract_normalized_date_range(request, default_period='all')
    start_date = _date_info['start_date']
    end_date = _date_info['end_date']
    period = _date_info['period']
    start_dt = _date_info['start_dt']
    end_dt = _date_info['end_dt']"""

if old_tc in tc_code:
    tc_code = tc_code.replace(old_tc, new_tc, 1)
    print("telecallers/views.py patched")
else:
    old_tc_crlf = old_tc.replace('\n', '\r\n')
    new_tc_crlf = new_tc.replace('\n', '\r\n')
    if old_tc_crlf in tc_code:
        tc_code = tc_code.replace(old_tc_crlf, new_tc_crlf, 1)
        print("telecallers/views.py patched (CRLF)")
    else:
        print("Failed to find block in telecallers/views.py")

with open(tc_path, 'w', encoding='utf-8') as f:
    f.write(tc_code)


# 3. Update counselors/views.py (counselor_dashboard)
counselors_path = os.path.join(CRM_DIR, 'counselors', 'views.py')
with open(counselors_path, 'r', encoding='utf-8') as f:
    c_code = f.read()

old_c = """    period = request.GET.get('period', 'all').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    today = timezone.localdate()
    start_dt, end_dt = None, None

    if period == 'today':
        start_dt = timezone.make_aware(datetime.combine(today, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'week':
        start_of_week = today - timedelta(days=today.weekday())
        start_dt = timezone.make_aware(datetime.combine(start_of_week, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'month':
        start_of_month = today.replace(day=1)
        start_dt = timezone.make_aware(datetime.combine(start_of_month, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'custom' and start_date and end_date:
        try:
            s_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            e_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            start_dt = timezone.make_aware(datetime.combine(s_date, time.min))
            end_dt = timezone.make_aware(datetime.combine(e_date, time.max))
        except ValueError:
            start_dt, end_dt = None, None"""

new_c = """    from leads.utils_date_filter import extract_normalized_date_range
    _date_info = extract_normalized_date_range(request, default_period='all')
    start_date = _date_info['start_date']
    end_date = _date_info['end_date']
    period = _date_info['period']
    today = timezone.localdate()
    start_dt = _date_info['start_dt']
    end_dt = _date_info['end_dt']"""

if old_c in c_code:
    c_code = c_code.replace(old_c, new_c, 1)
    print("counselors/views.py patched")
else:
    old_c_crlf = old_c.replace('\n', '\r\n')
    new_c_crlf = new_c.replace('\n', '\r\n')
    if old_c_crlf in c_code:
        c_code = c_code.replace(old_c_crlf, new_c_crlf, 1)
        print("counselors/views.py patched (CRLF)")
    else:
        print("Failed to find block in counselors/views.py")

with open(counselors_path, 'w', encoding='utf-8') as f:
    f.write(c_code)


# 4. Update managers/views.py (manager_dashboard)
mgr_path = os.path.join(CRM_DIR, 'managers', 'views.py')
with open(mgr_path, 'r', encoding='utf-8') as f:
    m_code = f.read()

old_m = """    period = request.GET.get('period', 'all').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    start_dt, end_dt = None, None
    if period == 'today':
        start_dt = timezone.make_aware(datetime.combine(today, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'week':
        start_of_week = today - timedelta(days=today.weekday())
        start_dt = timezone.make_aware(datetime.combine(start_of_week, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'month':
        start_of_month = today.replace(day=1)
        start_dt = timezone.make_aware(datetime.combine(start_of_month, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'custom' and start_date and end_date:
        try:
            s_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            e_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            start_dt = timezone.make_aware(datetime.combine(s_date, time.min))
            end_dt = timezone.make_aware(datetime.combine(e_date, time.max))
        except ValueError:
            start_dt, end_dt = None, None"""

new_m = """    from leads.utils_date_filter import extract_normalized_date_range
    _date_info = extract_normalized_date_range(request, default_period='all')
    start_date = _date_info['start_date']
    end_date = _date_info['end_date']
    period = _date_info['period']
    start_dt = _date_info['start_dt']
    end_dt = _date_info['end_dt']"""

if old_m in m_code:
    m_code = m_code.replace(old_m, new_m, 1)
    print("managers/views.py patched")
else:
    old_m_crlf = old_m.replace('\n', '\r\n')
    new_m_crlf = new_m.replace('\n', '\r\n')
    if old_m_crlf in m_code:
        m_code = m_code.replace(old_m_crlf, new_m_crlf, 1)
        print("managers/views.py patched (CRLF)")
    else:
        print("Failed to find block in managers/views.py")

with open(mgr_path, 'w', encoding='utf-8') as f:
    f.write(m_code)


# 5. Update branch_heads/views.py (branch_head_dashboard)
bh_path = os.path.join(CRM_DIR, 'branch_heads', 'views.py')
with open(bh_path, 'r', encoding='utf-8') as f:
    bh_code = f.read()

old_bh = """    period = request.GET.get('period', 'all').strip().lower()
    start_date_str = request.GET.get('start_date', '').strip()
    end_date_str = request.GET.get('end_date', '').strip()

    today = timezone.localdate()
    start_dt, end_dt = None, None

    if period == 'today':
        start_dt = timezone.make_aware(datetime.combine(today, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'week':
        start_of_week = today - timedelta(days=today.weekday())
        start_dt = timezone.make_aware(datetime.combine(start_of_week, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'month':
        start_of_month = today.replace(day=1)
        start_dt = timezone.make_aware(datetime.combine(start_of_month, time.min))
        end_dt = timezone.make_aware(datetime.combine(today, time.max))
    elif period == 'custom' and start_date_str and end_date_str:
        try:
            s_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            e_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            start_dt = timezone.make_aware(datetime.combine(s_date, time.min))
            end_dt = timezone.make_aware(datetime.combine(e_date, time.max))
        except ValueError:
            start_dt, end_dt = None, None"""

new_bh = """    from leads.utils_date_filter import extract_normalized_date_range
    _date_info = extract_normalized_date_range(request, default_period='all')
    start_date_str = _date_info['start_date']
    end_date_str = _date_info['end_date']
    period = _date_info['period']
    today = timezone.localdate()
    start_dt = _date_info['start_dt']
    end_dt = _date_info['end_dt']"""

if old_bh in bh_code:
    bh_code = bh_code.replace(old_bh, new_bh, 1)
    print("branch_heads/views.py patched")
else:
    old_bh_crlf = old_bh.replace('\n', '\r\n')
    new_bh_crlf = new_bh.replace('\n', '\r\n')
    if old_bh_crlf in bh_code:
        bh_code = bh_code.replace(old_bh_crlf, new_bh_crlf, 1)
        print("branch_heads/views.py patched (CRLF)")
    else:
        print("Failed to find block in branch_heads/views.py")

with open(bh_path, 'w', encoding='utf-8') as f:
    f.write(bh_code)


# 6. Update leads/views_accountant.py (accountant_dashboard)
acc_path = os.path.join(CRM_DIR, 'leads', 'views_accountant.py')
with open(acc_path, 'r', encoding='utf-8') as f:
    acc_code = f.read()

old_acc = """    today = timezone.localdate()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today.replace(day=1)
    else:
        start_date = today.replace(day=1)

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = today
    else:
        end_date = today

    # End of day datetime for queries
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))"""

new_acc = """    from leads.utils_date_filter import extract_normalized_date_range
    today = timezone.localdate()
    _date_info = extract_normalized_date_range(request, default_period='month')
    start_date = _date_info['start_date_obj'] or today.replace(day=1)
    end_date = _date_info['end_date_obj'] or today
    start_date_str = _date_info['start_date'] or start_date.strftime('%Y-%m-%d')
    end_date_str = _date_info['end_date'] or end_date.strftime('%Y-%m-%d')
    start_dt = _date_info['start_dt'] or timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_dt = _date_info['end_dt'] or timezone.make_aware(datetime.combine(end_date, datetime.max.time()))"""

if old_acc in acc_code:
    acc_code = acc_code.replace(old_acc, new_acc, 1)
    print("leads/views_accountant.py patched")
else:
    old_acc_crlf = old_acc.replace('\n', '\r\n')
    new_acc_crlf = new_acc.replace('\n', '\r\n')
    if old_acc_crlf in acc_code:
        acc_code = acc_code.replace(old_acc_crlf, new_acc_crlf, 1)
        print("leads/views_accountant.py patched (CRLF)")
    else:
        print("Failed to find block in leads/views_accountant.py")

with open(acc_path, 'w', encoding='utf-8') as f:
    f.write(acc_code)

print("Dashboard views date contracts updated successfully!")
