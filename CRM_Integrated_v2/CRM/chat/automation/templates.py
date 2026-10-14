"""
Admissions & Training WhatsApp Automation Flow Template.
Provides the graph-based default workflow (nodes + connections):
First Incoming Message -> Greeting -> Looking For (4 Options) -> Dynamic Course List
-> Save Course Data -> Branch Visit (YES/NO Condition) -> Date & Time -> Summary
-> Dynamic Course Brochure -> Dynamic Branch Location -> End.
"""

def get_default_admissions_flow_data():
    return {
        "nodes": [
            {
                "id": "trigger_1",
                "type": "trigger",
                "title": "First Incoming Message Trigger",
                "position": {"x": 240, "y": 40},
                "data": {
                    "trigger_type": "first_incoming_message"
                }
            },
            {
                "id": "greeting_1",
                "type": "message",
                "title": "Welcome Greeting",
                "position": {"x": 240, "y": 180},
                "data": {
                    "text": "👋 Welcome to *Tech Academy & Training Institute*!\n\nWe provide industry-led software engineering and technical training with assured placement assistance.\n\nLet's get you set up with the right career path! 🚀"
                }
            },
            {
                "id": "looking_for_1",
                "type": "buttons",
                "title": "What are you looking for?",
                "position": {"x": 240, "y": 360},
                "data": {
                    "header": "Career Track",
                    "text": "Please choose what you are looking for:",
                    "footer": "Select an option below",
                    "variable_name": "looking_for",
                    "options": [
                        {"id": "opt_training", "title": "Training"},
                        {"id": "opt_placement", "title": "Train + Placement"},
                        {"id": "opt_internship", "title": "Train + Internship"},
                        {"id": "opt_internship_placement", "title": "Train+Intern+Place"}
                    ]
                }
            },
            {
                "id": "course_list_1",
                "type": "list",
                "title": "Available Courses",
                "position": {"x": 240, "y": 560},
                "data": {
                    "source": "database",
                    "header": "Available Courses",
                    "text": "Select the technology you want to specialize in:",
                    "button_text": "View Courses",
                    "footer": "Industry-Standard Curriculums",
                    "variable_name": "course"
                }
            },
            {
                "id": "branch_visit_1",
                "type": "buttons",
                "title": "Campus Visit?",
                "position": {"x": 240, "y": 760},
                "data": {
                    "header": "Campus Tour & Counseling",
                    "text": "Would you like to schedule a free in-person counseling session at our nearest branch?",
                    "footer": "Free 1-on-1 counseling",
                    "variable_name": "branch_visit",
                    "options": [
                        {"id": "visit_yes", "title": "YES, Schedule Visit"},
                        {"id": "visit_no", "title": "NO, Online Only"}
                    ]
                }
            },
            {
                "id": "condition_branch_visit",
                "type": "condition",
                "title": "Check Campus Visit",
                "position": {"x": 240, "y": 960},
                "data": {
                    "variable": "branch_visit",
                    "operator": "contains",
                    "value": "YES"
                }
            },
            {
                "id": "date_time_1",
                "type": "question",
                "title": "Preferred Date & Time",
                "position": {"x": 460, "y": 1120},
                "data": {
                    "text": "📅 Great! Please reply with your preferred *Date & Time* for the campus visit (e.g., *Tomorrow 11:30 AM* or *Saturday 3 PM*):",
                    "variable_name": "visit_slot"
                }
            },
            {
                "id": "summary_1",
                "type": "message",
                "title": "Registration Summary",
                "position": {"x": 240, "y": 1300},
                "data": {
                    "text": "✅ *Thank you for sharing your preferences!*\n\nHere is your registration summary:\n• *Goal:* {{looking_for}}\n• *Course:* {{course_name}}\n• *Campus Visit:* {{branch_visit}}\n• *Schedule Slot:* {{visit_slot}}\n\nOur Senior Career Counselor will reach out shortly to guide your roadmap! 🎯"
                }
            },
            {
                "id": "course_brochure_1",
                "type": "media",
                "title": "Send Course Brochure",
                "position": {"x": 240, "y": 1480},
                "data": {
                    "source": "selected_course_brochure",
                    "caption": "📄 Here is the official curriculum brochure for *{{course_name}}*.",
                    "fallback_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
                }
            },
            {
                "id": "branch_location_1",
                "type": "location",
                "title": "Send Branch Location",
                "position": {"x": 240, "y": 1660},
                "data": {
                    "source": "dynamic_branch",
                    "fallback_name": "Tech Academy Headquarters",
                    "fallback_address": "45 Tech Park Avenue, Anna Salai, Chennai, Tamil Nadu 600002",
                    "fallback_latitude": 13.0827,
                    "fallback_longitude": 80.2707
                }
            },
            {
                "id": "end_1",
                "type": "end",
                "title": "Session Completed",
                "position": {"x": 240, "y": 1840},
                "data": {
                    "text": "If you have any other questions, feel free to message our team anytime. Thank you! 🌟"
                }
            }
        ],
        "connections": [
            {"source": "trigger_1", "source_output": "default", "target": "greeting_1", "target_input": "input"},
            {"source": "greeting_1", "source_output": "default", "target": "looking_for_1", "target_input": "input"},
            {"source": "looking_for_1", "source_output": "opt_training", "target": "course_list_1", "target_input": "input"},
            {"source": "looking_for_1", "source_output": "opt_placement", "target": "course_list_1", "target_input": "input"},
            {"source": "looking_for_1", "source_output": "opt_internship", "target": "course_list_1", "target_input": "input"},
            {"source": "looking_for_1", "source_output": "opt_internship_placement", "target": "course_list_1", "target_input": "input"},
            {"source": "course_list_1", "source_output": "default", "target": "branch_visit_1", "target_input": "input"},
            {"source": "branch_visit_1", "source_output": "visit_yes", "target": "condition_branch_visit", "target_input": "input"},
            {"source": "branch_visit_1", "source_output": "visit_no", "target": "condition_branch_visit", "target_input": "input"},
            {"source": "condition_branch_visit", "source_output": "YES", "target": "date_time_1", "target_input": "input"},
            {"source": "condition_branch_visit", "source_output": "NO", "target": "summary_1", "target_input": "input"},
            {"source": "date_time_1", "source_output": "default", "target": "summary_1", "target_input": "input"},
            {"source": "summary_1", "source_output": "default", "target": "course_brochure_1", "target_input": "input"},
            {"source": "course_brochure_1", "source_output": "default", "target": "branch_location_1", "target_input": "input"},
            {"source": "branch_location_1", "source_output": "default", "target": "end_1", "target_input": "input"}
        ],
        "settings": {
            "session_timeout_hours": 24,
            "handover_keywords": ["agent", "human", "talk to human", "support", "help"]
        }
    }
