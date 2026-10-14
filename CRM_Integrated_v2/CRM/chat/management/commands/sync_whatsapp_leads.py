from django.core.management.base import BaseCommand

from chat.crm import ensure_lead_for_conversation
from chat.models import Conversation


class Command(BaseCommand):
    help = ("Create CRM leads (source WhatsApp) for existing WhatsApp chats that don't have one yet. "
            "Safe to run again: numbers that already are leads are left as they are.")

    def handle(self, *args, **options):
        created = existing = skipped = 0
        for conv in Conversation.objects.select_related('business_account').order_by('created_at'):
            lead, was_created = ensure_lead_for_conversation(conv, conversation_created=False)
            if lead is None:
                skipped += 1
            elif was_created:
                created += 1
            else:
                existing += 1
        self.stdout.write(self.style.SUCCESS(
            f"{created} new WhatsApp lead(s), {existing} chat(s) already linked to a lead, {skipped} skipped."))
