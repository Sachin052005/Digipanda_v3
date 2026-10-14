"""
Facebook Lead Ads -> CRM leads (source "Facebook", channel "Facebook").

Branch of a new Facebook lead (needed for the CRM's branch assignment):
  1. a form answer whose question name contains "branch" (e.g. preferred_branch)
  2. a "location" / "city" answer that matches a CRM branch name
  3. the Facebook form name, if it contains a branch name ("Velachery - Data Science")
  4. settings.FB_DEFAULT_BRANCH
  Otherwise the lead is "Pending Assignment", like any CRM lead without a branch.
Course: an answer whose question name contains "course" / "program", else the form name.
"""
import logging

from leads import intake

log = logging.getLogger('crm')

SOURCE = "Facebook"
CHANNEL = "Facebook"


def _answers_with(answers, words):
    for key, value in (answers or {}).items():
        k = str(key).lower()
        if value and any(w in k for w in words):
            yield value


def branch_for(fb_lead):
    if fb_lead.fb_page and fb_lead.fb_page.branch:
        return fb_lead.fb_page.branch
    answers = fb_lead.all_answers or {}
    for value in _answers_with(answers, ("branch",)):
        b = intake.resolve_branch(value)
        if b:
            return b
    for value in _answers_with(answers, ("location", "city", "area")):
        b = intake.resolve_branch(value)
        if b:
            return b
    if fb_lead.city:
        b = intake.resolve_branch(fb_lead.city)
        if b:
            return b
    if fb_lead.form_name:
        b = intake.resolve_branch(fb_lead.form_name)
        if b:
            return b
    return intake.default_branch('FB_DEFAULT_BRANCH')


def product_for(fb_lead):
    for value in _answers_with(fb_lead.all_answers, ("course", "program", "programme")):
        p = intake.resolve_product(value)
        if p:
            return p
    return intake.resolve_product(fb_lead.form_name) if fb_lead.form_name else None


def _summary(fb_lead):
    parts = []
    if fb_lead.form_name:
        parts.append(f"Form: {fb_lead.form_name}")
    if fb_lead.ad_name:
        parts.append(f"Ad: {fb_lead.ad_name}")
    if fb_lead.campaign_name:
        parts.append(f"Campaign: {fb_lead.campaign_name}")
    skip = {"full_name", "first_name", "last_name", "phone_number", "phone", "email", "email_address"}
    answers = [f"{str(k).replace('_', ' ').title()}: {v}" for k, v in (fb_lead.all_answers or {}).items()
               if v and str(k).lower() not in skip]
    if answers:
        parts.append("Answers — " + "; ".join(answers))
    return " · ".join(parts)


def push_to_crm(fb_lead):
    """Create / update the CRM lead for a saved FacebookLead. Never raises; result saved on fb_lead."""
    if fb_lead.lead_id:
        return fb_lead.lead
    try:
        lead, created = intake.intake_lead(
            phone=fb_lead.phone,
            source=SOURCE,
            channel_name=CHANNEL,
            name=fb_lead.full_name,
            email=fb_lead.email,
            branch=branch_for(fb_lead),
            product=product_for(fb_lead),
            note="📘 Facebook Lead Ad — " + (_summary(fb_lead) or "new form submission"),
            provider_event_id=fb_lead.leadgen_id,
            incoming_timestamp=getattr(fb_lead, 'created_time', None),
            data_payload=fb_lead.all_answers or {},
        )

    except Exception as exc:  # bad / missing phone, DB problems: keep the Facebook record, show the error
        log.warning("Facebook lead %s not added to CRM: %s", fb_lead.leadgen_id, exc)
        fb_lead.crm_result = "error"
        fb_lead.crm_error = str(exc)[:255]
        fb_lead.save(update_fields=["crm_result", "crm_error"])
        return None
    fb_lead.lead = lead
    fb_lead.crm_result = "new" if created else "existing"
    fb_lead.crm_error = ""
    fb_lead.save(update_fields=["lead", "crm_result", "crm_error"])
    return lead
