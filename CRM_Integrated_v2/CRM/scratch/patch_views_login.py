import os

views_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\accounts\views.py"
with open(views_path, "r", encoding="utf-8") as f:
    code = f.read()

old_block = """    form = LoginForm(request.POST or None)
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
                messages.error(request, "This account is inactive. Please contact your administrator.")
                return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})

            if expected_role:
                if expected_role == UserRole.ADMIN and not user.is_admin_user:
                    messages.error(request, f"Access denied. '{user.username}' is not registered with Admin privileges.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.SALES_HEAD and not user.is_sales_head_user:
                    messages.error(request, f"Access denied. '{user.username}' is not a Sales Head.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.TELECALLER and not user.is_telecaller_user:
                    messages.error(request, f"Access denied. '{user.username}' is not a Telecaller.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.RECEPTIONIST and not user.is_receptionist_user:
                    messages.error(request, f"Access denied. '{user.username}' is not a Receptionist.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})

            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)  # Browser close expiration
            else:
                request.session.set_expiry(1209600)  # 2 weeks

            log_activity(
                user=user,
                action="User Logged In",
                description=f"{user.display_role} '{user.username}' logged in successfully.",
                object_type="User",
                object_id=str(user.pk),
                request=request
            )
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return login_redirect(request)
        else:
            messages.error(request, "Invalid username or password. Please try again.")"""

new_block = """    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email_input = (form.cleaned_data.get('email') or form.cleaned_data.get('username') or '').strip()
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me')

        # Authenticate via EmailAuthBackend (with case-insensitive email matching)
        user = authenticate(request, username=email_input, password=password)
        if user is None:
            user = authenticate(request, email=email_input, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact your administrator.")
                return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})

            if expected_role:
                if expected_role == UserRole.ADMIN and not user.is_admin_user:
                    messages.error(request, f"Access denied. '{user.email}' is not registered with Admin privileges.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.SALES_HEAD and not user.is_sales_head_user:
                    messages.error(request, f"Access denied. '{user.email}' is not a Sales Head.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.TELECALLER and not user.is_telecaller_user:
                    messages.error(request, f"Access denied. '{user.email}' is not a Telecaller.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.RECEPTIONIST and not user.is_receptionist_user:
                    messages.error(request, f"Access denied. '{user.email}' is not a Receptionist.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})

            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)  # Browser close expiration
            else:
                request.session.set_expiry(1209600)  # 2 weeks

            log_activity(
                user=user,
                action="User Logged In",
                description=f"{user.display_role} '{user.email}' logged in successfully.",
                object_type="User",
                object_id=str(user.pk),
                request=request
            )
            messages.success(request, f"Welcome back, {user.first_name or user.email}!")
            return login_redirect(request)
        else:
            messages.error(request, "Invalid email address or password. Please try again.")"""

if old_block in code:
    code = code.replace(old_block, new_block)
    # Also replace general_login portal title
    code = code.replace("portal_title='TECHPANDA CRM Login'", "portal_title='DigiPanda CRM Login'")
    with open(views_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    print("Successfully patched accounts/views.py _process_login")
else:
    print("Could not find old_block in accounts/views.py")
