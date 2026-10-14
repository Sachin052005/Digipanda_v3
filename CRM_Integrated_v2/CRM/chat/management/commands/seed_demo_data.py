"""
Django management command to seed realistic WhatsApp CRM demo data.
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from chat.models import BusinessAccount, Conversation, Message


class Command(BaseCommand):
    help = 'Seeds initial WhatsApp CRM conversations and messages into SQLite'

    def handle(self, *args, **options):
        self.stdout.write("Seeding WhatsApp CRM demo data...")

        # Ensure Business Accounts exist
        main_acc, _ = BusinessAccount.objects.get_or_create(
            phone_number_id='1294166677119820',
            defaults={
                'name': 'Home AI Line',
                'phone_number': '+91 84382 39448',
                'is_default': True,
                'is_active': True,
            }
        )
        supp_acc, _ = BusinessAccount.objects.get_or_create(
            phone_number_id='1294166677119999',
            defaults={
                'name': 'Support & Admissions',
                'phone_number': '+91 80000 12345',
                'is_default': False,
                'is_active': True,
            }
        )

        # Clear existing messages and conversations for idempotency
        Message.objects.all().delete()
        Conversation.objects.all().delete()

        now = timezone.now()

        demo_contacts = [
            {
                "customer_name": "Priya Kumar",
                "phone_number": "+919876543210",
                "is_pinned": True,
                "is_online": True,
                "last_seen": "online",
                "unread_count": 2,
                "messages": [
                    {
                        "sender": Message.SENDER_AGENT,
                        "text": "Hello Priya! Welcome to EduTech Academy. How can I assist you today?",
                        "delta_mins": -95,
                        "status": Message.STATUS_READ,
                    },
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "Hi, I need course details for the Advanced Python and Full Stack Django program.",
                        "delta_mins": -90,
                        "status": Message.STATUS_DELIVERED,
                    },
                    {
                        "sender": Message.SENDER_AGENT,
                        "text": "Certainly! Our Django program is an 8-week intensive certification including real-time web development and REST APIs.",
                        "delta_mins": -40,
                        "status": Message.STATUS_READ,
                    },
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "What is the fee structure and schedule for weekend batches?",
                        "delta_mins": -15,
                        "status": Message.STATUS_DELIVERED,
                    },
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "Also, do you provide job placement assistance after completion?",
                        "delta_mins": -2,
                        "status": Message.STATUS_DELIVERED,
                    },
                ]
            },
            {
                "customer_name": "Arun Kumar",
                "phone_number": "+919876543211",
                "is_pinned": False,
                "is_online": True,
                "last_seen": "online",
                "unread_count": 0,
                "messages": [
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "Hello team, I submitted my assignment for the CRM project.",
                        "delta_mins": -180,
                        "status": Message.STATUS_DELIVERED,
                    },
                    {
                        "sender": Message.SENDER_AGENT,
                        "text": "Thanks Arun! Our mentor is reviewing your code submission right now.",
                        "delta_mins": -120,
                        "status": Message.STATUS_READ,
                    },
                    {
                        "sender": Message.SENDER_AGENT,
                        "text": "Great job on the database schema and query optimizations! Everything passed verification.",
                        "delta_mins": -45,
                        "status": Message.STATUS_READ,
                    },
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "Thank you so much! Looking forward to the next module.",
                        "delta_mins": -10,
                        "status": Message.STATUS_DELIVERED,
                    },
                ]
            },
            {
                "customer_name": "Meena Raj",
                "phone_number": "+919876543212",
                "is_pinned": False,
                "is_online": False,
                "last_seen": "last seen today at 11:45 AM",
                "unread_count": 1,
                "messages": [
                    {
                        "sender": Message.SENDER_AGENT,
                        "text": "Hi Meena, sharing the link for today's live demonstration.",
                        "delta_mins": -320,
                        "status": Message.STATUS_READ,
                    },
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "I was unable to join due to an internet glitch. Is there a recording available?",
                        "delta_mins": -60,
                        "status": Message.STATUS_DELIVERED,
                    },
                ]
            },
            {
                "customer_name": "Rahul Kumar",
                "phone_number": "+919876543213",
                "is_pinned": False,
                "is_online": False,
                "last_seen": "last seen yesterday",
                "unread_count": 0,
                "messages": [
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "Can I upgrade my subscription plan to Enterprise?",
                        "delta_mins": -1440,
                        "status": Message.STATUS_DELIVERED,
                    },
                    {
                        "sender": Message.SENDER_AGENT,
                        "text": "Yes, absolutely! I have dispatched the invoice to your registered email.",
                        "delta_mins": -1400,
                        "status": Message.STATUS_READ,
                    },
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "Payment completed. Thanks for the quick support!",
                        "delta_mins": -1350,
                        "status": Message.STATUS_DELIVERED,
                    },
                ]
            },
            {
                "customer_name": "Divya",
                "phone_number": "+919876543214",
                "is_pinned": False,
                "is_online": True,
                "last_seen": "online",
                "unread_count": 3,
                "messages": [
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "Hi! Are admissions open for the upcoming summer batch?",
                        "delta_mins": -18,
                        "status": Message.STATUS_DELIVERED,
                    },
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "Could you also share the brochure?",
                        "delta_mins": -12,
                        "status": Message.STATUS_DELIVERED,
                    },
                    {
                        "sender": Message.SENDER_CUSTOMER,
                        "text": "I'd like to book an appointment with the academic counselor.",
                        "delta_mins": -4,
                        "status": Message.STATUS_DELIVERED,
                    },
                ]
            },
        ]

        for item in demo_contacts:
            last_msg_item = item["messages"][-1]
            last_msg_time = now + timedelta(minutes=last_msg_item["delta_mins"])

            conv = Conversation.objects.create(
                business_account=main_acc,
                customer_name=item["customer_name"],
                phone_number=item["phone_number"],
                last_message=last_msg_item["text"],
                last_message_time=last_msg_time,
                unread_count=item["unread_count"],
                is_pinned=item["is_pinned"],
                is_online=item["is_online"],
                last_seen=item["last_seen"],
            )

            for m in item["messages"]:
                m_time = now + timedelta(minutes=m["delta_mins"])
                Message.objects.create(
                    conversation=conv,
                    sender=m["sender"],
                    message_type=Message.TYPE_TEXT,
                    message_text=m["text"],
                    status=m["status"],
                    timestamp=m_time,
                    whatsapp_message_id=f"wamid.demo_{conv.id}_{m_time.timestamp()}"
                )

            self.stdout.write(f"  Created conversation for {conv.customer_name} ({conv.phone_number}) with {len(item['messages'])} messages.")

        # Create demo conversation for the second business account
        supp_conv = Conversation.objects.create(
            business_account=supp_acc,
            customer_name="Karthik Raja",
            phone_number="+919876543301",
            last_message="Can you share the fee refund policy?",
            last_message_time=now - timedelta(minutes=25),
            unread_count=1,
            is_pinned=True,
            is_online=True,
            last_seen="online",
        )
        Message.objects.create(
            conversation=supp_conv,
            sender=Message.SENDER_CUSTOMER,
            message_type=Message.TYPE_TEXT,
            message_text="Can you share the fee refund policy?",
            status=Message.STATUS_DELIVERED,
            timestamp=now - timedelta(minutes=25),
        )

        self.stdout.write(self.style.SUCCESS("Demo data successfully seeded into SQLite!"))
