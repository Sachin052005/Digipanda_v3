import os

finance_views = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\finance\views.py"
with open(finance_views, "r", encoding="utf-8") as f:
    code = f.read()

old_fin = """    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username_input = form.cleaned_data.get('username', '').strip()
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me')

        matched_user = User.objects.filter(email__iexact=username_input).first()
        if not matched_user:
            matched_user = User.objects.filter(username__iexact=username_input).first()

        auth_username = matched_user.username if matched_user else username_input
        user = authenticate(request, username=auth_username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "Your account has been deactivated. Please contact your administrator.")
                return render(request, 'finance/login.html', {
                    'form': form,
                    'next': next_url,
                    'portal_title': 'Branch Financial Head Portal',
                })

            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)

            try:
                from activities.services import log_activity
                log_activity(
                    user=user,
                    action="Finance Portal Sign In",
                    description=f"{user.display_role} '{user.username}' signed in to Finance Portal.",
                    object_type="User",
                    object_id=str(user.pk),
                    request=request
                )
            except Exception:
                pass

            messages.success(request, f"Welcome back, {user.first_name or user.username}!")

            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)

            from accounts.views import login_redirect
            return login_redirect(request)
        else:
            messages.error(request, "Invalid username or password. Please verify your credentials.")"""

new_fin = """    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email_input = (form.cleaned_data.get('email') or form.cleaned_data.get('username') or '').strip()
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me')

        user = authenticate(request, username=email_input, password=password)
        if user is None:
            user = authenticate(request, email=email_input, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "Your account has been deactivated. Please contact your administrator.")
                return render(request, 'finance/login.html', {
                    'form': form,
                    'next': next_url,
                    'portal_title': 'Branch Financial Head Portal',
                })

            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)

            try:
                from activities.services import log_activity
                log_activity(
                    user=user,
                    action="Finance Portal Sign In",
                    description=f"{user.display_role} '{user.email}' signed in to Finance Portal.",
                    object_type="User",
                    object_id=str(user.pk),
                    request=request
                )
            except Exception:
                pass

            messages.success(request, f"Welcome back, {user.first_name or user.email}!")

            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)

            from accounts.views import login_redirect
            return login_redirect(request)
        else:
            messages.error(request, "Invalid email address or password. Please verify your credentials.")"""

if old_fin in code:
    code = code.replace(old_fin, new_fin)
    with open(finance_views, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    print("Successfully patched finance/views.py")
else:
    print("Could not find old_fin block in finance/views.py")
