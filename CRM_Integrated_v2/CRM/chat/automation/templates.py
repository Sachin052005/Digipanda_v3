# Digipanda Academy Admissions WhatsApp Automation Flow Template

def get_default_admissions_flow_data():
    return {
    "nodes": [
        {
            "x": 100,
            "y": 80,
            "id": "trigger_1",
            "data": {
                "title": "Trigger",
                "keywords": "hi, hello, course, restart, start",
                "trigger_type": "first_incoming_message"
            },
            "type": "trigger",
            "title": "Trigger",
            "position": {
                "x": 100,
                "y": 80
            },
            "next_node_id": "msg_1",
            "trigger_type": "first_incoming_message",
            "trigger_keywords": "hi, hello, course, restart, start"
        },
        {
            "x": 380,
            "y": 80,
            "id": "msg_1",
            "body": "Hey there! \ud83d\udc4b\n\nWelcome to Digipanda Academy!\ud83d\ude80\n\nReady to level up your digital marketing skills?\n\nExplore hands-on training in SEO, Google Ads, Meta Ads, Social Media, Content Creation, Video Editing & AI Tools.\n\nLet's help you get started! \u2728",
            "data": {
                "text": "Hey there! \ud83d\udc4b\n\nWelcome to Digipanda Academy!\ud83d\ude80\n\nReady to level up your digital marketing skills?\n\nExplore hands-on training in SEO, Google Ads, Meta Ads, Social Media, Content Creation, Video Editing & AI Tools.\n\nLet's help you get started! \u2728",
                "title": "Welcome Message"
            },
            "type": "message",
            "title": "Welcome Message",
            "position": {
                "x": 380,
                "y": 80
            },
            "next_node_id": "node_buttons_7461"
        },
        {
            "x": 380,
            "y": 360,
            "id": "node_buttons_7461",
            "body": "What are you looking for?",
            "data": {
                "text": "What are you looking for?",
                "title": "Q1: What are you looking for?",
                "footer": "Select an option",
                "header": "Question 1",
                "options": [
                    {
                        "id": "opt_1",
                        "title": "Training",
                        "next_node_id": "node_buttons_8415"
                    },
                    {
                        "id": "opt_2",
                        "title": "Train + Placement",
                        "next_node_id": "node_buttons_8415"
                    }
                ],
                "variable_name": "interest_type"
            },
            "type": "buttons",
            "title": "Q1: What are you looking for?",
            "footer": "Select an option",
            "header": "Question 1",
            "options": [
                {
                    "id": "opt_1",
                    "title": "Training",
                    "next_node_id": "node_buttons_8415"
                },
                {
                    "id": "opt_2",
                    "title": "Train + Placement",
                    "next_node_id": "node_buttons_8415"
                }
            ],
            "position": {
                "x": 380,
                "y": 360
            },
            "next_node_id": None,
            "variable_name": "interest_type"
        },
        {
            "x": 720,
            "y": 360,
            "id": "node_buttons_8415",
            "body": "When are you planning to join?",
            "data": {
                "text": "When are you planning to join?",
                "title": "Q2: When are you planning to join?",
                "footer": "Select timeframe",
                "header": "Question 2",
                "options": [
                    {
                        "id": "opt_1",
                        "title": "Immediately",
                        "next_node_id": "node_list_q3"
                    },
                    {
                        "id": "opt_2",
                        "title": "Within 7 Days",
                        "next_node_id": "node_list_q3"
                    },
                    {
                        "id": "opt_3",
                        "title": "Within 15 Days",
                        "next_node_id": "node_list_q3"
                    }
                ],
                "variable_name": "joining_timeframe"
            },
            "type": "buttons",
            "title": "Q2: When are you planning to join?",
            "footer": "Select timeframe",
            "header": "Question 2",
            "options": [
                {
                    "id": "opt_1",
                    "title": "Immediately",
                    "next_node_id": "node_list_q3"
                },
                {
                    "id": "opt_2",
                    "title": "Within 7 Days",
                    "next_node_id": "node_list_q3"
                },
                {
                    "id": "opt_3",
                    "title": "Within 15 Days",
                    "next_node_id": "node_list_q3"
                }
            ],
            "position": {
                "x": 720,
                "y": 360
            },
            "next_node_id": None,
            "variable_name": "joining_timeframe"
        },
        {
            "x": 1060,
            "y": 360,
            "id": "node_list_q3",
            "body": "What is your current status?",
            "data": {
                "text": "What is your current status?",
                "title": "Q3: What is your current status?",
                "footer": "Tap button to view choices",
                "header": "Current Status",
                "source": "custom",
                "sections": [
                    {
                        "rows": [
                            {
                                "id": "row_1",
                                "title": "College Student",
                                "description": "Currently enrolled"
                            },
                            {
                                "id": "row_2",
                                "title": "Fresher / Job Seeker",
                                "description": "Looking for employment"
                            },
                            {
                                "id": "row_3",
                                "title": "Working Professional",
                                "description": "Up-skilling"
                            },
                            {
                                "id": "row_4",
                                "title": "Business Owner / Entrep",
                                "description": "Entrepreneur or business"
                            }
                        ],
                        "title": "Status Options"
                    }
                ],
                "button_text": "Select Status",
                "variable_name": "student_status"
            },
            "type": "list",
            "title": "Q3: What is your current status?",
            "footer": "Tap button to view choices",
            "header": "Current Status",
            "source": "custom",
            "position": {
                "x": 1060,
                "y": 360
            },
            "sections": [
                {
                    "rows": [
                        {
                            "id": "row_1",
                            "title": "College Student",
                            "description": "Currently enrolled"
                        },
                        {
                            "id": "row_2",
                            "title": "Fresher / Job Seeker",
                            "description": "Looking for employment"
                        },
                        {
                            "id": "row_3",
                            "title": "Working Professional",
                            "description": "Up-skilling"
                        },
                        {
                            "id": "row_4",
                            "title": "Business Owner / Entrep",
                            "description": "Entrepreneur or business"
                        }
                    ],
                    "title": "Status Options"
                }
            ],
            "button_text": "Select Status",
            "next_node_id": "node_buttons_q4",
            "variable_name": "student_status"
        },
        {
            "x": 1060,
            "y": 680,
            "id": "node_buttons_q4",
            "body": "Preferred training mode?",
            "data": {
                "text": "Preferred training mode?",
                "title": "Q4: Preferred training mode?",
                "footer": "Select your mode",
                "header": "Training Mode",
                "options": [
                    {
                        "id": "opt_1",
                        "title": "Classroom (Chennai)",
                        "next_node_id": "node_buttons_q5"
                    },
                    {
                        "id": "opt_2",
                        "title": "Online Training",
                        "next_node_id": "node_buttons_q5"
                    }
                ],
                "variable_name": "training_mode"
            },
            "type": "buttons",
            "title": "Q4: Preferred training mode?",
            "footer": "Select your mode",
            "header": "Training Mode",
            "options": [
                {
                    "id": "opt_1",
                    "title": "Classroom (Chennai)",
                    "next_node_id": "node_buttons_q5"
                },
                {
                    "id": "opt_2",
                    "title": "Online Training",
                    "next_node_id": "node_buttons_q5"
                }
            ],
            "position": {
                "x": 1060,
                "y": 680
            },
            "next_node_id": None,
            "variable_name": "training_mode"
        },
        {
            "x": 720,
            "y": 680,
            "id": "node_buttons_q5",
            "body": "Which program interests you?",
            "data": {
                "text": "Which program interests you?",
                "title": "Q5: Which program interests you?",
                "footer": "Career vs Pro",
                "header": "Select Program",
                "options": [
                    {
                        "id": "opt_1",
                        "title": "45 Days Career Prog",
                        "next_node_id": "end_1"
                    },
                    {
                        "id": "opt_2",
                        "title": "60 Days Pro Program",
                        "next_node_id": "end_1"
                    }
                ],
                "variable_name": "program_duration"
            },
            "type": "buttons",
            "title": "Q5: Which program interests you?",
            "footer": "Career vs Pro",
            "header": "Select Program",
            "options": [
                {
                    "id": "opt_1",
                    "title": "45 Days Career Prog",
                    "next_node_id": "end_1"
                },
                {
                    "id": "opt_2",
                    "title": "60 Days Pro Program",
                    "next_node_id": "end_1"
                }
            ],
            "position": {
                "x": 720,
                "y": 680
            },
            "next_node_id": None,
            "variable_name": "program_duration"
        },
        {
            "x": 380,
            "y": 680,
            "id": "end_1",
            "body": "Thank you for your interest in **DigiPanda Academy!** \ud83d\udc99\n\nOur team will help you with course details, available batches and career guidance.\n\n\ud83d\udcde Need assistance? Call or WhatsApp **74488 88593**.\n\n\ud83c\udf10 Website: https://digipandaacademy.com/\n\nLet's build your digital future! \ud83d\ude80",
            "data": {
                "text": "Thank you for your interest in **DigiPanda Academy!** \ud83d\udc99\n\nOur team will help you with course details, available batches and career guidance.\n\n\ud83d\udcde Need assistance? Call or WhatsApp **74488 88593**.\n\n\ud83c\udf10 Website: https://digipandaacademy.com/\n\nLet's build your digital future! \ud83d\ude80",
                "title": "End Session"
            },
            "type": "end",
            "title": "End Session",
            "position": {
                "x": 380,
                "y": 680
            },
            "next_node_id": None
        }
    ],
    "viewport": {
        "x": 0,
        "y": 0,
        "zoom": 1
    },
    "connections": [
        {
            "id": "c_trig_msg",
            "source": "trigger_1",
            "target": "msg_1",
            "target_input": "input",
            "source_output": "default"
        },
        {
            "id": "c_msg_q1",
            "source": "msg_1",
            "target": "node_buttons_7461",
            "target_input": "input",
            "source_output": "default"
        },
        {
            "id": "c_q1_opt1_q2",
            "source": "node_buttons_7461",
            "target": "node_buttons_8415",
            "target_input": "input",
            "source_output": "opt_1"
        },
        {
            "id": "c_q1_opt2_q2",
            "source": "node_buttons_7461",
            "target": "node_buttons_8415",
            "target_input": "input",
            "source_output": "opt_2"
        },
        {
            "id": "c_q2_opt1_q3",
            "source": "node_buttons_8415",
            "target": "node_list_q3",
            "target_input": "input",
            "source_output": "opt_1"
        },
        {
            "id": "c_q2_opt2_q3",
            "source": "node_buttons_8415",
            "target": "node_list_q3",
            "target_input": "input",
            "source_output": "opt_2"
        },
        {
            "id": "c_q2_opt3_q3",
            "source": "node_buttons_8415",
            "target": "node_list_q3",
            "target_input": "input",
            "source_output": "opt_3"
        },
        {
            "id": "c_q3_q4",
            "source": "node_list_q3",
            "target": "node_buttons_q4",
            "target_input": "input",
            "source_output": "default"
        },
        {
            "id": "c_q4_opt1_q5",
            "source": "node_buttons_q4",
            "target": "node_buttons_q5",
            "target_input": "input",
            "source_output": "opt_1"
        },
        {
            "id": "c_q4_opt2_q5",
            "source": "node_buttons_q4",
            "target": "node_buttons_q5",
            "target_input": "input",
            "source_output": "opt_2"
        },
        {
            "id": "c_q5_opt1_end",
            "source": "node_buttons_q5",
            "target": "end_1",
            "target_input": "input",
            "source_output": "opt_1"
        },
        {
            "id": "c_q5_opt2_end",
            "source": "node_buttons_q5",
            "target": "end_1",
            "target_input": "input",
            "source_output": "opt_2"
        }
    ]
}
