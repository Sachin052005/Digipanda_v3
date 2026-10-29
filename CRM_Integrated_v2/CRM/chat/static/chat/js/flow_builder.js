/**
 * WhatsApp Flow Builder - Vanilla JavaScript Application
 * Visual No-Code Automation Graph Editor & Interactive Simulator
 */

(function () {
    'use strict';

    // Application State
    const state = {
        businessAccounts: [],
        selectedBusinessAccountId: null,
        currentFlow: null,
        selectedNodeId: null,
        scale: 1.0,
        draggedNode: null,
        dragOffset: { x: 0, y: 0 },
        history: [],
        historyIndex: -1,
        selectedEdgeId: null,
        connectingFrom: null,
        hoveredTargetPort: null,
        // Simulator State
        simState: {
            isOpen: false,
            currentNodeId: null,
            collectedData: {},
            history: []
        }
    };

    // Default Fallback Template (Admissions & Training Graph)
    const DEFAULT_TEMPLATE = {
    "name": "Digipanda",
    "trigger_type": "first_incoming_message",
    "trigger_keywords": "hi, hello, course, restart, start",
    "flow_data": {
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
                "next_node_id": null,
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
                "next_node_id": null,
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
                "next_node_id": null,
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
                "next_node_id": null,
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
                "next_node_id": null
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
};

    // DOM Elements
    const elements = {
        flowNameDisplay: document.getElementById('flowNameDisplay'),
        flowVersionTag: document.getElementById('flowVersionTag'),
        flowStatusBadge: document.getElementById('flowStatusBadge'),
        flowBusinessAccountSelect: document.getElementById('flowBusinessAccountSelect'),
        btnResetTemplate: document.getElementById('btnResetTemplate'),
        btnOpenSimulator: document.getElementById('btnOpenSimulator'),
        btnCreateDraft: document.getElementById('btnCreateDraft'),
        btnSaveDraft: document.getElementById('btnSaveDraft'),
        btnPublishFlow: document.getElementById('btnPublishFlow'),

        // Left Palette
        paletteNodesList: document.getElementById('paletteNodesList'),
        triggerTypeSelect: document.getElementById('triggerTypeSelect'),
        triggerKeywordsBox: document.getElementById('triggerKeywordsBox'),
        triggerKeywordsInput: document.getElementById('triggerKeywordsInput'),

        // Canvas
        canvasArea: document.getElementById('canvasArea'),
        canvasViewport: document.getElementById('canvasViewport'),
        canvasPlane: document.getElementById('canvasPlane'),
        canvasSvgLayer: document.getElementById('canvasSvgLayer'),
        canvasNodesLayer: document.getElementById('canvasNodesLayer'),
        btnZoomIn: document.getElementById('btnZoomIn'),
        btnZoomOut: document.getElementById('btnZoomOut'),
        zoomLevelText: document.getElementById('zoomLevelText'),
        btnAutoLayout: document.getElementById('btnAutoLayout'),
        btnResetView: document.getElementById('btnResetView'),

        // Inspector
        inspectorSidebar: document.getElementById('inspectorSidebar'),
        inspectorNodeBadge: document.getElementById('inspectorNodeBadge'),
        inspectorTitle: document.getElementById('inspectorTitle'),
        btnCloseInspector: document.getElementById('btnCloseInspector'),
        emptyInspectorState: document.getElementById('emptyInspectorState'),
        inspectorForm: document.getElementById('inspectorForm'),
        editNodeId: document.getElementById('editNodeId'),
        editNodeTitle: document.getElementById('editNodeTitle'),
        editNodeBody: document.getElementById('editNodeBody'),
        groupMessageBody: document.getElementById('groupMessageBody'),
        groupInteractiveHeaders: document.getElementById('groupInteractiveHeaders'),
        editNodeHeader: document.getElementById('editNodeHeader'),
        editNodeFooter: document.getElementById('editNodeFooter'),
        groupVariableName: document.getElementById('groupVariableName'),
        editVariableName: document.getElementById('editVariableName'),
        groupButtonsOptions: document.getElementById('groupButtonsOptions'),
        btnAddOptionBtn: document.getElementById('btnAddOptionBtn'),
        buttonsOptionsList: document.getElementById('buttonsOptionsList'),
        groupListRows: document.getElementById('groupListRows'),
        editListSource: document.getElementById('editListSource'),
        customListRowsContainer: document.getElementById('customListRowsContainer'),
        btnAddListRowBtn: document.getElementById('btnAddListRowBtn'),
        listRowsContainer: document.getElementById('listRowsContainer'),
        groupConditionDetails: document.getElementById('groupConditionDetails'),
        editConditionVariable: document.getElementById('editConditionVariable'),
        editConditionOperator: document.getElementById('editConditionOperator'),
        editConditionValue: document.getElementById('editConditionValue'),
        editConditionYesTarget: document.getElementById('editConditionYesTarget'),
        editConditionNoTarget: document.getElementById('editConditionNoTarget'),
        groupSaveDataDetails: document.getElementById('groupSaveDataDetails'),
        editSaveDataKey: document.getElementById('editSaveDataKey'),
        editSaveDataValue: document.getElementById('editSaveDataValue'),
        groupDelayDetails: document.getElementById('groupDelayDetails'),
        editDelaySeconds: document.getElementById('editDelaySeconds'),
        groupMediaDetails: document.getElementById('groupMediaDetails'),
        editMediaSource: document.getElementById('editMediaSource'),
        customMediaFields: document.getElementById('customMediaFields'),
        editMediaUrl: document.getElementById('editMediaUrl'),
        editMediaFilename: document.getElementById('editMediaFilename'),
        editMediaCaption: document.getElementById('editMediaCaption'),
        groupLocationDetails: document.getElementById('groupLocationDetails'),
        groupLeadStatusDetails: document.getElementById('groupLeadStatusDetails'),
        editLeadStatus: document.getElementById('editLeadStatus'),
        groupFollowUpHours: document.getElementById('groupFollowUpHours'),
        editFollowUpHours: document.getElementById('editFollowUpHours'),
        groupAssignDetails: document.getElementById('groupAssignDetails'),
        editAssignMode: document.getElementById('editAssignMode'),
        groupAssignTelecaller: document.getElementById('groupAssignTelecaller'),
        editAssignTelecaller: document.getElementById('editAssignTelecaller'),
        editAssignOnlyUnassigned: document.getElementById('editAssignOnlyUnassigned'),
        editLocationSource: document.getElementById('editLocationSource'),
        customLocationFields: document.getElementById('customLocationFields'),
        editLocationName: document.getElementById('editLocationName'),
        editLocationAddress: document.getElementById('editLocationAddress'),
        editLocationLat: document.getElementById('editLocationLat'),
        editLocationLng: document.getElementById('editLocationLng'),
        groupNextNode: document.getElementById('groupNextNode'),
        editNextNodeId: document.getElementById('editNextNodeId'),
        btnDeleteNode: document.getElementById('btnDeleteNode'),

        // Validation Modal
        validationModalBackdrop: document.getElementById('validationModalBackdrop'),
        validationErrorList: document.getElementById('validationErrorList'),
        btnCloseValidationModal: document.getElementById('btnCloseValidationModal'),
        btnAcknowledgeValidation: document.getElementById('btnAcknowledgeValidation'),

        // Simulator
        simulatorBackdrop: document.getElementById('simulatorBackdrop'),
        simulatorDrawer: document.getElementById('simulatorDrawer'),
        btnCloseSimulator: document.getElementById('btnCloseSimulator'),
        btnRestartSimulation: document.getElementById('btnRestartSimulation'),
        simMessages: document.getElementById('simMessages'),
        simChatForm: document.getElementById('simChatForm'),
        simChatInput: document.getElementById('simChatInput'),
        simListSheet: document.getElementById('simListSheet'),
        simSheetTitle: document.getElementById('simSheetTitle'),
        btnCloseSimSheet: document.getElementById('btnCloseSimSheet'),
        simSheetItems: document.getElementById('simSheetItems'),

        // Toast
        builderToast: document.getElementById('builderToast'),
        builderToastMsg: document.getElementById('builderToastMsg'),

        // Modern SaaS Enhancements
        saveStatusWrap: document.getElementById('saveStatusWrap'),
        saveStatusDot: document.getElementById('saveStatusDot'),
        saveStatusText: document.getElementById('saveStatusText'),
        btnUndo: document.getElementById('btnUndo'),
        btnRedo: document.getElementById('btnRedo'),
        btnBottomUndo: document.getElementById('btnBottomUndo'),
        btnBottomRedo: document.getElementById('btnBottomRedo'),
        btnZoomFit: document.getElementById('btnZoomFit'),
        flowBranchSelect: document.getElementById('flowBranchSelect'),
        branchSavedIndicator: document.getElementById('branchSavedIndicator'),
        paletteSearchInput: document.getElementById('paletteSearchInput'),
        flowOverviewPanel: document.getElementById('flowOverviewPanel'),
        overviewFlowName: document.getElementById('overviewFlowName'),
        overviewFlowVersion: document.getElementById('overviewFlowVersion'),
        overviewFlowStatus: document.getElementById('overviewFlowStatus'),
        overviewFlowTrigger: document.getElementById('overviewFlowTrigger'),
        overviewNodeCount: document.getElementById('overviewNodeCount'),
        overviewConnectionCount: document.getElementById('overviewConnectionCount'),
        messageLivePreview: document.getElementById('messageLivePreview'),
        btnOpenVariablePicker: document.getElementById('btnOpenVariablePicker'),
        varPickerBackdrop: document.getElementById('varPickerBackdrop'),
        btnCloseVarPicker: document.getElementById('btnCloseVarPicker'),
        confirmDialogModal: document.getElementById('confirmDialogModal'),
        confirmDialogTitle: document.getElementById('confirmDialogTitle'),
        confirmDialogMsg: document.getElementById('confirmDialogMsg'),
        btnDialogCancel: document.getElementById('btnDialogCancel'),
        btnDialogConfirm: document.getElementById('btnDialogConfirm'),
        btnCancelDialogX: document.getElementById('btnCancelDialogX'),
        simDebugDrawer: document.getElementById('simDebugDrawer'),
        simDebugHeader: document.getElementById('simDebugHeader'),
        simDebugToggleIcon: document.getElementById('simDebugToggleIcon'),
        simDebugContent: document.getElementById('simDebugContent'),
        debugSessionStatus: document.getElementById('debugSessionStatus'),
        debugCurrentNode: document.getElementById('debugCurrentNode'),
        debugFlowVersion: document.getElementById('debugFlowVersion'),
        debugCollectedData: document.getElementById('debugCollectedData'),
        canvasMinimap: document.getElementById('canvasMinimap'),
        minimapCanvas: document.getElementById('minimapCanvas'),
        minimapViewport: document.getElementById('minimapViewport'),

        // AI Assistant & Advanced Node Fields
        btnOpenAIAssistant: document.getElementById('btnOpenAIAssistant'),
        aiAssistantModal: document.getElementById('aiAssistantModal'),
        btnCloseAIAssistant: document.getElementById('btnCloseAIAssistant'),
        btnCancelAIAssistant: document.getElementById('btnCancelAIAssistant'),
        btnGenerateFromPrompt: document.getElementById('btnGenerateFromPrompt'),
        aiFlowNameInput: document.getElementById('aiFlowNameInput'),
        aiPromptInput: document.getElementById('aiPromptInput'),
        editQuestionExpectedType: document.getElementById('editQuestionExpectedType'),
        editQuestionRetryLimit: document.getElementById('editQuestionRetryLimit'),
        editQuestionInvalidMessage: document.getElementById('editQuestionInvalidMessage'),

        // Validation & Version Management
        btnValidateFlow: document.getElementById('btnValidateFlow'),
        btnVersionHistory: document.getElementById('btnVersionHistory'),
        versionHistoryModal: document.getElementById('versionHistoryModal'),
        btnCloseVersionHistory: document.getElementById('btnCloseVersionHistory'),
        versionHistoryList: document.getElementById('versionHistoryList'),
        builderApp: document.getElementById('builderApp'),
        btnNewFlow: document.getElementById('btnNewFlow'),
        newFlowModal: document.getElementById('newFlowModal'),
        btnCloseNewFlowModal: document.getElementById('btnCloseNewFlowModal'),
        btnCancelNewFlowModal: document.getElementById('btnCancelNewFlowModal'),
        btnConfirmCreateNewFlow: document.getElementById('btnConfirmCreateNewFlow'),
        newFlowNameInput: document.getElementById('newFlowNameInput'),
        newFlowTriggerSelect: document.getElementById('newFlowTriggerSelect'),
        newFlowKeywordsWrap: document.getElementById('newFlowKeywordsWrap'),
        newFlowKeywordsInput: document.getElementById('newFlowKeywordsInput'),
        newFlowTemplateSelect: document.getElementById('newFlowTemplateSelect')
    };

    // Node Type Metadata
    const NODE_TYPES = {
        start: { label: 'Start Trigger', icon: '⚡', color: '#10b981' },
        trigger: { label: 'Trigger', icon: '⚡', color: '#10b981' },
        message: { label: 'Message', icon: '💬', color: '#3b82f6' },
        buttons: { label: 'Buttons', icon: '🔘', color: '#8b5cf6' },
        list: { label: 'List Menu', icon: '📋', color: '#06b6d4' },
        condition: { label: 'Condition', icon: '🔀', color: '#f59e0b' },
        question: { label: 'Question', icon: '❓', color: '#f59e0b' },
        save_data: { label: 'Save Data', icon: '💾', color: '#10b981' },
        delay: { label: 'Delay', icon: '⏳', color: '#a855f7' },
        media: { label: 'Brochure / Media', icon: '📄', color: '#ec4899' },
        location: { label: 'Location Pin', icon: '📍', color: '#10b981' },
        human_handover: { label: 'Handover', icon: '👤', color: '#ef4444' },
        lead_status: { label: 'Lead Status', icon: '🏷️', color: '#f97316' },
        assign_telecaller: { label: 'Assign Telecaller', icon: '🎧', color: '#0ea5e9' },
        end: { label: 'End Session', icon: '🏁', color: '#64748b' }
    };

    /* ==========================================================================
       Initialization & Data Fetching
       ========================================================================== */

    async function init() {
        bindEvents();
        fetchCrmOptions();
        await fetchBusinessAccounts();
    }

    /* CRM options (lead statuses + telecallers) for the Lead Status / Assign Telecaller steps */
    const CRM_FOLLOW_UP = 'Follow-up';
    const crmOptions = { statuses: [], telecallers: [] };

    async function fetchCrmOptions() {
        try {
            const resp = await fetch('/api/crm/options/');
            if (!resp.ok) return;
            const data = await resp.json();
            crmOptions.statuses = data.statuses || [];
            crmOptions.telecallers = data.telecallers || [];
            crmOptions.branches = data.branches || [];
            if (elements.flowBranchSelect) {
                elements.flowBranchSelect.innerHTML = '<option value="">-- No Branch Assigned --</option>' +
                    crmOptions.branches.map(b => `<option value="${b.id}">${escapeHtml(b.name)}</option>`).join('');
                updateBranchSelectForActiveAccount();
            }
            if (elements.editLeadStatus) {
                elements.editLeadStatus.innerHTML = crmOptions.statuses
                    .map(s => `<option value="${escapeHtml(s.value)}">${escapeHtml(s.label)}</option>`).join('');
            }
            if (elements.editAssignTelecaller) {
                elements.editAssignTelecaller.innerHTML = '<option value="">-- Select telecaller --</option>' +
                    crmOptions.telecallers
                        .map(t => `<option value="${t.id}">${escapeHtml(t.name)}${t.is_active ? '' : ' (inactive)'}</option>`).join('');
            }
            if (state.selectedNodeId && typeof selectNode === 'function') selectNode(state.selectedNodeId);
        } catch (err) {
            console.warn('Could not load CRM options', err);
        }
    }

    function updateBranchSelectForActiveAccount() {
        if (!elements.flowBranchSelect) return;
        const currentAcc = (state.businessAccounts || []).find(a => a.id === state.selectedBusinessAccountId);
        if (currentAcc) {
            const bId = currentAcc.crm_branch_id || currentAcc.crm_branch || '';
            elements.flowBranchSelect.value = bId ? String(bId) : '';
        } else {
            elements.flowBranchSelect.value = '';
        }
    }

    function crmStatusLabel(value) {
        const s = crmOptions.statuses.find(x => x.value === value);
        return s ? s.label : (value || '?');
    }

    function crmTelecallerName(id) {
        const t = crmOptions.telecallers.find(x => String(x.id) === String(id));
        return t ? t.name : `Telecaller #${id}`;
    }

    function crmNodeSummary(node) {
        if (node.type === 'lead_status') {
            const st = node.status || node.data?.status;
            const hrs = node.follow_up_hours || node.data?.follow_up_hours;
            return `🏷️ Set lead to ${crmStatusLabel(st)}` + (hrs ? ` (follow up in ${hrs} h)` : '');
        }
        if (node.type === 'assign_telecaller') {
            const mode = node.mode || node.data?.mode || 'auto';
            const who = mode === 'specific'
                ? crmTelecallerName(node.telecaller_id || node.data?.telecaller_id)
                : 'branch telecaller (Lead Setup %)';
            const only = (node.only_if_unassigned ?? node.data?.only_if_unassigned) ? ' (if unassigned)' : '';
            return `🎧 Assign to ${who}${only}`;
        }
        return '';
    }

    async function fetchBusinessAccounts() {
        try {
            const resp = await fetch('/api/business-accounts/');
            if (!resp.ok) throw new Error('Failed to load accounts');
            const data = await resp.json();
            if (Array.isArray(data)) {
                state.businessAccounts = data;
            } else if (Array.isArray(data?.accounts)) {
                state.businessAccounts = data.accounts;
            } else if (Array.isArray(data?.results)) {
                state.businessAccounts = data.results;
            } else {
                state.businessAccounts = [];
            }

            elements.flowBusinessAccountSelect.innerHTML = '';
            if (state.businessAccounts.length === 0) {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'Global / Default Account';
                elements.flowBusinessAccountSelect.appendChild(opt);
                state.selectedBusinessAccountId = null;
            } else {
                state.businessAccounts.forEach(acc => {
                    const opt = document.createElement('option');
                    opt.value = acc.id;
                    opt.textContent = `${acc.name} (${acc.phone_number || 'Default'})`;
                    elements.flowBusinessAccountSelect.appendChild(opt);
                });
                state.selectedBusinessAccountId = state.businessAccounts[0].id;
            }
            updateBranchSelectForActiveAccount();

            await loadFlowForCurrentAccount();
        } catch (err) {
            console.error('Error loading business accounts:', err);
            showToast('Loaded offline fallback template.', true);
            useDefaultTemplate();
        }
    }

    async function loadFlowForCurrentAccount() {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const pathMatches = window.location.pathname.match(/\/(?:chat\/)?automations?\/(\d+)/i) || window.location.pathname.match(/\/automation\/(\d+)/i);
            const queryFlowId = elements.builderApp?.dataset?.flowId || urlParams.get('id') || (pathMatches ? pathMatches[1] : null);
            if (queryFlowId) {
                const flowRes = await fetch(`/api/flows/${queryFlowId}/`);
                if (flowRes.ok) {
                    state.currentFlow = await flowRes.json();
                    renderFlowMetadata();
                    renderCanvas();
                    recordHistory();
                    setSaveStatus('saved');
                    setTimeout(() => zoomFit(), 150);
                    return;
                }
            }

            const url = state.selectedBusinessAccountId
                ? `/api/flows/?business_account_id=${state.selectedBusinessAccountId}`
                : '/api/flows/';
            const resp = await fetch(url);
            if (!resp.ok) throw new Error('Failed to fetch flows');

            const data = await resp.json();
            const flows = Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : (Array.isArray(data?.flows) ? data.flows : []));
            if (flows && flows.length > 0) {
                // Prefer active published flow first, or the newest flow
                const activeFlow = flows.find(f => f.is_active && f.status === 'published');
                state.currentFlow = activeFlow || flows[0];
                renderFlowMetadata();
                renderCanvas();
                recordHistory();
                setSaveStatus('saved');
                setTimeout(() => zoomFit(), 150);
            } else {
                // Seed default
                await createDefaultFlowOnServer();
            }
        } catch (err) {
            console.warn('Using default template:', err);
            useDefaultTemplate();
        }
    }

    async function createDefaultFlowOnServer() {
        try {
            const payload = {
                business_account: state.selectedBusinessAccountId,
                name: DEFAULT_TEMPLATE.name,
                slug: 'admissions-training-flow',
                version: 1,
                status: 'published',
                trigger_type: DEFAULT_TEMPLATE.trigger_type,
                trigger_keywords: DEFAULT_TEMPLATE.trigger_keywords,
                flow_data: DEFAULT_TEMPLATE.flow_data
            };
            const resp = await fetch('/api/flows/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (resp.ok) {
                state.currentFlow = await resp.json();
                renderFlowMetadata();
                renderCanvas();
                showToast('Default Admissions Flow loaded.');
            } else {
                useDefaultTemplate();
            }
        } catch (err) {
            useDefaultTemplate();
        }
    }

    function useDefaultTemplate() {
        state.currentFlow = JSON.parse(JSON.stringify(DEFAULT_TEMPLATE));
        state.currentFlow.id = null;
        state.currentFlow.version = 1;
        state.currentFlow.status = 'draft';
        renderFlowMetadata();
        renderCanvas();
        setTimeout(() => zoomFit(), 150);
    }

    function renderFlowMetadata() {
        if (!state.currentFlow) return;
        elements.flowNameDisplay.textContent = state.currentFlow.name || 'Admissions Flow';
        elements.flowVersionTag.textContent = `v${state.currentFlow.version || 1}`;

        const isPublished = state.currentFlow.status === 'published';
        elements.flowStatusBadge.textContent = isPublished ? 'Published' : 'Draft';
        elements.flowStatusBadge.className = `status-badge ${isPublished ? 'status-published' : 'status-draft'}`;

        if (elements.btnCreateDraft) {
            elements.btnCreateDraft.style.display = isPublished ? 'inline-flex' : 'none';
        }

        elements.triggerTypeSelect.value = state.currentFlow.trigger_type || 'keyword';
        elements.triggerKeywordsInput.value = state.currentFlow.trigger_keywords || '';
        elements.triggerKeywordsBox.style.display = elements.triggerTypeSelect.value === 'keyword' ? 'block' : 'none';
    }

    /* ==========================================================================
       Canvas & Graph Rendering
       ========================================================================== */

    function renderCanvas() {
        if (!state.currentFlow || !state.currentFlow.flow_data) return;
        const nodes = state.currentFlow.flow_data.nodes || [];

        // Clear canvas
        elements.canvasNodesLayer.innerHTML = '';

        // Auto-position if coordinates are missing
        ensureNodePositions(nodes);

        // Render each node card
        nodes.forEach(node => {
            const nodeEl = createNodeCardElement(node);
            elements.canvasNodesLayer.appendChild(nodeEl);
        });

        // Redraw SVG connection lines
        drawConnectionLines();

        // Populate Next Node dropdowns in inspector
        refreshNextNodeOptions();

        // Update Minimap and Overview
        updateMinimap();
        if (!state.selectedNodeId) {
            updateFlowOverview();
        }
    }

    function ensureNodePositions(nodes) {
        let currentY = 60;
        nodes.forEach((n, idx) => {
            if (typeof n.x !== 'number') n.x = 220;
            if (typeof n.y !== 'number') {
                n.y = currentY;
                currentY += 180;
            }
        });
    }

    function createNodeCardElement(node) {
        const meta = NODE_TYPES[node.type] || { label: node.type, icon: '📦', color: '#94a3b8' };

        const card = document.createElement('div');
        card.className = `flow-node node-type-${node.type || 'message'} ${node.id === 'START' || node.type === 'trigger' ? 'start-node' : ''} ${state.selectedNodeId === node.id ? 'selected' : ''}`;
        card.id = `node-${node.id}`;
        const posX = typeof node.x === 'number' ? node.x : (node.position && typeof node.position.x === 'number' ? node.position.x : 100);
        const posY = typeof node.y === 'number' ? node.y : (node.position && typeof node.position.y === 'number' ? node.position.y : 100);
        node.x = posX;
        node.y = posY;
        if (!node.position) node.position = { x: posX, y: posY };
        card.style.left = `${posX}px`;
        card.style.top = `${posY}px`;

        // Card Header
        let choicesHtml = '';
        if (node.type === 'buttons' && Array.isArray(node.options)) {
            choicesHtml = `<div class="node-choices-preview">` +
                node.options.map(opt => `
                    <div class="choice-chip">
                        <span>🔘 ${escapeHtml(opt.title)}</span>
                        <span class="choice-target">➔ ${escapeHtml(opt.next_node_id || 'End')}</span>
                    </div>
                `).join('') + `</div>`;
        } else if (node.type === 'list' && Array.isArray(node.sections)) {
            const allRows = [];
            node.sections.forEach(s => (s.rows || []).forEach(r => allRows.push(r)));
            if (allRows.length > 0) {
                choicesHtml = `<div class="node-choices-preview">` +
                    allRows.map((r, rIdx) => {
                        const targetId = r.next_node_id || getNodeTarget(node.id, r.id || `row_${rIdx + 1}`) || (node.next_node_id || '');
                        const targetNode = (state.currentFlow?.flow_data?.nodes || []).find(n => n.id === targetId);
                        const targetLabel = targetNode ? (targetNode.title || targetNode.id) : (targetId ? targetId : 'Next');
                        return `
                            <div class="choice-chip">
                                <span>📋 ${escapeHtml(r.title || `Option ${rIdx + 1}`)}</span>
                                <span class="choice-target">➔ ${escapeHtml(targetLabel)}</span>
                            </div>
                        `;
                    }).join('') + `</div>`;
            }
        }

        let bodyPreview = '';
        if (node.body) {
            bodyPreview = `<p class="node-preview-text">${escapeHtml(node.body)}</p>`;
        } else if (node.description) {
            bodyPreview = `<p class="node-preview-text">${escapeHtml(node.description)}</p>`;
        } else if (node.type === 'media') {
            bodyPreview = `<p class="node-preview-text">📄 ${escapeHtml(node.filename || 'Document')}</p>`;
        } else if (node.type === 'location') {
            bodyPreview = `<p class="node-preview-text">📍 ${escapeHtml(node.name || 'Location')}</p>`;
        } else if (node.type === 'lead_status' || node.type === 'assign_telecaller') {
            bodyPreview = `<p class="node-preview-text">${escapeHtml(crmNodeSummary(node))}</p>`;
        }

        let nextIndicator = '';
        if (node.next_node_id) {
            nextIndicator = `<span class="node-port-out">➔ Next: ${escapeHtml(node.next_node_id)}</span>`;
        } else if (node.type === 'end') {
            nextIndicator = `<span style="color: #64748b;">🏁 Complete</span>`;
        }

        // Real-time canvas connectivity linting
        const conns = state.currentFlow?.flow_data?.connections || [];
        const hasIncoming = conns.some(c => c.target === node.id);
        const hasOutgoing = conns.some(c => c.source === node.id) || Boolean(node.next_node_id || node.yes_node_id || node.no_node_id);
        const isTrigger = ['trigger', 'start'].includes(node.type) || node.id === 'trigger_1' || node.id === 'START';
        const isEnd = ['end', 'human_handover'].includes(node.type);

        let warningBadge = '';
        if (!isTrigger && !hasIncoming) {
            warningBadge = `<span class="node-warning-badge" title="Warning: No step leads into this step.">⚠️</span>`;
        } else if (!isEnd && !hasOutgoing) {
            warningBadge = `<span class="node-warning-badge" title="Warning: This step has no outgoing connection.">⚠️</span>`;
        }

        card.innerHTML = `
            ${warningBadge}
            <div class="flow-node-header">
                <div class="node-title-group">
                    <span class="node-icon">${meta.icon}</span>
                    <span class="node-title" title="${escapeHtml(node.title)}">${escapeHtml(node.title || node.id)}</span>
                </div>
                <div class="node-header-right">
                    <span class="node-badge" style="border-left: 2px solid ${meta.color}">${meta.label}</span>
                    <div class="node-quick-actions">
                        <button type="button" class="node-quick-btn btn-node-edit" title="Configure Step">
                            <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                        </button>
                        ${!isTrigger ? `<button type="button" class="node-quick-btn btn-node-del" title="Delete Step">
                            <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>` : ''}
                    </div>
                </div>
            </div>
            <div class="flow-node-body">
                ${bodyPreview}
                ${choicesHtml}
            </div>
            <div class="flow-node-footer">
                <span style="font-family: var(--font-mono); font-size: 10px;">#${escapeHtml(node.id)}</span>
                ${nextIndicator}
            </div>
        `;

        // Wire quick header action buttons
        const btnEditQuick = card.querySelector('.btn-node-edit');
        if (btnEditQuick) {
            btnEditQuick.addEventListener('click', (e) => {
                e.stopPropagation();
                selectNode(node.id);
            });
        }
        const btnDelQuick = card.querySelector('.btn-node-del');
        if (btnDelQuick) {
            btnDelQuick.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteNode(node.id);
            });
        }

        // Render n8n-Style Interactive Port Handles
        const portsContainer = document.createElement('div');
        portsContainer.className = 'node-ports-container';

        // 1. Left Input Port (For all steps except root trigger/start)
        if (node.id !== 'START' && node.id !== 'trigger_1' && node.type !== 'start' && node.type !== 'trigger') {
            const inPort = document.createElement('div');
            inPort.className = 'node-port port-input';
            inPort.setAttribute('data-port-type', 'input');
            inPort.setAttribute('data-port-id', 'input');
            inPort.setAttribute('data-node-id', node.id);
            inPort.title = `Input Port (${node.title || node.id})`;

            inPort.addEventListener('mouseenter', () => {
                if (state.connectingFrom && state.connectingFrom.sourceNodeId !== node.id) {
                    inPort.classList.add('valid-target');
                    state.hoveredTargetPort = { nodeId: node.id, portId: 'input' };
                }
            });
            inPort.addEventListener('mouseleave', () => {
                inPort.classList.remove('valid-target');
                if (state.hoveredTargetPort?.nodeId === node.id) {
                    state.hoveredTargetPort = null;
                }
            });
            inPort.addEventListener('mouseup', (e) => {
                e.stopPropagation();
                if (state.connectingFrom && state.connectingFrom.sourceNodeId !== node.id) {
                    createConnection(
                        state.connectingFrom.sourceNodeId,
                        state.connectingFrom.sourcePortId,
                        node.id,
                        'input'
                    );
                    state.connectingFrom = null;
                    state.hoveredTargetPort = null;
                }
            });
            portsContainer.appendChild(inPort);
        }

        // 2. Right Output Port(s)
        if (node.type === 'condition') {
            // YES Port
            const yesPort = document.createElement('div');
            yesPort.className = 'node-port port-output port-yes';
            yesPort.style.top = '35%';
            yesPort.setAttribute('data-port-type', 'output');
            yesPort.setAttribute('data-port-id', 'YES');
            yesPort.setAttribute('data-node-id', node.id);
            yesPort.title = 'YES branch (Drag to connect)';
            const yesBadge = document.createElement('span');
            yesBadge.className = 'port-badge port-badge-yes';
            yesBadge.textContent = 'YES';
            yesPort.appendChild(yesBadge);
            yesPort.addEventListener('mousedown', (e) => startConnectionDrag(node.id, 'YES', e));
            portsContainer.appendChild(yesPort);

            // NO Port
            const noPort = document.createElement('div');
            noPort.className = 'node-port port-output port-no';
            noPort.style.top = '65%';
            noPort.setAttribute('data-port-type', 'output');
            noPort.setAttribute('data-port-id', 'NO');
            noPort.setAttribute('data-node-id', node.id);
            noPort.title = 'NO branch (Drag to connect)';
            const noBadge = document.createElement('span');
            noBadge.className = 'port-badge port-badge-no';
            noBadge.textContent = 'NO';
            noPort.appendChild(noBadge);
            noPort.addEventListener('mousedown', (e) => startConnectionDrag(node.id, 'NO', e));
            portsContainer.appendChild(noPort);
        } else if (node.type === 'buttons' && Array.isArray(node.options) && node.options.length > 0) {
            node.options.forEach((opt, optIdx) => {
                const optPort = document.createElement('div');
                optPort.className = 'node-port port-output';
                const topPct = Math.round(((optIdx + 1) / (node.options.length + 1)) * 100);
                optPort.style.top = `${topPct}%`;
                optPort.setAttribute('data-port-type', 'output');
                optPort.setAttribute('data-port-id', opt.id || `opt_${optIdx + 1}`);
                optPort.setAttribute('data-node-id', node.id);
                optPort.title = `Option: "${opt.title}" (Drag to connect)`;
                const optBadge = document.createElement('span');
                optBadge.className = 'port-badge';
                optBadge.textContent = `${optIdx + 1}`;
                optPort.appendChild(optBadge);
                optPort.addEventListener('mousedown', (e) => startConnectionDrag(node.id, opt.id || `opt_${optIdx + 1}`, e));
                portsContainer.appendChild(optPort);
            });
        } else if (node.type === 'list' && Array.isArray(node.sections) && (node.sections[0]?.rows?.length || 0) > 0) {
            const rows = node.sections[0].rows;
            rows.forEach((r, rIdx) => {
                const rowPort = document.createElement('div');
                rowPort.className = 'node-port port-output';
                const topPct = Math.round(((rIdx + 1) / (rows.length + 1)) * 100);
                rowPort.style.top = `${topPct}%`;
                rowPort.setAttribute('data-port-type', 'output');
                rowPort.setAttribute('data-port-id', r.id || `row_${rIdx + 1}`);
                rowPort.setAttribute('data-node-id', node.id);
                rowPort.title = `Option ${rIdx + 1}: "${r.title}" (Drag to connect)`;
                const rowBadge = document.createElement('span');
                rowBadge.className = 'port-badge';
                rowBadge.textContent = `${rIdx + 1}`;
                rowPort.appendChild(rowBadge);
                rowPort.addEventListener('mousedown', (e) => startConnectionDrag(node.id, r.id || `row_${rIdx + 1}`, e));
                portsContainer.appendChild(rowPort);
            });
        } else if (node.type !== 'end' && node.type !== 'human_handover') {
            const defPort = document.createElement('div');
            defPort.className = 'node-port port-output';
            defPort.setAttribute('data-port-type', 'output');
            defPort.setAttribute('data-port-id', 'default');
            defPort.setAttribute('data-node-id', node.id);
            defPort.title = 'Next step (Drag to connect)';
            defPort.addEventListener('mousedown', (e) => startConnectionDrag(node.id, 'default', e));
            portsContainer.appendChild(defPort);
        }

        card.appendChild(portsContainer);

        // Card Click -> Select Node
        card.addEventListener('click', (e) => {
            e.stopPropagation();
            state.selectedEdgeId = null;
            selectNode(node.id);
        });

        // Drag Handling
        const header = card.querySelector('.flow-node-header');
        header.addEventListener('mousedown', (e) => {
            initNodeDrag(node, card, e);
        });

        return card;
    }

    function initNodeDrag(node, cardEl, e) {
        state.draggedNode = node;
        const rect = cardEl.getBoundingClientRect();
        state.dragOffset = {
            x: (e.clientX - rect.left) / state.scale,
            y: (e.clientY - rect.top) / state.scale
        };

        function onMouseMove(moveEvent) {
            if (!state.draggedNode) return;
            const viewportRect = elements.canvasViewport.getBoundingClientRect();
            const newX = (moveEvent.clientX - viewportRect.left + elements.canvasViewport.scrollLeft) / state.scale - state.dragOffset.x;
            const newY = (moveEvent.clientY - viewportRect.top + elements.canvasViewport.scrollTop) / state.scale - state.dragOffset.y;

            state.draggedNode.x = Math.max(20, Math.round(newX));
            state.draggedNode.y = Math.max(20, Math.round(newY));

            cardEl.style.left = `${state.draggedNode.x}px`;
            cardEl.style.top = `${state.draggedNode.y}px`;

            drawConnectionLines();
        }

        function onMouseUp() {
            if (state.draggedNode) {
                recordHistory();
            }
            state.draggedNode = null;
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
            updateMinimap();
        }

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
    }

    /* ==========================================================================
       Interactive Port Drag-to-Connect Engine
       ========================================================================== */

    function startConnectionDrag(sourceNodeId, sourcePortId, e) {
        e.preventDefault();
        e.stopPropagation();
        state.connectingFrom = { sourceNodeId, sourcePortId };
        state.hoveredTargetPort = null;

        let dragLine = document.getElementById('activeConnectionDragLine');
        if (!dragLine) {
            dragLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            dragLine.id = 'activeConnectionDragLine';
            dragLine.setAttribute('class', 'connection-drag-path');
            dragLine.setAttribute('marker-end', 'url(#arrowhead)');
            elements.canvasSvgLayer.appendChild(dragLine);
        }

        const startCoords = getPortCoordinates(sourceNodeId, 'output', sourcePortId);

        function onMouseMove(moveEvent) {
            if (!state.connectingFrom) return;
            const planeRect = elements.canvasPlane.getBoundingClientRect();
            const mouseX = (moveEvent.clientX - planeRect.left) / state.scale;
            const mouseY = (moveEvent.clientY - planeRect.top) / state.scale;

            const d = getBezierPath(startCoords.x, startCoords.y, mouseX, mouseY);
            dragLine.setAttribute('d', d);
        }

        function onMouseUp() {
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);

            if (dragLine && dragLine.parentNode) {
                dragLine.parentNode.removeChild(dragLine);
            }

            if (state.connectingFrom && state.hoveredTargetPort) {
                createConnection(
                    state.connectingFrom.sourceNodeId,
                    state.connectingFrom.sourcePortId,
                    state.hoveredTargetPort.nodeId,
                    state.hoveredTargetPort.portId
                );
            }

            document.querySelectorAll('.node-port.valid-target').forEach(p => p.classList.remove('valid-target'));
            state.connectingFrom = null;
            state.hoveredTargetPort = null;
        }

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
    }

    function createConnection(sourceId, sourceOutput, targetId, targetInput) {
        if (!state.currentFlow?.flow_data) return;
        if (sourceId === targetId) {
            showToast('Cannot connect a step to itself.', true);
            return;
        }
        if (!state.currentFlow.flow_data.connections) {
            state.currentFlow.flow_data.connections = [];
        }

        const conns = state.currentFlow.flow_data.connections;
        const outPort = sourceOutput || 'default';
        const inPort = targetInput || 'input';

        // Disconnect existing edge for this source output port
        const existingIdx = conns.findIndex(c => c.source === sourceId && (c.source_output || 'default') === outPort);
        if (existingIdx !== -1) {
            conns.splice(existingIdx, 1);
        }

        const newConnId = `conn_${sourceId}_${outPort}_${targetId}_${Date.now()}`;
        conns.push({
            id: newConnId,
            source: sourceId,
            source_output: outPort,
            target: targetId,
            target_input: inPort
        });

        // Synchronize backward compatible node attributes
        const sourceNode = (state.currentFlow.flow_data.nodes || []).find(n => n.id === sourceId);
        if (sourceNode) {
            if (sourceNode.type === 'condition') {
                if (outPort === 'YES') sourceNode.yes_node_id = targetId;
                else if (outPort === 'NO') sourceNode.no_node_id = targetId;
            } else if (sourceNode.type === 'buttons' && Array.isArray(sourceNode.options)) {
                const opt = sourceNode.options.find(o => o.id === outPort);
                if (opt) opt.next_node_id = targetId;
            } else if (sourceNode.type === 'list' && Array.isArray(sourceNode.sections)) {
                const row = (sourceNode.sections[0]?.rows || []).find(r => r.id === outPort);
                if (row) row.next_node_id = targetId;
                else sourceNode.next_node_id = targetId;
            } else {
                sourceNode.next_node_id = targetId;
            }
        }

        state.selectedEdgeId = newConnId;
        renderCanvas();
        recordHistory();
        setSaveStatus('unsaved');
        showToast('Connected steps.');
    }

    function selectEdge(edgeId) {
        state.selectedEdgeId = edgeId;
        if (edgeId) {
            state.selectedNodeId = null;
            selectNode(null);
        }
        drawConnectionLines();
    }

    function deleteEdge(edgeId) {
        if (!state.currentFlow?.flow_data?.connections) return;
        const conns = state.currentFlow.flow_data.connections;
        const edgeIndex = conns.findIndex(c => c.id === edgeId);
        if (edgeIndex === -1) return;
        const removedConn = conns.splice(edgeIndex, 1)[0];

        // Clear backward compatible node pointer
        const sourceNode = (state.currentFlow.flow_data.nodes || []).find(n => n.id === removedConn.source);
        if (sourceNode) {
            if (sourceNode.type === 'condition') {
                if (removedConn.source_output === 'YES') sourceNode.yes_node_id = null;
                else if (removedConn.source_output === 'NO') sourceNode.no_node_id = null;
            } else if (sourceNode.type === 'buttons' && Array.isArray(sourceNode.options)) {
                const opt = sourceNode.options.find(o => o.id === removedConn.source_output);
                if (opt) opt.next_node_id = null;
            } else if (sourceNode.type === 'list' && Array.isArray(sourceNode.sections)) {
                const row = (sourceNode.sections[0]?.rows || []).find(r => r.id === removedConn.source_output);
                if (row) row.next_node_id = null;
                else if (sourceNode.next_node_id === removedConn.target) sourceNode.next_node_id = null;
            } else {
                if (sourceNode.next_node_id === removedConn.target) {
                    sourceNode.next_node_id = null;
                }
            }
        }

        state.selectedEdgeId = null;
        renderCanvas();
        recordHistory();
        setSaveStatus('unsaved');
        showToast('Connection removed.');
    }

    function getPortCoordinates(nodeId, portType, portId) {
        const nodeCard = document.getElementById(`node-${nodeId}`);
        const CARD_WIDTH = 290;
        if (!nodeCard) {
            const node = (state.currentFlow?.flow_data?.nodes || []).find(n => n.id === nodeId);
            const x = node ? (node.position?.x ?? node.x ?? 240) : 240;
            const y = node ? (node.position?.y ?? node.y ?? 40) : 40;
            return {
                x: portType === 'input' ? x : x + CARD_WIDTH,
                y: y + 70
            };
        }

        const selector = portType === 'input'
            ? `.node-port.port-input`
            : `.node-port.port-output[data-port-id="${portId}"]`;
        const portEl = nodeCard.querySelector(selector);
        if (portEl) {
            const planeRect = elements.canvasPlane.getBoundingClientRect();
            const portRect = portEl.getBoundingClientRect();
            return {
                x: (portRect.left + portRect.width / 2 - planeRect.left) / state.scale,
                y: (portRect.top + portRect.height / 2 - planeRect.top) / state.scale
            };
        }

        // Fallback using card bounding box inside canvasPlane
        const planeRect = elements.canvasPlane.getBoundingClientRect();
        const cardRect = nodeCard.getBoundingClientRect();
        const cardX = (cardRect.left - planeRect.left) / state.scale;
        const cardY = (cardRect.top - planeRect.top) / state.scale;
        const cardW = cardRect.width / state.scale;
        const cardH = cardRect.height / state.scale;

        if (portType === 'input') {
            return { x: cardX, y: cardY + cardH / 2 };
        }
        return { x: cardX + cardW, y: cardY + cardH / 2 };
    }

    function getBezierPath(x1, y1, x2, y2) {
        const dx = Math.abs(x2 - x1);
        const curvature = Math.max(50, dx * 0.45);
        const cp1x = x1 + curvature;
        const cp1y = y1;
        const cp2x = x2 - curvature;
        const cp2y = y2;
        return `M ${x1} ${y1} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x2} ${y2}`;
    }

    function getBezierMidpoint(x1, y1, x2, y2) {
        const dx = Math.abs(x2 - x1);
        const curvature = Math.max(50, dx * 0.45);
        const cp1x = x1 + curvature;
        const cp1y = y1;
        const cp2x = x2 - curvature;
        const cp2y = y2;
        return {
            x: 0.125 * x1 + 0.375 * cp1x + 0.375 * cp2x + 0.125 * x2,
            y: 0.125 * y1 + 0.375 * cp1y + 0.375 * cp2y + 0.125 * y2
        };
    }

    /* ==========================================================================
       SVG Connection Connectors (Bezier Curves & Hitareas)
       ========================================================================== */

    function drawConnectionLines() {
        if (!state.currentFlow || !state.currentFlow.flow_data) return;
        const nodes = state.currentFlow.flow_data.nodes || [];
        const nodeMap = {};
        nodes.forEach(n => nodeMap[n.id] = n);

        // Ensure connections array exists and is populated
        if (!Array.isArray(state.currentFlow.flow_data.connections) || state.currentFlow.flow_data.connections.length === 0) {
            state.currentFlow.flow_data.connections = [];
            nodes.forEach(source => {
                if (source.type === 'condition') {
                    if (source.yes_node_id && nodeMap[source.yes_node_id]) {
                        state.currentFlow.flow_data.connections.push({
                            id: `conn_${source.id}_YES_${source.yes_node_id}`,
                            source: source.id,
                            source_output: 'YES',
                            target: source.yes_node_id,
                            target_input: 'input'
                        });
                    }
                    if (source.no_node_id && nodeMap[source.no_node_id]) {
                        state.currentFlow.flow_data.connections.push({
                            id: `conn_${source.id}_NO_${source.no_node_id}`,
                            source: source.id,
                            source_output: 'NO',
                            target: source.no_node_id,
                            target_input: 'input'
                        });
                    }
                } else if (source.type === 'buttons' && Array.isArray(source.options)) {
                    source.options.forEach((opt, optIdx) => {
                        if (opt.next_node_id && nodeMap[opt.next_node_id]) {
                            state.currentFlow.flow_data.connections.push({
                                id: `conn_${source.id}_${opt.id || optIdx + 1}_${opt.next_node_id}`,
                                source: source.id,
                                source_output: opt.id || `opt_${optIdx + 1}`,
                                target: opt.next_node_id,
                                target_input: 'input'
                            });
                        }
                    });
                } else if (source.type === 'list' && Array.isArray(source.sections)) {
                    (source.sections[0]?.rows || []).forEach((r, rIdx) => {
                        if (r.next_node_id && nodeMap[r.next_node_id]) {
                            state.currentFlow.flow_data.connections.push({
                                id: `conn_${source.id}_${r.id || rIdx + 1}_${r.next_node_id}`,
                                source: source.id,
                                source_output: r.id || `row_${rIdx + 1}`,
                                target: r.next_node_id,
                                target_input: 'input'
                            });
                        }
                    });
                    if (source.next_node_id && nodeMap[source.next_node_id]) {
                        state.currentFlow.flow_data.connections.push({
                            id: `conn_${source.id}_default_${source.next_node_id}`,
                            source: source.id,
                            source_output: 'default',
                            target: source.next_node_id,
                            target_input: 'input'
                        });
                    }
                } else if (source.next_node_id && nodeMap[source.next_node_id]) {
                    state.currentFlow.flow_data.connections.push({
                        id: `conn_${source.id}_default_${source.next_node_id}`,
                        source: source.id,
                        source_output: 'default',
                        target: source.next_node_id,
                        target_input: 'input'
                    });
                }
            });
        }

        // Ensure all connections have an ID
        state.currentFlow.flow_data.connections.forEach((c, idx) => {
            if (!c.id) c.id = `conn_${c.source}_${c.source_output || 'default'}_${c.target}_${idx}`;
        });

        // Clear existing SVG paths (retain defs)
        const defs = elements.canvasSvgLayer.querySelector('defs');
        elements.canvasSvgLayer.innerHTML = '';
        if (defs) elements.canvasSvgLayer.appendChild(defs);

        const connections = state.currentFlow.flow_data.connections;
        connections.forEach(conn => {
            const source = nodeMap[conn.source];
            const target = nodeMap[conn.target];
            if (!source || !target) return;

            const isSelected = state.selectedEdgeId === conn.id;
            const startPt = getPortCoordinates(conn.source, 'output', conn.source_output || 'default');
            const endPt = getPortCoordinates(conn.target, 'input', conn.target_input || 'input');
            const d = getBezierPath(startPt.x, startPt.y, endPt.x, endPt.y);

            let stroke = '#10b981';
            if (conn.source_output === 'YES') stroke = '#34d399';
            else if (conn.source_output === 'NO') stroke = '#ef4444';
            else if (conn.source_output && conn.source_output !== 'default') stroke = '#8b5cf6';

            // SVG Group for interactive edge
            const edgeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            edgeGroup.setAttribute('class', `connection-group ${isSelected ? 'selected' : ''}`);
            edgeGroup.setAttribute('data-edge-id', conn.id);

            // Invisible wide hitarea for easy clicking
            const hitarea = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            hitarea.setAttribute('d', d);
            hitarea.setAttribute('class', 'connection-hitarea');
            hitarea.setAttribute('stroke', 'transparent');
            hitarea.setAttribute('stroke-width', '18');
            hitarea.setAttribute('fill', 'none');
            hitarea.style.cursor = 'pointer';

            hitarea.addEventListener('click', (e) => {
                e.stopPropagation();
                selectEdge(conn.id);
            });

            // Visible path
            const visiblePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            visiblePath.setAttribute('d', d);
            visiblePath.setAttribute('class', `connection-path active ${isSelected ? 'selected' : ''}`);
            visiblePath.setAttribute('stroke', stroke);
            visiblePath.setAttribute('marker-end', 'url(#arrowhead)');

            edgeGroup.appendChild(hitarea);
            edgeGroup.appendChild(visiblePath);

            // If selected, render delete button at Bezier midpoint
            if (isSelected) {
                const mid = getBezierMidpoint(startPt.x, startPt.y, endPt.x, endPt.y);
                const delGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                delGroup.setAttribute('class', 'edge-delete-btn');
                delGroup.setAttribute('transform', `translate(${mid.x}, ${mid.y})`);
                delGroup.style.cursor = 'pointer';
                delGroup.innerHTML = `
                    <circle r="12" fill="#ef4444" stroke="#ffffff" stroke-width="2" />
                    <text text-anchor="middle" dominant-baseline="central" fill="#ffffff" font-size="14" font-weight="bold">×</text>
                `;
                delGroup.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteEdge(conn.id);
                });
                edgeGroup.appendChild(delGroup);
            }

            elements.canvasSvgLayer.appendChild(edgeGroup);
        });
    }

    /* ==========================================================================
       Property Inspector (Editing Nodes)
       ========================================================================== */

    function getNodeTargetId(nodeId, outputPort = 'default') {
        return getNodeTarget(nodeId, outputPort);
    }

    function getNodeTarget(nodeId, outputPort = 'default') {
        const conns = state.currentFlow?.flow_data?.connections || [];
        const match = conns.find(c => c.source === nodeId && (c.source_output === outputPort || (!c.source_output && outputPort === 'default')));
        return match ? match.target : null;
    }

    function setNodeConnection(sourceId, outputPort, targetId) {
        if (!state.currentFlow?.flow_data) return;
        if (!state.currentFlow.flow_data.connections) state.currentFlow.flow_data.connections = [];
        const conns = state.currentFlow.flow_data.connections;
        const idx = conns.findIndex(c => c.source === sourceId && (c.source_output === outputPort || (!c.source_output && outputPort === 'default')));
        if (targetId) {
            if (idx !== -1) {
                conns[idx].target = targetId;
            } else {
                conns.push({
                    id: `conn_${sourceId}_${outputPort}_${targetId}_${Date.now()}`,
                    source: sourceId,
                    source_output: outputPort,
                    target: targetId,
                    target_input: 'input'
                });
            }
        } else {
            if (idx !== -1) {
                conns.splice(idx, 1);
            }
        }
    }

    function selectNode(nodeId) {
        if (state.selectedNodeId && state.selectedNodeId !== nodeId) {
            applyInspectorChanges(false);
        }
        state.selectedNodeId = nodeId;

        // Highlight selected card
        document.querySelectorAll('.flow-node').forEach(el => el.classList.remove('selected'));
        const activeCard = document.getElementById(`node-${nodeId}`);
        if (activeCard) activeCard.classList.add('selected');

        const nodes = state.currentFlow.flow_data.nodes || [];
        const node = nodes.find(n => n.id === nodeId);

        if (!node) {
            if (elements.flowOverviewPanel) {
                elements.flowOverviewPanel.style.display = 'block';
                updateFlowOverview();
            }
            if (elements.emptyInspectorState) elements.emptyInspectorState.style.display = 'none';
            if (elements.inspectorForm) elements.inspectorForm.style.display = 'none';
            return;
        }

        if (elements.flowOverviewPanel) elements.flowOverviewPanel.style.display = 'none';
        if (elements.emptyInspectorState) elements.emptyInspectorState.style.display = 'none';
        elements.inspectorForm.style.display = 'flex';
        refreshNextNodeOptions();

        const meta = NODE_TYPES[node.type] || { label: node.type, icon: '📦' };
        elements.inspectorNodeBadge.textContent = `${meta.icon} ${meta.label}`;
        elements.inspectorTitle.textContent = node.title || node.id;

        // Populate fields
        elements.editNodeId.value = node.id;
        elements.editNodeTitle.value = node.title || '';
        elements.editNodeBody.value = node.body || node.description || (node.data && (node.data.text || node.data.body)) || '';

        // Reset visibility
        elements.groupMessageBody.style.display = 'block';
        elements.groupInteractiveHeaders.style.display = 'none';
        elements.groupVariableName.style.display = 'none';
        elements.groupButtonsOptions.style.display = 'none';
        elements.groupListRows.style.display = 'none';
        elements.groupConditionDetails.style.display = 'none';
        elements.groupSaveDataDetails.style.display = 'none';
        elements.groupDelayDetails.style.display = 'none';
        elements.groupMediaDetails.style.display = 'none';
        elements.groupLocationDetails.style.display = 'none';
        if (elements.groupLeadStatusDetails) elements.groupLeadStatusDetails.style.display = 'none';
        if (elements.groupAssignDetails) elements.groupAssignDetails.style.display = 'none';
        elements.groupNextNode.style.display = 'block';

        // Type-specific field population
        if (node.type === 'buttons') {
            elements.groupInteractiveHeaders.style.display = 'flex';
            elements.groupVariableName.style.display = 'block';
            elements.groupButtonsOptions.style.display = 'block';
            elements.editNodeHeader.value = node.header || (node.data && node.data.header) || '';
            elements.editNodeFooter.value = node.footer || (node.data && node.data.footer) || '';
            elements.editVariableName.value = node.variable_name || (node.data && node.data.variable_name) || '';
            renderButtonsOptionsEditor(node.options || (node.data && node.data.options) || []);
        } else if (node.type === 'list') {
            elements.groupInteractiveHeaders.style.display = 'flex';
            elements.groupVariableName.style.display = 'block';
            elements.groupListRows.style.display = 'block';
            elements.editNodeHeader.value = node.header || (node.data && node.data.header) || '';
            elements.editNodeFooter.value = node.footer || (node.data && node.data.footer) || '';
            elements.editVariableName.value = node.variable_name || (node.data && node.data.variable_name) || '';
            const isDb = (node.data?.source || node.source) === 'database';
            elements.editListSource.value = isDb ? 'database' : 'custom';
            elements.customListRowsContainer.style.display = isDb ? 'none' : 'block';
            renderListRowsEditor(node.sections || []);
        } else if (node.type === 'condition') {
            elements.groupMessageBody.style.display = 'none';
            elements.groupNextNode.style.display = 'none';
            elements.groupConditionDetails.style.display = 'block';
            elements.editConditionVariable.value = node.data?.variable || node.variable || node.variable_name || '';
            elements.editConditionOperator.value = node.data?.operator || node.operator || 'contains';
            elements.editConditionValue.value = node.data?.value || node.value || '';

            const otherNodes = (state.currentFlow.flow_data.nodes || []).filter(n => n.id !== node.id);
            elements.editConditionYesTarget.innerHTML = '<option value="">-- Stop / End --</option>';
            elements.editConditionNoTarget.innerHTML = '<option value="">-- Stop / End --</option>';

            const currentYes = node.yes_node_id || getNodeTarget(node.id, 'YES');
            const currentNo = node.no_node_id || getNodeTarget(node.id, 'NO');

            otherNodes.forEach(n => {
                const optYes = document.createElement('option');
                optYes.value = n.id;
                optYes.textContent = `${n.title || n.id} (#${n.id})`;
                if (n.id === currentYes) optYes.selected = true;
                elements.editConditionYesTarget.appendChild(optYes);

                const optNo = document.createElement('option');
                optNo.value = n.id;
                optNo.textContent = `${n.title || n.id} (#${n.id})`;
                if (n.id === currentNo) optNo.selected = true;
                elements.editConditionNoTarget.appendChild(optNo);
            });
        } else if (node.type === 'save_data') {
            elements.groupMessageBody.style.display = 'none';
            elements.groupSaveDataDetails.style.display = 'block';
            elements.editSaveDataKey.value = node.data?.variable || node.data?.key || node.variable_name || node.key || '';
            elements.editSaveDataValue.value = node.data?.value || node.value || '';
        } else if (node.type === 'delay') {
            elements.groupMessageBody.style.display = 'none';
            elements.groupDelayDetails.style.display = 'block';
            elements.editDelaySeconds.value = node.data?.seconds || node.seconds || 5;
        } else if (node.type === 'question') {
            elements.groupVariableName.style.display = 'block';
            elements.editVariableName.value = node.variable_name || (node.data && node.data.variable_name) || '';
            if (elements.editQuestionExpectedType) {
                elements.editQuestionExpectedType.value = node.expected_type || (node.data && node.data.expected_type) || 'text';
            }
            if (elements.editQuestionRetryLimit) {
                elements.editQuestionRetryLimit.value = node.retry_limit || (node.data && node.data.retry_limit) || 3;
            }
            if (elements.editQuestionInvalidMessage) {
                elements.editQuestionInvalidMessage.value = node.invalid_message || (node.data && node.data.invalid_message) || '';
            }
        } else if (node.type === 'media') {
            elements.groupMediaDetails.style.display = 'block';
            const isDbBrochure = (node.data?.source || node.source) === 'selected_course_brochure';
            elements.editMediaSource.value = isDbBrochure ? 'selected_course_brochure' : 'custom_url';
            elements.customMediaFields.style.display = isDbBrochure ? 'none' : 'block';
            elements.editMediaUrl.value = node.media_url || node.data?.fallback_url || '';
            elements.editMediaFilename.value = node.filename || '';
            elements.editMediaCaption.value = node.caption || (node.data && node.data.caption) || '';
        } else if (node.type === 'location') {
            elements.groupLocationDetails.style.display = 'block';
            const isDynamicBranch = (node.data?.source || node.source) === 'dynamic_branch';
            elements.editLocationSource.value = isDynamicBranch ? 'dynamic_branch' : 'custom_pin';
            elements.customLocationFields.style.display = isDynamicBranch ? 'none' : 'block';
            elements.editLocationName.value = node.name || (node.data && node.data.fallback_name) || '';
            elements.editLocationAddress.value = node.address || (node.data && node.data.fallback_address) || '';
            elements.editLocationLat.value = node.latitude || (node.data && node.data.fallback_latitude) || '';
            elements.editLocationLng.value = node.longitude || (node.data && node.data.fallback_longitude) || '';
        } else if (node.type === 'lead_status') {
            elements.groupMessageBody.style.display = 'none';
            elements.groupLeadStatusDetails.style.display = 'block';
            const st = node.status || node.data?.status || 'Interested';
            elements.editLeadStatus.value = st;
            elements.editFollowUpHours.value = node.follow_up_hours || node.data?.follow_up_hours || '';
            elements.groupFollowUpHours.style.display = st === CRM_FOLLOW_UP ? 'block' : 'none';
        } else if (node.type === 'assign_telecaller') {
            elements.groupMessageBody.style.display = 'none';
            elements.groupAssignDetails.style.display = 'block';
            const mode = node.mode || node.data?.mode || 'auto';
            elements.editAssignMode.value = mode;
            elements.editAssignTelecaller.value = String(node.telecaller_id || node.data?.telecaller_id || '');
            elements.groupAssignTelecaller.style.display = mode === 'specific' ? 'block' : 'none';
            elements.editAssignOnlyUnassigned.checked = Boolean(node.only_if_unassigned ?? node.data?.only_if_unassigned);
        } else if (node.type === 'end' || node.type === 'human_handover') {
            elements.groupNextNode.style.display = 'none';
        }

        // Set next node
        const currentTarget = node.next_node_id || getNodeTarget(node.id, 'default') || '';
        elements.editNextNodeId.value = currentTarget;

        // START or trigger node cannot be deleted
        elements.btnDeleteNode.style.display = (node.id === 'START' || node.id === 'trigger_1' || node.type === 'trigger' || node.type === 'start') ? 'none' : 'block';

        updateLivePreview();
    }

    function renderButtonsOptionsEditor(options) {
        elements.buttonsOptionsList.innerHTML = '';
        const nodes = (state.currentFlow.flow_data.nodes || []).filter(n => n.id !== state.selectedNodeId);

        options.forEach((opt, idx) => {
            const row = document.createElement('div');
            row.className = 'inspector-option-row';
            row.innerHTML = `
                <div class="option-row-inputs">
                    <input type="text" class="form-control opt-title-input" placeholder="Button Title (max 20 chars)" value="${escapeHtml(opt.title)}" maxlength="20">
                    <button type="button" class="option-remove-btn" title="Remove Option" data-idx="${idx}">&times;</button>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 11px; color: var(--text-muted);">➔ Next:</span>
                    <select class="form-control opt-target-select">
                        <option value="">-- Stop / End --</option>
                        ${nodes.map(n => `<option value="${n.id}" ${opt.next_node_id === n.id ? 'selected' : ''}>${escapeHtml(n.title || n.id)}</option>`).join('')}
                    </select>
                </div>
            `;

            row.querySelector('.option-remove-btn').addEventListener('click', () => {
                options.splice(idx, 1);
                renderButtonsOptionsEditor(options);
            });

            elements.buttonsOptionsList.appendChild(row);
        });

        elements.btnAddOptionBtn.style.display = options.length >= 3 ? 'none' : 'block';
        let limitNotice = elements.buttonsOptionsList.querySelector('.meta-button-limit-notice');
        if (!limitNotice) {
            limitNotice = document.createElement('div');
            limitNotice.className = 'meta-button-limit-notice';
            limitNotice.style.cssText = 'font-size: 11px; color: #f59e0b; padding: 6px 8px; background: rgba(245, 158, 11, 0.1); border-radius: 4px; margin-top: 8px; border-left: 2px solid #f59e0b;';
            limitNotice.innerHTML = '⚠️ <strong>Meta WhatsApp rule:</strong> Maximum 3 quick-reply buttons allowed. For questions with 4 to 10 choices, use a <strong>List Menu</strong> step.';
            elements.buttonsOptionsList.appendChild(limitNotice);
        }
        limitNotice.style.display = options.length >= 3 ? 'block' : 'none';
    }

    function renderListRowsEditor(sections) {
        elements.listRowsContainer.innerHTML = '';
        if (sections.length === 0) sections.push({ title: 'Options', rows: [] });

        const section = sections[0];
        const rows = section.rows || [];

        rows.forEach((rowItem, idx) => {
            const rowEl = document.createElement('div');
            rowEl.className = 'inspector-option-row';
            const curTitle = rowItem.title || '';
            rowEl.innerHTML = `
                <div class="option-row-inputs">
                    <input type="text" class="form-control list-title-input" placeholder="Option Title (max 24 chars)" maxlength="24" value="${escapeHtml(curTitle)}">
                    <button type="button" class="option-remove-btn" title="Remove option" data-idx="${idx}">&times;</button>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px; gap: 8px;">
                    <input type="text" class="form-control list-desc-input" placeholder="Short description (optional, max 72)" maxlength="72" value="${escapeHtml(rowItem.description || '')}" style="font-size: 11px; flex: 1;">
                    <span class="char-count-pill" style="font-size: 10px; color: var(--text-muted);">${curTitle.length}/24</span>
                </div>
            `;

            const titleInput = rowEl.querySelector('.list-title-input');
            const countPill = rowEl.querySelector('.char-count-pill');
            titleInput.addEventListener('input', () => {
                countPill.textContent = `${titleInput.value.length}/24`;
                if (titleInput.value.length >= 24) {
                    countPill.style.color = '#ef4444';
                } else {
                    countPill.style.color = 'var(--text-muted)';
                }
            });

            rowEl.querySelector('.option-remove-btn').addEventListener('click', () => {
                rows.splice(idx, 1);
                renderListRowsEditor(sections);
                renderCanvas();
                recordHistory();
                setSaveStatus('unsaved');
            });

            elements.listRowsContainer.appendChild(rowEl);
        });

        if (elements.btnAddListRowBtn) {
            elements.btnAddListRowBtn.style.display = rows.length >= 10 ? 'none' : 'block';
        }
    }

    function refreshNextNodeOptions() {
        const nodes = state.currentFlow?.flow_data?.nodes || [];
        elements.editNextNodeId.innerHTML = '<option value="">-- Complete / Stop --</option>';

        nodes.forEach(n => {
            if (n.id !== state.selectedNodeId) {
                const opt = document.createElement('option');
                opt.value = n.id;
                opt.textContent = `${n.title || n.id} (#${n.id})`;
                elements.editNextNodeId.appendChild(opt);
            }
        });
    }

    function applyInspectorChanges(showNotification = true) {
        if (!state.selectedNodeId || !state.currentFlow) return;
        const nodes = state.currentFlow.flow_data.nodes || [];
        const node = nodes.find(n => n.id === state.selectedNodeId);
        if (!node) return;

        node.title = elements.editNodeTitle.value.trim();
        node.body = elements.editNodeBody.value.trim();
        if (node.data) {
            node.data.text = node.body;
            node.data.title = node.title;
        }
        node.next_node_id = elements.editNextNodeId.value || null;

        if (node.type === 'buttons') {
            node.header = elements.editNodeHeader.value.trim();
            node.footer = elements.editNodeFooter.value.trim();
            node.variable_name = elements.editVariableName.value.trim() || 'choice';

            const optionRows = elements.buttonsOptionsList.querySelectorAll('.inspector-option-row');
            const newOptions = [];
            optionRows.forEach((row, idx) => {
                const title = row.querySelector('.opt-title-input').value.trim();
                const target = row.querySelector('.opt-target-select').value;
                if (title) {
                    const optId = `opt_${idx + 1}`;
                    newOptions.push({
                        id: optId,
                        title: title.slice(0, 20),
                        next_node_id: target || null
                    });
                    setNodeConnection(node.id, optId, target || null);
                }
            });
            node.options = newOptions;
            if (!node.data) node.data = {};
            node.data.header = node.header;
            node.data.footer = node.footer;
            node.data.variable_name = node.variable_name;
            node.data.options = newOptions;
        } else if (node.type === 'list') {
            node.header = elements.editNodeHeader.value.trim();
            node.footer = elements.editNodeFooter.value.trim();
            node.variable_name = elements.editVariableName.value.trim() || 'selection';

            if (!node.data) node.data = {};
            node.data.header = node.header;
            node.data.footer = node.footer;
            node.data.variable_name = node.variable_name;

            if (elements.editListSource.value === 'database') {
                node.source = 'database';
                node.data.source = 'database';
            } else {
                node.source = 'custom';
                node.data.source = 'custom';
                const listRowEls = elements.listRowsContainer.querySelectorAll('.inspector-option-row');
                const newRows = [];
                listRowEls.forEach((row, idx) => {
                    const title = row.querySelector('.list-title-input').value.trim();
                    const desc = row.querySelector('.list-desc-input').value.trim();
                    if (title) {
                        newRows.push({
                            id: `row_${idx + 1}`,
                            title: title,
                            description: desc
                        });
                    }
                });
                node.sections = [{ title: 'Programs', rows: newRows }];
                node.data.sections = node.sections;
            }
            setNodeConnection(node.id, 'default', node.next_node_id);
        } else if (node.type === 'condition') {
            node.variable_name = elements.editConditionVariable.value.trim();
            node.operator = elements.editConditionOperator.value;
            node.value = elements.editConditionValue.value.trim();
            node.yes_node_id = elements.editConditionYesTarget.value || null;
            node.no_node_id = elements.editConditionNoTarget.value || null;
            if (!node.data) node.data = {};
            node.data.variable = node.variable_name;
            node.data.operator = node.operator;
            node.data.value = node.value;
            setNodeConnection(node.id, 'YES', node.yes_node_id);
            setNodeConnection(node.id, 'NO', node.no_node_id);
        } else if (node.type === 'save_data') {
            node.key = elements.editSaveDataKey.value.trim();
            node.value = elements.editSaveDataValue.value.trim();
            if (!node.data) node.data = {};
            node.data.variable = node.key;
            node.data.value = node.value;
            setNodeConnection(node.id, 'default', node.next_node_id);
        } else if (node.type === 'delay') {
            node.seconds = parseInt(elements.editDelaySeconds.value, 10) || 5;
            if (!node.data) node.data = {};
            node.data.seconds = node.seconds;
            setNodeConnection(node.id, 'default', node.next_node_id);
        } else if (node.type === 'question') {
            node.variable_name = elements.editVariableName.value.trim() || 'user_input';
            node.expected_type = elements.editQuestionExpectedType ? elements.editQuestionExpectedType.value : 'text';
            node.retry_limit = elements.editQuestionRetryLimit ? (parseInt(elements.editQuestionRetryLimit.value, 10) || 3) : 3;
            node.invalid_message = elements.editQuestionInvalidMessage ? elements.editQuestionInvalidMessage.value.trim() : '';
            if (!node.data) node.data = {};
            node.data.variable_name = node.variable_name;
            node.data.expected_type = node.expected_type;
            node.data.retry_limit = node.retry_limit;
            node.data.invalid_message = node.invalid_message;
            setNodeConnection(node.id, 'default', node.next_node_id);
        } else if (node.type === 'media') {
            if (!node.data) node.data = {};
            if (elements.editMediaSource.value === 'selected_course_brochure') {
                node.source = 'selected_course_brochure';
                node.data.source = 'selected_course_brochure';
            } else {
                node.source = 'custom_url';
                node.data.source = 'custom_url';
                node.media_url = elements.editMediaUrl.value.trim();
                node.filename = elements.editMediaFilename.value.trim();
                node.data.fallback_url = node.media_url;
            }
            node.caption = elements.editMediaCaption.value.trim();
            node.data.caption = node.caption;
            setNodeConnection(node.id, 'default', node.next_node_id);
        } else if (node.type === 'location') {
            if (!node.data) node.data = {};
            if (elements.editLocationSource.value === 'dynamic_branch') {
                node.source = 'dynamic_branch';
                node.data.source = 'dynamic_branch';
            } else {
                node.source = 'custom_pin';
                node.data.source = 'custom_pin';
                node.name = elements.editLocationName.value.trim();
                node.address = elements.editLocationAddress.value.trim();
                node.latitude = parseFloat(elements.editLocationLat.value) || 13.0827;
                node.longitude = parseFloat(elements.editLocationLng.value) || 80.2707;
                node.data.fallback_name = node.name;
                node.data.fallback_address = node.address;
                node.data.fallback_latitude = node.latitude;
                node.data.fallback_longitude = node.longitude;
            }
            setNodeConnection(node.id, 'default', node.next_node_id);
        } else if (node.type === 'lead_status') {
            if (!node.data) node.data = {};
            node.status = elements.editLeadStatus.value;
            const hrs = parseFloat(elements.editFollowUpHours.value);
            node.follow_up_hours = node.status === CRM_FOLLOW_UP && hrs > 0 ? hrs : null;
            node.data.status = node.status;
            node.data.follow_up_hours = node.follow_up_hours;
            setNodeConnection(node.id, 'default', node.next_node_id);
        } else if (node.type === 'assign_telecaller') {
            if (!node.data) node.data = {};
            node.mode = elements.editAssignMode.value;
            node.telecaller_id = node.mode === 'specific' ? (parseInt(elements.editAssignTelecaller.value, 10) || null) : null;
            node.only_if_unassigned = elements.editAssignOnlyUnassigned.checked;
            node.data.mode = node.mode;
            node.data.telecaller_id = node.telecaller_id;
            node.data.only_if_unassigned = node.only_if_unassigned;
            setNodeConnection(node.id, 'default', node.next_node_id);
        } else {
            setNodeConnection(node.id, 'default', node.next_node_id);
        }

        renderCanvas();
        recordHistory();
        if (showNotification) {
            showToast(`Updated "${node.title}"`);
        }
    }

    function deleteSelectedNode() {
        if (!state.selectedNodeId || state.selectedNodeId === 'START' || state.selectedNodeId === 'trigger_1') return;
        const node = (state.currentFlow?.flow_data?.nodes || []).find(n => n.id === state.selectedNodeId);
        const nodeName = node ? (node.title || node.id) : state.selectedNodeId;

        showConfirmDialog(
            'Delete Step',
            `Are you sure you want to delete "${nodeName}"? Any connections pointing to this step will be disconnected.`,
            'Delete Step',
            true,
            () => {
                const nodes = state.currentFlow.flow_data.nodes || [];
                const idx = nodes.findIndex(n => n.id === state.selectedNodeId);
                if (idx !== -1) {
                    const deletedId = state.selectedNodeId;
                    nodes.splice(idx, 1);

                    // Clear pointers to deleted node
                    nodes.forEach(n => {
                        if (n.next_node_id === deletedId) n.next_node_id = null;
                        if (n.yes_node_id === deletedId) n.yes_node_id = null;
                        if (n.no_node_id === deletedId) n.no_node_id = null;
                        if (n.options) {
                            n.options.forEach(o => {
                                if (o.next_node_id === deletedId) o.next_node_id = null;
                            });
                        }
                    });

                    // Clean connections
                    if (state.currentFlow.flow_data.connections) {
                        state.currentFlow.flow_data.connections = state.currentFlow.flow_data.connections.filter(
                            c => c.source !== deletedId && c.target !== deletedId
                        );
                    }

                    state.selectedNodeId = null;
                    selectNode(null);
                    renderCanvas();
                    recordHistory();
                    showToast('Step removed from flow.');
                }
            }
        );
    }

    /* ==========================================================================
       Add Node from Palette
       ========================================================================== */

    function addNewNode(type, customPos = null, customData = null) {
        if (!state.currentFlow) return;
        if (!state.currentFlow.flow_data) state.currentFlow.flow_data = { nodes: [], connections: [] };
        if (!state.currentFlow.flow_data.nodes) state.currentFlow.flow_data.nodes = [];
        const nodes = state.currentFlow.flow_data.nodes;
        const meta = NODE_TYPES[type] || { label: type ? type.toUpperCase() : 'New Step' };

        const newId = `node_${type || 'step'}_${Date.now().toString().slice(-4)}`;

        // Place below lowest node, near selected node, or in visible viewport center
        let posX = 240;
        let posY = 100;
        if (customPos && typeof customPos.x === 'number' && typeof customPos.y === 'number') {
            posX = customPos.x;
            posY = customPos.y;
        } else {
            const vp = elements.canvasViewport;
            if (state.selectedNodeId) {
                const sel = nodes.find(n => n.id === state.selectedNodeId);
                if (sel) {
                    posX = (sel.x || sel.position?.x || 240);
                    posY = (sel.y || sel.position?.y || 100) + 160;
                }
            } else if (vp) {
                const vpRect = vp.getBoundingClientRect();
                posX = Math.max(40, Math.round((vp.scrollLeft + vpRect.width / 2) / state.scale) - 120);
                posY = Math.max(40, Math.round((vp.scrollTop + vpRect.height / 2) / state.scale) - 60);
            } else {
                let maxY = 40;
                nodes.forEach(n => {
                    const ny = n.position ? n.position.y : (n.y || 0);
                    if (ny > maxY) maxY = ny;
                });
                posY = maxY + 180;
            }
        }

        const newNode = {
            id: newId,
            type: type || 'message',
            title: `${meta.label} Step`,
            position: { x: posX, y: posY },
            x: posX,
            y: posY,
            next_node_id: null,
            data: {}
        };

        if (type === 'trigger' || type === 'start') {
            const trigType = customData?.trigger_type || 'first_incoming_message';
            newNode.title = trigType === 'keyword' ? 'Keyword Trigger' : 'Incoming Message Trigger';
            newNode.data = { trigger_type: trigType };
            if (trigType === 'keyword') {
                newNode.trigger_keywords = 'course, admission, fees';
                newNode.data.keywords = 'course, admission, fees';
            }
        } else if (type === 'message') {
            newNode.body = 'Hello! Here is your update.';
            newNode.data.text = newNode.body;
        } else if (type === 'buttons') {
            newNode.header = 'Choices';
            newNode.body = 'Please choose an option:';
            newNode.variable_name = 'choice';
            newNode.options = [
                { id: 'opt_1', title: 'Option 1', next_node_id: null },
                { id: 'opt_2', title: 'Option 2', next_node_id: null }
            ];
            newNode.data = {
                header: newNode.header,
                text: newNode.body,
                variable_name: newNode.variable_name,
                options: newNode.options
            };
        } else if (type === 'list') {
            newNode.header = 'Available Courses';
            newNode.body = 'Select the technology:';
            newNode.variable_name = 'course';
            newNode.source = 'database';
            newNode.data = {
                source: 'database',
                header: newNode.header,
                text: newNode.body,
                button_text: 'View Courses',
                variable_name: 'course'
            };
        } else if (type === 'condition') {
            newNode.title = 'Check Condition';
            newNode.variable_name = 'branch_visit';
            newNode.operator = 'contains';
            newNode.value = 'YES';
            newNode.yes_node_id = null;
            newNode.no_node_id = null;
            newNode.data = {
                variable: 'branch_visit',
                operator: 'contains',
                value: 'YES'
            };
        } else if (type === 'save_data') {
            newNode.title = 'Save Data';
            newNode.key = 'course_id';
            newNode.value = '1';
            newNode.data = {
                variable: 'course_id',
                value: '1'
            };
        } else if (type === 'delay') {
            newNode.title = 'Delay';
            newNode.seconds = 5;
            newNode.data = { seconds: 5 };
        } else if (type === 'question') {
            newNode.body = 'Please reply with your preferred date and time:';
            newNode.variable_name = 'visit_slot';
            newNode.data = {
                text: newNode.body,
                variable_name: 'visit_slot'
            };
        } else if (type === 'media') {
            newNode.source = 'selected_course_brochure';
            newNode.caption = 'Here is the course brochure.';
            newNode.data = {
                source: 'selected_course_brochure',
                caption: newNode.caption
            };
        } else if (type === 'location') {
            newNode.source = 'dynamic_branch';
            newNode.data = {
                source: 'dynamic_branch'
            };
        } else if (type === 'lead_status') {
            newNode.title = 'Mark as Interested';
            newNode.status = 'Interested';
            newNode.follow_up_hours = null;
            newNode.data = { status: 'Interested', follow_up_hours: null };
        } else if (type === 'assign_telecaller') {
            newNode.title = 'Assign Telecaller';
            newNode.mode = 'auto';
            newNode.telecaller_id = null;
            newNode.only_if_unassigned = true;
            newNode.data = { mode: 'auto', telecaller_id: null, only_if_unassigned: true };
        } else if (type === 'human_handover') {
            newNode.title = 'Handover to Agent';
            newNode.body = 'Conversation handed over to human support counselor.';
            newNode.data = { text: newNode.body };
        } else if (type === 'end') {
            newNode.body = 'Session completed. Thank you!';
            newNode.data = { text: newNode.body };
        }

        nodes.push(newNode);
        renderCanvas();
        recordHistory();
        selectNode(newId);
        showToast(`Added ${meta.label} step.`);
    }

    /* ==========================================================================
       Auto Layout & Zoom Controls
       ========================================================================== */

    function autoLayoutGraph() {
        if (!state.currentFlow?.flow_data?.nodes) return;
        const nodes = state.currentFlow.flow_data.nodes;
        if (nodes.length === 0) return;

        const conns = state.currentFlow.flow_data.connections || [];
        const nodeMap = {};
        nodes.forEach(n => nodeMap[n.id] = n);

        // Find incoming connection count
        const incomingCount = {};
        nodes.forEach(n => incomingCount[n.id] = 0);
        conns.forEach(c => {
            if (incomingCount[c.target] !== undefined) incomingCount[c.target]++;
        });

        // Roots: trigger/start nodes or nodes with 0 incoming connections
        const rootNodes = nodes.filter(n => ['trigger', 'start'].includes(n.type) || incomingCount[n.id] === 0);
        if (rootNodes.length === 0) rootNodes.push(nodes[0]);

        // BFS traversal to assign DAG levels
        const levels = {};
        const queue = [];
        rootNodes.forEach(r => {
            levels[r.id] = 0;
            queue.push(r.id);
        });

        const visited = new Set();
        while (queue.length > 0) {
            const currId = queue.shift();
            if (visited.has(currId)) continue;
            visited.add(currId);

            const currLevel = levels[currId] || 0;
            const targets = [];
            conns.forEach(c => {
                if (c.source === currId && c.target && nodeMap[c.target]) {
                    targets.push(c.target);
                }
            });
            const nodeObj = nodeMap[currId];
            if (nodeObj) {
                if (nodeObj.next_node_id && nodeMap[nodeObj.next_node_id]) targets.push(nodeObj.next_node_id);
                if (nodeObj.yes_node_id && nodeMap[nodeObj.yes_node_id]) targets.push(nodeObj.yes_node_id);
                if (nodeObj.no_node_id && nodeMap[nodeObj.no_node_id]) targets.push(nodeObj.no_node_id);
                if (Array.isArray(nodeObj.options)) {
                    nodeObj.options.forEach(o => {
                        if (o.next_node_id && nodeMap[o.next_node_id]) targets.push(o.next_node_id);
                    });
                }
            }

            targets.forEach(tgtId => {
                const nextLevel = currLevel + 1;
                if (levels[tgtId] === undefined || levels[tgtId] < nextLevel) {
                    levels[tgtId] = nextLevel;
                }
                if (!visited.has(tgtId)) {
                    queue.push(tgtId);
                }
            });
        }

        // Handle any unvisited nodes
        let maxLvl = 0;
        Object.values(levels).forEach(l => { if (l > maxLvl) maxLvl = l; });
        nodes.forEach(n => {
            if (levels[n.id] === undefined) {
                maxLvl++;
                levels[n.id] = maxLvl;
            }
        });

        // Group nodes by level
        const columns = {};
        nodes.forEach(n => {
            const lvl = levels[n.id] !== undefined ? levels[n.id] : 0;
            if (!columns[lvl]) columns[lvl] = [];
            columns[lvl].push(n);
        });

        const X_GAP = 360;
        const Y_GAP = 230;
        const START_X = 80;
        const START_Y = 80;

        Object.keys(columns).sort((a, b) => Number(a) - Number(b)).forEach(lvlStr => {
            const lvl = Number(lvlStr);
            const colNodes = columns[lvl];
            colNodes.forEach((node, idx) => {
                node.x = START_X + lvl * X_GAP;
                node.y = START_Y + idx * Y_GAP;
                if (!node.position) node.position = {};
                node.position.x = node.x;
                node.position.y = node.y;
            });
        });

        renderCanvas();
        recordHistory();
        setSaveStatus('unsaved');
        showToast('Workflows automatically organized into clean graph layout.');
    }

    function setZoom(newScale) {
        state.scale = Math.min(1.5, Math.max(0.5, newScale));
        elements.canvasPlane.style.transform = `scale(${state.scale})`;
        elements.zoomLevelText.textContent = `${Math.round(state.scale * 100)}%`;
        drawConnectionLines();
    }

    /* ==========================================================================
       Draft & Publish APIs
       ========================================================================== */

    async function saveDraft() {
        if (!state.currentFlow) return;

        applyInspectorChanges(false);
        setSaveStatus('saving');

        // Sync metadata
        state.currentFlow.name = elements.flowNameDisplay.textContent.trim() || 'WhatsApp Automation Flow';
        state.currentFlow.trigger_type = elements.triggerTypeSelect.value;
        state.currentFlow.trigger_keywords = elements.triggerKeywordsInput.value.trim();
        state.currentFlow.business_account = state.selectedBusinessAccountId;

        const isPublished = state.currentFlow.status === 'published';
        const payload = {
            ...state.currentFlow,
            auto_fork_draft: isPublished
        };

        try {
            const method = state.currentFlow.id ? 'PUT' : 'POST';
            const endpoint = state.currentFlow.id ? `/api/flows/${state.currentFlow.id}/` : '/api/flows/';

            const resp = await fetch(endpoint, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                if (errData.code === 'PUBLISHED_IMMUTABLE') {
                    return await createNewDraft();
                }
                throw new Error(errData.error || 'Save failed');
            }
            const data = await resp.json();
            state.currentFlow = data;
            renderFlowMetadata();
            setSaveStatus('saved');
            showToast(isPublished ? `Forked into editable draft v${state.currentFlow.version}!` : 'Draft saved successfully!');
        } catch (err) {
            console.error('Error saving draft:', err);
            setSaveStatus('unsaved');
            showToast('Error saving draft: ' + (err.message || 'Server error'), true);
        }
    }

    async function createNewDraft() {
        if (!state.currentFlow?.id) return;
        try {
            const resp = await fetch(`/api/flows/${state.currentFlow.id}/create-draft/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                throw new Error(data.error || 'Failed to create draft');
            }
            const data = await resp.json();
            state.currentFlow = data.flow;
            renderFlowMetadata();
            renderCanvas();
            recordHistory();
            setSaveStatus('saved');
            showToast(`Created draft v${state.currentFlow.version}! You can now edit.`);
        } catch (err) {
            console.error(err);
            showToast(err.message || 'Failed to create draft version', true);
        }
    }

    function renderValidationIssues(errors) {
        if (!elements.validationErrorList || !elements.validationModalBackdrop) return;
        elements.validationErrorList.innerHTML = '';
        errors.forEach(err => {
            const li = document.createElement('li');
            li.style.display = 'flex';
            li.style.justifyContent = 'space-between';
            li.style.alignItems = 'center';
            li.style.gap = '8px';
            li.style.marginBottom = '6px';

            const span = document.createElement('span');
            const errText = typeof err === 'string' ? err : (err.message || JSON.stringify(err));
            span.textContent = errText;
            li.appendChild(span);

            let nodeId = typeof err === 'object' && err.node_id ? err.node_id : null;
            if (!nodeId && typeof err === 'string') {
                const match = err.match(/node\s+["']?([a-zA-Z0-9_-]+)["']?/i) || err.match(/#([a-zA-Z0-9_-]+)/);
                if (match && match[1]) nodeId = match[1];
            }

            if (nodeId && nodeId !== 'root' && nodeId !== 'connections') {
                const fixBtn = document.createElement('button');
                fixBtn.type = 'button';
                fixBtn.textContent = 'Fix';
                fixBtn.className = 'btn-fix-node';
                fixBtn.addEventListener('click', () => {
                    elements.validationModalBackdrop.style.display = 'none';
                    focusAndSelectNode(nodeId);
                });
                li.appendChild(fixBtn);
            }
            elements.validationErrorList.appendChild(li);
        });
        elements.validationModalBackdrop.style.display = 'flex';
        showToast('Validation failed: check issues', true);
    }

    async function validateFlowAction() {
        if (!state.currentFlow?.flow_data) return;
        applyInspectorChanges(false);
        try {
            showToast('Validating workflow...');
            const resp = await fetch('/api/flows/validate/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ flow_data: state.currentFlow.flow_data })
            });
            const data = await resp.json();
            if (data.valid) {
                showToast('✓ Workflow is completely valid and ready to publish!');
            } else {
                renderValidationIssues(data.errors || []);
            }
        } catch (err) {
            console.error('Validation error:', err);
            showToast('Failed to validate flow.', true);
        }
    }

    async function openVersionHistory() {
        if (!state.currentFlow?.id) {
            showToast('Save a flow before viewing versions.', true);
            return;
        }
        if (!elements.versionHistoryModal || !elements.versionHistoryList) return;
        elements.versionHistoryList.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">Loading version history...</div>';
        elements.versionHistoryModal.style.display = 'flex';

        try {
            const resp = await fetch(`/api/flows/${state.currentFlow.id}/versions/`);
            if (!resp.ok) throw new Error('Failed to load version history');
            const versions = await resp.json();
            if (!Array.isArray(versions) || versions.length === 0) {
                elements.versionHistoryList.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">No version records found.</div>';
                return;
            }

            elements.versionHistoryList.innerHTML = '';
            versions.forEach(v => {
                const card = document.createElement('div');
                card.className = 'version-item-card';
                const isCurrent = v.id === state.currentFlow.id;
                const statusBadge = v.status === 'published' 
                    ? '<span class="status-badge status-published">Published</span>' 
                    : '<span class="status-badge status-draft">Draft</span>';
                
                const createdDate = v.created_at ? new Date(v.created_at).toLocaleString() : 'Recent';
                const nodeCount = (v.flow_data?.nodes || []).length;

                card.innerHTML = `
                    <div class="version-item-meta">
                        <div class="version-item-title">
                            <span>v${v.version} — ${escapeHtml(v.name)}</span>
                            ${statusBadge}
                            ${isCurrent ? '<span style="font-size: 11px; color: #10b981; font-weight: 700;">(Current)</span>' : ''}
                        </div>
                        <div class="version-item-date">Created: ${createdDate} • ${nodeCount} steps</div>
                    </div>
                    <div>
                        ${!isCurrent ? `<button type="button" class="btn-restore-version" data-id="${v.id}">Restore as Draft</button>` : '<span style="color: var(--text-muted); font-size: 12px;">Active</span>'}
                    </div>
                `;

                const restoreBtn = card.querySelector('.btn-restore-version');
                if (restoreBtn) {
                    restoreBtn.addEventListener('click', async () => {
                        restoreVersionToDraft(v.id);
                    });
                }
                elements.versionHistoryList.appendChild(card);
            });
        } catch (err) {
            console.error('Version error:', err);
            elements.versionHistoryList.innerHTML = '<div style="text-align: center; color: #ef4444; padding: 20px;">Failed to load versions.</div>';
        }
    }

    async function restoreVersionToDraft(flowId) {
        showConfirmDialog(
            'Restore Version',
            'This will clone this historical version into a new editable draft without modifying the live active flow. Continue?',
            'Restore Version',
            false,
            async () => {
                try {
                    const resp = await fetch(`/api/flows/${flowId}/restore-version/`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    if (!resp.ok) throw new Error('Restore failed');
                    const data = await resp.json();
                    state.currentFlow = data.flow;
                    if (elements.versionHistoryModal) elements.versionHistoryModal.style.display = 'none';
                    renderFlowMetadata();
                    renderCanvas();
                    recordHistory();
                    setSaveStatus('saved');
                    showToast(data.message || 'Restored version successfully!');
                } catch (err) {
                    showToast('Failed to restore version.', true);
                }
            }
        );
    }

    async function publishFlow() {
        if (!state.currentFlow) return;

        applyInspectorChanges(false);

        // First save if draft
        if (state.currentFlow.status !== 'published') {
            await saveDraft();
        }

        if (!state.currentFlow.id) {
            showToast('Please save draft before publishing.', true);
            return;
        }

        showConfirmDialog(
            'Publish Live Flow',
            `Are you sure you want to publish Version ${state.currentFlow.version || 1} live? This will activate it for all incoming customer messages.`,
            'Publish Live',
            false,
            async () => {
                try {
                    const resp = await fetch(`/api/flows/${state.currentFlow.id}/publish/`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });

                    if (!resp.ok) {
                        const data = await resp.json().catch(() => ({}));
                        if (data.details && Array.isArray(data.details)) {
                            renderValidationIssues(data.details);
                            return;
                        }
                        throw new Error(data.error || 'Publish failed');
                    }
                    const data = await resp.json();
                    state.currentFlow = data.flow;
                    renderFlowMetadata();
                    setSaveStatus('saved');
                    showToast(`🚀 Published Live as Version ${state.currentFlow.version}!`);
                } catch (err) {
                    console.error('Publish error:', err);
                    showToast(err.message || 'Error publishing flow.', true);
                }
            }
        );
    }

    /* ==========================================================================
       WhatsApp Chatbot Simulator
       ========================================================================== */

    function openSimulator() {
        elements.simulatorBackdrop.classList.add('open');
        elements.simulatorDrawer.classList.add('open');
        state.simState.isOpen = true;
        updateSimTelemetry();
        restartSimulation();
    }

    function closeSimulator() {
        elements.simulatorBackdrop.classList.remove('open');
        elements.simulatorDrawer.classList.remove('open');
        elements.simListSheet.classList.remove('open');
        state.simState.isOpen = false;
        document.querySelectorAll('.flow-node.sim-active').forEach(el => el.classList.remove('sim-active'));
        updateSimTelemetry();
    }

    function restartSimulation() {
        elements.simMessages.innerHTML = '';
        state.simState.collectedData = {};
        elements.simListSheet.classList.remove('open');
        document.querySelectorAll('.flow-node.sim-active').forEach(el => el.classList.remove('sim-active'));
        updateSimTelemetry();

        // Start from START, trigger, or first node
        const nodes = state.currentFlow?.flow_data?.nodes || [];
        const startNode = nodes.find(n => n.id === 'START' || n.id === 'trigger_1' || n.type === 'start' || n.type === 'trigger') || nodes[0];
        if (!startNode) return;

        const nextId = startNode.next_node_id || getNodeTarget(startNode.id, 'default') || startNode.id;
        executeSimNode(nextId);
    }

    function executeSimNode(nodeId) {
        if (!nodeId) return;
        const nodes = state.currentFlow?.flow_data?.nodes || [];
        const node = nodes.find(n => n.id === nodeId);
        if (!node) return;

        state.simState.currentNodeId = nodeId;
        updateSimTelemetry();

        // Canvas tracing & node glow
        document.querySelectorAll('.flow-node.sim-active').forEach(el => el.classList.remove('sim-active'));
        const activeCard = document.getElementById(`node-${nodeId}`);
        if (activeCard) {
            activeCard.classList.add('sim-active');
            activeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
        }

        // 1. Text Message
        if (node.type === 'message') {
            const rawBody = node.body || (node.data && (node.data.text || node.data.body)) || '';
            const body = interpolateText(rawBody, state.simState.collectedData);
            addSimBotBubble(body);
            const nextTarget = node.next_node_id || getNodeTarget(node.id, 'default');
            if (nextTarget) {
                setTimeout(() => executeSimNode(nextTarget), 600);
            }
        }
        // 2. Buttons
        else if (node.type === 'buttons') {
            const rawBody = node.body || (node.data && (node.data.text || node.data.body)) || '';
            const body = interpolateText(rawBody, state.simState.collectedData);
            addSimBotButtons(body, node);
        }
        // 3. List
        else if (node.type === 'list') {
            const rawBody = node.body || (node.data && (node.data.text || node.data.body)) || '';
            const body = interpolateText(rawBody, state.simState.collectedData);
            addSimBotList(body, node);
        }
        // 4. Condition
        else if (node.type === 'condition') {
            const varName = node.variable_name || (node.data && node.data.variable) || '';
            const op = node.operator || (node.data && node.data.operator) || 'contains';
            const val = node.value || (node.data && node.data.value) || '';
            const actual = state.simState.collectedData[varName] || '';
            let isTrue = false;
            const actStr = String(actual).toLowerCase().trim();
            const tgtStr = String(val).toLowerCase().trim();
            if (op === 'equals') isTrue = actStr === tgtStr;
            else if (op === 'not_equals') isTrue = actStr !== tgtStr;
            else if (op === 'contains') isTrue = actStr.includes(tgtStr);
            else if (op === 'not_contains') isTrue = !actStr.includes(tgtStr);
            else if (op === 'exists') isTrue = Boolean(actual);

            const nextTarget = isTrue
                ? (node.yes_node_id || getNodeTarget(node.id, 'YES'))
                : (node.no_node_id || getNodeTarget(node.id, 'NO'));

            if (nextTarget) {
                setTimeout(() => executeSimNode(nextTarget), 400);
            }
        }
        // 5. Save Data
        else if (node.type === 'save_data') {
            const k = node.key || (node.data && node.data.variable) || 'variable';
            const v = node.value || (node.data && node.data.value) || '';
            state.simState.collectedData[k] = interpolateText(v, state.simState.collectedData);
            const nextTarget = node.next_node_id || getNodeTarget(node.id, 'default');
            if (nextTarget) {
                setTimeout(() => executeSimNode(nextTarget), 300);
            }
        }
        // 6. Delay
        else if (node.type === 'delay') {
            const s = node.seconds || (node.data && node.data.seconds) || 1;
            const nextTarget = node.next_node_id || getNodeTarget(node.id, 'default');
            if (nextTarget) {
                setTimeout(() => executeSimNode(nextTarget), 500);
            }
        }
        // 7. Question
        else if (node.type === 'question') {
            const rawBody = node.body || (node.data && (node.data.text || node.data.body)) || '';
            const body = interpolateText(rawBody, state.simState.collectedData);
            addSimBotBubble(body);
        }
        // 8. Media
        else if (node.type === 'media') {
            addSimBotMedia(node);
            const nextTarget = node.next_node_id || getNodeTarget(node.id, 'default');
            if (nextTarget) {
                setTimeout(() => executeSimNode(nextTarget), 600);
            }
        }
        // 9. Location
        else if (node.type === 'location') {
            addSimBotLocation(node);
            const nextTarget = node.next_node_id || getNodeTarget(node.id, 'default');
            if (nextTarget) {
                setTimeout(() => executeSimNode(nextTarget), 600);
            }
        }
        // CRM steps: nothing is sent to the student; show what the CRM would do
        else if (node.type === 'lead_status' || node.type === 'assign_telecaller') {
            addSimCrmNote(crmNodeSummary(node));
            const nextTarget = node.next_node_id || getNodeTarget(node.id, 'default');
            if (nextTarget) {
                setTimeout(() => executeSimNode(nextTarget), 300);
            }
        }
        // 10. End
        else if (node.type === 'end') {
            const rawBody = node.body || (node.data && (node.data.text || node.data.body)) || 'Session completed.';
            const body = interpolateText(rawBody, state.simState.collectedData);
            addSimBotBubble(body);
        }
        // 11. Human Handover
        else if (node.type === 'human_handover') {
            addSimBotBubble("👤 Handed over to admissions counselor.");
        }
    }

    function handleSimUserInput(text) {
        if (!text.trim()) return;
        addSimUserBubble(text);

        const nodes = state.currentFlow?.flow_data?.nodes || [];
        const currNode = nodes.find(n => n.id === state.simState.currentNodeId);

        if (!currNode) {
            restartSimulation();
            return;
        }

        if (currNode.type === 'question') {
            const expectedType = currNode.expected_type || currNode.data?.expected_type || 'text';
            const rawVal = text.trim();
            let isValid = true;
            let invalidMsg = currNode.invalid_message || currNode.data?.invalid_message || '';

            if (expectedType === 'number') {
                if (!/^\d+(\.\d+)?$/.test(rawVal.replace(/\s+/g, ''))) {
                    isValid = false;
                    if (!invalidMsg) invalidMsg = 'Please enter a valid numeric value.';
                }
            } else if (expectedType === 'email') {
                if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(rawVal)) {
                    isValid = false;
                    if (!invalidMsg) invalidMsg = 'Please enter a valid email address.';
                }
            }

            if (!isValid) {
                currNode._sim_retries = (currNode._sim_retries || 0) + 1;
                const maxRetries = parseInt(currNode.retry_limit || currNode.data?.retry_limit || 3, 10);
                if (currNode._sim_retries >= maxRetries) {
                    addSimBotBubble(`⚠️ Maximum retry limit reached (${maxRetries}). Continuing...`);
                    currNode._sim_retries = 0;
                    const nextId = currNode.next_node_id || getNodeTarget(currNode.id, 'default');
                    if (nextId) setTimeout(() => executeSimNode(nextId), 600);
                } else {
                    addSimBotBubble(`⚠️ ${invalidMsg} (Attempt ${currNode._sim_retries}/${maxRetries})`);
                }
                return;
            }

            currNode._sim_retries = 0;
            const varName = currNode.variable_name || 'input';
            state.simState.collectedData[varName] = rawVal;
            updateSimTelemetry();
            const nextTarget = currNode.next_node_id || getNodeTarget(currNode.id, 'default');
            if (nextTarget) {
                setTimeout(() => executeSimNode(nextTarget), 500);
            }
        } else if (currNode.type === 'buttons') {
            const opt = (currNode.options || []).find(o => o.title.toLowerCase() === text.toLowerCase());
            if (opt) {
                selectSimOption(opt, currNode);
            } else {
                addSimBotBubble("Please tap one of the provided options above.");
            }
        }
    }

    function selectSimOption(opt, node) {
        addSimUserBubble(opt.title);
        const varName = node.variable_name || 'choice';
        state.simState.collectedData[varName] = opt.title;
        updateSimTelemetry();

        const nextId = opt.next_node_id || node.next_node_id;
        setTimeout(() => executeSimNode(nextId), 500);
    }

    function selectSimListRow(row, node) {
        elements.simListSheet.classList.remove('open');
        addSimUserBubble(row.title);
        const varName = node.variable_name || 'selection';
        state.simState.collectedData[varName] = row.title;
        updateSimTelemetry();

        const nextId = node.next_node_id;
        setTimeout(() => executeSimNode(nextId), 500);
    }

    function addSimCrmNote(text) {
        const note = document.createElement('div');
        note.className = 'sim-crm-note';
        note.textContent = `CRM: ${text} (not sent to student)`;
        elements.simMessages.appendChild(note);
        if (typeof scrollSimToBottom === 'function') scrollSimToBottom();
    }

    function interpolateText(text, data) {
        return text.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, key) => data[key] || `[${key}]`);
    }

    function addSimBotBubble(text) {
        const bubble = document.createElement('div');
        bubble.className = 'sim-bubble sim-bubble-bot';
        bubble.innerHTML = `
            <div>${formatWhatsAppMarkdown(text)}</div>
            <div class="sim-bubble-time">${getCurrentTime()}</div>
        `;
        elements.simMessages.appendChild(bubble);
        scrollSimToBottom();
    }

    function addSimUserBubble(text) {
        const bubble = document.createElement('div');
        bubble.className = 'sim-bubble sim-bubble-user';
        bubble.innerHTML = `
            <div>${escapeHtml(text)}</div>
            <div class="sim-bubble-meta">
                <span class="sim-bubble-time">${getCurrentTime()}</span>
                <span class="sim-double-tick" title="Read">
                    <svg viewBox="0 0 16 15" width="15" height="14" fill="none">
                        <path d="M15.01 3.316l-7.79 7.789a.5.5 0 01-.707 0L2.99 7.581a.5.5 0 11.707-.707l3.17 3.17 7.436-7.435a.5.5 0 11.707.707z" fill="#53bdeb"/>
                        <path d="M12.01 3.316l-7.79 7.789a.5.5 0 01-.707 0L.09 7.581a.5.5 0 11.707-.707l3.17 3.17 7.436-7.435a.5.5 0 11.707.707z" fill="#53bdeb"/>
                    </svg>
                </span>
            </div>
        `;
        elements.simMessages.appendChild(bubble);
        scrollSimToBottom();
    }

    function addSimBotButtons(bodyText, node) {
        const bubble = document.createElement('div');
        bubble.className = 'sim-bubble sim-bubble-bot';

        let btnsHtml = `<div class="sim-buttons-wrap">`;
        (node.options || []).forEach(opt => {
            btnsHtml += `
            <button type="button" class="sim-btn-choice" data-id="${opt.id}">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 10 4 15 9 20"></polyline><path d="M20 4v7a4 4 0 0 1-4 4H4"></path></svg>
                <span>${escapeHtml(opt.title)}</span>
            </button>`;
        });
        btnsHtml += `</div>`;

        bubble.innerHTML = `
            ${node.header ? `<div style="font-size: 11px; font-weight: 700; color: #34d399; margin-bottom: 4px;">${escapeHtml(node.header)}</div>` : ''}
            <div>${formatWhatsAppMarkdown(bodyText)}</div>
            ${btnsHtml}
            ${node.footer ? `<div style="font-size: 10px; color: #8696a0; margin-top: 4px;">${escapeHtml(node.footer)}</div>` : ''}
            <div class="sim-bubble-time">${getCurrentTime()}</div>
        `;

        bubble.querySelectorAll('.sim-btn-choice').forEach(btn => {
            btn.addEventListener('click', () => {
                const optId = btn.getAttribute('data-id');
                const opt = (node.options || []).find(o => o.id === optId);
                if (opt) selectSimOption(opt, node);
            });
        });

        elements.simMessages.appendChild(bubble);
        scrollSimToBottom();
    }

    function addSimBotList(bodyText, node) {
        const bubble = document.createElement('div');
        bubble.className = 'sim-bubble sim-bubble-bot';

        bubble.innerHTML = `
            ${node.header ? `<div style="font-size: 11px; font-weight: 700; color: #34d399; margin-bottom: 4px;">${escapeHtml(node.header)}</div>` : ''}
            <div>${formatWhatsAppMarkdown(bodyText)}</div>
            <button type="button" class="sim-list-btn">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
                <span>${escapeHtml(node.button_text || 'View Options')}</span>
            </button>
            <div class="sim-bubble-time">${getCurrentTime()}</div>
        `;

        bubble.querySelector('.sim-list-btn').addEventListener('click', () => {
            openSimListSheet(node);
        });

        elements.simMessages.appendChild(bubble);
        scrollSimToBottom();
    }

    function openSimListSheet(node) {
        elements.simSheetTitle.textContent = node.header || 'Select Course';
        elements.simSheetItems.innerHTML = '';

        const sections = node.sections || [];
        sections.forEach(sec => {
            (sec.rows || []).forEach(r => {
                const item = document.createElement('div');
                item.className = 'sim-sheet-item';
                item.innerHTML = `
                    <div class="sim-sheet-item-title">${escapeHtml(r.title)}</div>
                    <div class="sim-sheet-item-desc">${escapeHtml(r.description || '')}</div>
                `;
                item.addEventListener('click', () => selectSimListRow(r, node));
                elements.simSheetItems.appendChild(item);
            });
        });

        elements.simListSheet.classList.add('open');
    }

    function addSimBotMedia(node) {
        const bubble = document.createElement('div');
        bubble.className = 'sim-bubble sim-bubble-bot';

        bubble.innerHTML = `
            <div class="sim-media-card">
                <span class="sim-media-icon">📄</span>
                <div class="sim-media-info">
                    <div class="sim-media-filename">${escapeHtml(node.filename || 'Brochure.pdf')}</div>
                    <div style="font-size: 10px; color: #8696a0;">PDF Document • 2.4 MB</div>
                </div>
            </div>
            ${node.caption ? `<div>${formatWhatsAppMarkdown(interpolateText(node.caption, state.simState.collectedData))}</div>` : ''}
            <div class="sim-bubble-time">${getCurrentTime()}</div>
        `;
        elements.simMessages.appendChild(bubble);
        scrollSimToBottom();
    }

    function addSimBotLocation(node) {
        const bubble = document.createElement('div');
        bubble.className = 'sim-bubble sim-bubble-bot';

        bubble.innerHTML = `
            <div class="sim-location-card">
                <div class="sim-loc-title">📍 ${escapeHtml(node.name || 'Branch Location')}</div>
                <div class="sim-loc-addr">${escapeHtml(node.address || '')}</div>
                <div style="font-size: 10px; color: #34d399; margin-top: 4px;">Tap to open in Google Maps</div>
            </div>
            <div class="sim-bubble-time">${getCurrentTime()}</div>
        `;
        elements.simMessages.appendChild(bubble);
        scrollSimToBottom();
    }

    function scrollSimToBottom() {
        elements.simMessages.scrollTop = elements.simMessages.scrollHeight;
    }

    function updateSimTelemetry() {
        if (elements.debugSessionStatus) {
            elements.debugSessionStatus.textContent = state.simState.isOpen ? 'ACTIVE' : 'IDLE';
            elements.debugSessionStatus.className = state.simState.isOpen ? 'status-pill active' : 'status-pill idle';
        }
        if (elements.debugCurrentNode) {
            elements.debugCurrentNode.textContent = state.simState.currentNodeId || 'None';
        }
        if (elements.debugFlowVersion) {
            elements.debugFlowVersion.textContent = `v${state.currentFlow?.version || 1} (${state.currentFlow?.status || 'draft'})`;
        }
        if (elements.debugCollectedData) {
            elements.debugCollectedData.textContent = JSON.stringify(state.simState.collectedData, null, 2);
        }
    }

    /* ==========================================================================
       History, Save Status & Visual State Helpers
       ========================================================================== */

    function setSaveStatus(status) {
        if (!elements.saveStatusDot || !elements.saveStatusText) return;
        if (status === 'saved') {
            elements.saveStatusDot.style.background = '#10b981';
            elements.saveStatusText.textContent = 'Saved just now';
        } else if (status === 'saving') {
            elements.saveStatusDot.style.background = '#f59e0b';
            elements.saveStatusText.textContent = 'Saving...';
        } else if (status === 'unsaved') {
            elements.saveStatusDot.style.background = '#94a3b8';
            elements.saveStatusText.textContent = 'Unsaved changes';
        }
    }

    function recordHistory() {
        if (!state.currentFlow || !state.currentFlow.flow_data) return;
        const snapshot = JSON.stringify(state.currentFlow.flow_data);

        if (state.historyIndex >= 0 && state.history[state.historyIndex] === snapshot) {
            return;
        }

        state.history = state.history.slice(0, state.historyIndex + 1);
        state.history.push(snapshot);
        if (state.history.length > 30) state.history.shift();
        state.historyIndex = state.history.length - 1;

        updateHistoryButtons();
        setSaveStatus('unsaved');
    }

    function undo() {
        if (state.historyIndex > 0) {
            state.historyIndex--;
            state.currentFlow.flow_data = JSON.parse(state.history[state.historyIndex]);
            renderCanvas();
            updateHistoryButtons();
            setSaveStatus('unsaved');
            showToast('Undo action');
        }
    }

    function redo() {
        if (state.historyIndex < state.history.length - 1) {
            state.historyIndex++;
            state.currentFlow.flow_data = JSON.parse(state.history[state.historyIndex]);
            renderCanvas();
            updateHistoryButtons();
            setSaveStatus('unsaved');
            showToast('Redo action');
        }
    }

    function updateHistoryButtons() {
        const canUndo = state.historyIndex > 0;
        const canRedo = state.historyIndex < state.history.length - 1;

        if (elements.btnUndo) elements.btnUndo.disabled = !canUndo;
        if (elements.btnBottomUndo) elements.btnBottomUndo.disabled = !canUndo;
        if (elements.btnRedo) elements.btnRedo.disabled = !canRedo;
        if (elements.btnBottomRedo) elements.btnBottomRedo.disabled = !canRedo;
    }

    function updateFlowOverview() {
        if (!state.currentFlow) return;
        if (elements.overviewFlowName) elements.overviewFlowName.textContent = state.currentFlow.name || 'Admissions Flow';
        if (elements.overviewFlowVersion) elements.overviewFlowVersion.textContent = `v${state.currentFlow.version || 1}`;
        if (elements.overviewFlowStatus) {
            const isPub = state.currentFlow.status === 'published';
            elements.overviewFlowStatus.textContent = isPub ? 'Published' : 'Draft';
            elements.overviewFlowStatus.className = `status-badge ${isPub ? 'status-published' : 'status-draft'}`;
        }
        if (elements.overviewFlowTrigger) {
            elements.overviewFlowTrigger.textContent = (state.currentFlow.trigger_type || 'keyword').toUpperCase();
        }
        const nodes = state.currentFlow.flow_data?.nodes || [];
        const conns = state.currentFlow.flow_data?.connections || [];
        if (elements.overviewNodeCount) elements.overviewNodeCount.textContent = nodes.length;
        if (elements.overviewConnectionCount) elements.overviewConnectionCount.textContent = conns.length;
    }

    function updateLivePreview() {
        if (!elements.messageLivePreview) return;
        const bodyVal = elements.editNodeBody?.value || '';
        const headerVal = elements.editNodeHeader?.value || '';
        const footerVal = elements.editNodeFooter?.value || '';
        const selectedNode = (state.currentFlow?.flow_data?.nodes || []).find(n => n.id === state.selectedNodeId);

        let optionsHtml = '';
        if (selectedNode && selectedNode.type === 'buttons' && Array.isArray(selectedNode.options) && selectedNode.options.length > 0) {
            optionsHtml = `<div class="wa-preview-buttons">` +
                selectedNode.options.map(opt => `<button type="button" class="wa-preview-btn">🔘 ${escapeHtml(opt.title || 'Option')}</button>`).join('') +
                `</div>`;
        } else if (selectedNode && selectedNode.type === 'list' && Array.isArray(selectedNode.sections) && selectedNode.sections.length > 0) {
            optionsHtml = `<div class="wa-preview-list-btn"><button type="button" class="wa-preview-btn-menu">📋 View Options</button></div>`;
        }

        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        elements.messageLivePreview.innerHTML = `
            <div class="wa-bubble-card">
                ${headerVal ? `<div class="wa-bubble-header">${escapeHtml(headerVal)}</div>` : ''}
                <div class="wa-bubble-body">${bodyVal ? escapeHtml(bodyVal).replace(/\n/g, '<br>') : '<span style="color:#94a3b8; font-style:italic;">(Enter message text above...)</span>'}</div>
                ${footerVal ? `<div class="wa-bubble-footer">${escapeHtml(footerVal)}</div>` : ''}
                <div class="wa-bubble-meta">
                    <span class="wa-bubble-time">${timeStr}</span>
                    <span class="wa-bubble-ticks">✓✓</span>
                </div>
                ${optionsHtml}
            </div>
        `;
    }

    function showConfirmDialog(title, message, confirmText = 'Confirm', isDanger = true, onConfirm = null) {
        if (!elements.confirmDialogModal) {
            if (window.confirm(`${title}\n\n${message}`)) {
                if (onConfirm) onConfirm();
            }
            return;
        }

        elements.confirmDialogTitle.textContent = title;
        elements.confirmDialogMsg.textContent = message;
        elements.btnDialogConfirm.textContent = confirmText;
        elements.btnDialogConfirm.className = isDanger ? 'btn btn-danger' : 'btn btn-primary';

        function closeDialog() {
            elements.confirmDialogModal.style.display = 'none';
            cleanup();
        }

        function handleConfirm() {
            closeDialog();
            if (onConfirm) onConfirm();
        }

        function cleanup() {
            elements.btnDialogConfirm.removeEventListener('click', handleConfirm);
            elements.btnDialogCancel.removeEventListener('click', closeDialog);
            if (elements.btnCancelDialogX) elements.btnCancelDialogX.removeEventListener('click', closeDialog);
        }

        elements.btnDialogConfirm.addEventListener('click', handleConfirm);
        elements.btnDialogCancel.addEventListener('click', closeDialog);
        if (elements.btnCancelDialogX) elements.btnCancelDialogX.addEventListener('click', closeDialog);

        elements.confirmDialogModal.style.display = 'flex';
    }

    function focusAndSelectNode(nodeId) {
        if (elements.validationModalBackdrop) {
            elements.validationModalBackdrop.style.display = 'none';
        }
        selectNode(nodeId);
        const cardEl = document.getElementById(`node-${nodeId}`);
        if (cardEl) {
            cardEl.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
            cardEl.classList.add('pulse-highlight');
            setTimeout(() => cardEl.classList.remove('pulse-highlight'), 2000);
        }
    }

    function updateMinimap() {
        if (!elements.minimapCanvas || !elements.canvasViewport) return;
        const canvas = elements.minimapCanvas;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const width = canvas.width;
        const height = canvas.height;
        ctx.clearRect(0, 0, width, height);

        const nodes = state.currentFlow?.flow_data?.nodes || [];
        if (nodes.length === 0) return;

        let maxX = 800;
        let maxY = 1200;
        nodes.forEach(n => {
            const nx = n.x || 240;
            const ny = n.y || 40;
            if (nx + 290 > maxX) maxX = nx + 290;
            if (ny + 160 > maxY) maxY = ny + 160;
        });

        const worldW = maxX + 80;
        const worldH = maxY + 80;
        const scaleX = width / worldW;
        const scaleY = height / worldH;
        const miniScale = Math.min(scaleX, scaleY);

        nodes.forEach(n => {
            const nx = (n.x || 240) * miniScale;
            const ny = (n.y || 40) * miniScale;
            const nw = Math.max(12, 290 * miniScale);
            const nh = Math.max(6, 90 * miniScale);

            ctx.fillStyle = n.id === state.selectedNodeId ? '#3b82f6' : (NODE_TYPES[n.type]?.color || '#94a3b8');
            ctx.fillRect(nx, ny, nw, nh);
        });

        if (elements.minimapViewport) {
            const vp = elements.canvasViewport;
            const vpX = (vp.scrollLeft / state.scale) * miniScale;
            const vpY = (vp.scrollTop / state.scale) * miniScale;
            const vpW = (vp.clientWidth / state.scale) * miniScale;
            const vpH = (vp.clientHeight / state.scale) * miniScale;

            elements.minimapViewport.style.left = `${Math.max(0, vpX)}px`;
            elements.minimapViewport.style.top = `${Math.max(0, vpY)}px`;
            elements.minimapViewport.style.width = `${Math.min(width, vpW)}px`;
            elements.minimapViewport.style.height = `${Math.min(height, vpH)}px`;
        }
    }

    function zoomFit() {
        if (!state.currentFlow?.flow_data?.nodes || state.currentFlow.flow_data.nodes.length === 0) return;
        const nodes = state.currentFlow.flow_data.nodes;
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        nodes.forEach(n => {
            const nx = n.x || 240;
            const ny = n.y || 40;
            if (nx < minX) minX = nx;
            if (ny < minY) minY = ny;
            if (nx + 290 > maxX) maxX = nx + 290;
            if (ny + 160 > maxY) maxY = ny + 160;
        });

        const vpWidth = elements.canvasViewport.clientWidth;
        const vpHeight = elements.canvasViewport.clientHeight;
        const graphWidth = maxX - minX + 100;
        const graphHeight = maxY - minY + 100;

        const targetScale = Math.min(1.2, Math.max(0.4, Math.min(vpWidth / graphWidth, vpHeight / graphHeight)));
        setZoom(targetScale);

        elements.canvasViewport.scrollTo({
            left: Math.max(0, minX * targetScale - 30),
            top: Math.max(0, minY * targetScale - 30),
            behavior: 'smooth'
        });
    }

    /* ==========================================================================
       Event Listeners Binding
       ========================================================================== */

    
    async function handleCreateNewFlowInEditor() {
        const name = (elements.newFlowNameInput?.value || '').trim() || 'New Automation Flow';
        const trigger = elements.newFlowTriggerSelect?.value || 'first_incoming_message';
        const keywords = (elements.newFlowKeywordsInput?.value || '').trim() || 'hi, hello, course';
        const templateChoice = elements.newFlowTemplateSelect?.value || 'blank';

        let initialFlowData;
        if (templateChoice === 'admissions') {
            useDefaultTemplate();
            initialFlowData = state.currentFlow?.flow_data;
        } else {
            initialFlowData = {
                nodes: [
                    { id: "trigger_1", type: "trigger", title: trigger === 'keyword' ? "Keyword Trigger" : "Trigger", x: 150, y: 150, trigger_type: trigger, data: { trigger_type: trigger, keywords: keywords }, next_node_id: "msg_1" },
                    { id: "msg_1", type: "message", title: "Welcome Message", body: "Hello! Welcome to TECHPANDA WhatsApp.", x: 420, y: 150, data: { text: "Hello! Welcome to TECHPANDA WhatsApp." }, next_node_id: "end_1" },
                    { id: "end_1", type: "end", title: "End Session", body: "Thank you for connecting with us!", x: 700, y: 150, data: { text: "Thank you for connecting with us!" } }
                ],
                connections: [
                    { id: "conn_trig_msg", source: "trigger_1", source_output: "default", target: "msg_1", target_input: "input" },
                    { id: "conn_msg_end", source: "msg_1", source_output: "default", target: "end_1", target_input: "input" }
                ]
            };
        }

        try {
            const resp = await fetch('/api/flows/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    slug: name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
                    version: 1,
                    trigger_type: trigger,
                    trigger_keywords: keywords,
                    business_account: state.selectedBusinessAccountId,
                    flow_data: initialFlowData
                })
            });
            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.error || errData.name?.[0] || 'Failed to create new flow');
            }
            const createdFlow = await resp.json();
            state.currentFlow = createdFlow;
            if (elements.newFlowModal) elements.newFlowModal.style.display = 'none';
            history.pushState(null, '', `/chat/automation/${createdFlow.id}/`);
            renderFlowMetadata();
            renderCanvas();
            recordHistory();
            setSaveStatus('saved');
            showToast(`✨ Created flow "${name}"!`);
        } catch (err) {
            console.error('Error creating new flow:', err);
            showToast(err.message || 'Error creating flow', true);
        }
    }

    function bindEvents() {
        // Business Account selection change
        elements.flowBusinessAccountSelect.addEventListener('change', async (e) => {
            state.selectedBusinessAccountId = e.target.value ? parseInt(e.target.value, 10) : null;
            updateBranchSelectForActiveAccount();
            await loadFlowForCurrentAccount();
        });

        // Branch Selection Change for active WhatsApp Line
        if (elements.flowBranchSelect) {
            elements.flowBranchSelect.addEventListener('change', async (e) => {
                const branchId = e.target.value ? parseInt(e.target.value, 10) : null;
                if (!state.selectedBusinessAccountId) {
                    showToast('Please select a WhatsApp line first', true);
                    return;
                }
                try {
                    const resp = await fetch(`/api/business-accounts/${state.selectedBusinessAccountId}/`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ crm_branch_id: branchId })
                    });
                    if (resp.ok) {
                        const updatedAcc = await resp.json();
                        const accIdx = state.businessAccounts.findIndex(a => a.id === state.selectedBusinessAccountId);
                        if (accIdx !== -1) {
                            state.businessAccounts[accIdx] = updatedAcc;
                        }
                        if (elements.branchSavedIndicator) {
                            elements.branchSavedIndicator.classList.add('visible');
                            setTimeout(() => elements.branchSavedIndicator.classList.remove('visible'), 2000);
                        }
                        showToast(`WhatsApp Line mapped to "${updatedAcc.crm_branch_name || 'Unassigned Branch'}".`);
                    } else {
                        showToast('Failed to update branch for WhatsApp line', true);
                    }
                } catch (err) {
                    console.error('Error updating branch:', err);
                    showToast('Network error updating branch', true);
                }
            });
        }

        // Flow Name input
        if (elements.flowNameInput) {
            elements.flowNameInput.addEventListener('input', (e) => {
                if (state.currentFlow) {
                    state.currentFlow.name = e.target.value.trim() || 'Untitled Flow';
                }
                setSaveStatus('unsaved');
            });
        }

        // Trigger Mode change
        elements.triggerTypeSelect.addEventListener('change', (e) => {
            elements.triggerKeywordsBox.style.display = e.target.value === 'keyword' ? 'block' : 'none';
            setSaveStatus('unsaved');
        });

        // Save, Publish, Validate, & Version History
        elements.btnSaveDraft.addEventListener('click', saveDraft);
        elements.btnPublishFlow.addEventListener('click', publishFlow);
        if (elements.btnValidateFlow) {
            elements.btnValidateFlow.addEventListener('click', validateFlowAction);
        }
        if (elements.btnNewFlow) {
            elements.btnNewFlow.addEventListener('click', () => {
                if (elements.newFlowModal) {
                    if (elements.newFlowNameInput) elements.newFlowNameInput.value = '';
                    if (elements.newFlowKeywordsInput) elements.newFlowKeywordsInput.value = '';
                    if (elements.newFlowKeywordsWrap) elements.newFlowKeywordsWrap.style.display = 'none';
                    if (elements.newFlowTriggerSelect) elements.newFlowTriggerSelect.value = 'first_incoming_message';
                    elements.newFlowModal.style.display = 'flex';
                    if (elements.newFlowNameInput) elements.newFlowNameInput.focus();
                }
            });
        }
        if (elements.btnCloseNewFlowModal) {
            elements.btnCloseNewFlowModal.addEventListener('click', () => {
                if (elements.newFlowModal) elements.newFlowModal.style.display = 'none';
            });
        }
        if (elements.btnCancelNewFlowModal) {
            elements.btnCancelNewFlowModal.addEventListener('click', () => {
                if (elements.newFlowModal) elements.newFlowModal.style.display = 'none';
            });
        }
        if (elements.newFlowTriggerSelect) {
            elements.newFlowTriggerSelect.addEventListener('change', (e) => {
                if (elements.newFlowKeywordsWrap) {
                    elements.newFlowKeywordsWrap.style.display = e.target.value === 'keyword' ? 'block' : 'none';
                }
            });
        }
        if (elements.btnConfirmCreateNewFlow) {
            elements.btnConfirmCreateNewFlow.addEventListener('click', handleCreateNewFlowInEditor);
        }
        if (elements.newFlowModal) {
            elements.newFlowModal.addEventListener('click', (e) => {
                if (e.target === elements.newFlowModal) {
                    elements.newFlowModal.style.display = 'none';
                }
            });
        }

        if (elements.btnVersionHistory) {
            elements.btnVersionHistory.addEventListener('click', openVersionHistory);
        }
        if (elements.btnCloseVersionHistory) {
            elements.btnCloseVersionHistory.addEventListener('click', () => {
                if (elements.versionHistoryModal) elements.versionHistoryModal.style.display = 'none';
            });
        }
        if (elements.versionHistoryModal) {
            elements.versionHistoryModal.addEventListener('click', (e) => {
                if (e.target === elements.versionHistoryModal) {
                    elements.versionHistoryModal.style.display = 'none';
                }
            });
        }

        // Reset Template
        elements.btnResetTemplate.addEventListener('click', () => {
            showConfirmDialog(
                'Reset to Default Template',
                'Reset canvas back to the default Admissions & Training template? Any unsaved edits will be lost.',
                'Reset Canvas',
                true,
                () => {
                    useDefaultTemplate();
                    recordHistory();
                    showToast('Reset to default Admissions & Training template.');
                }
            );
        });

        // Canvas Zoom & Layout
        elements.btnZoomIn.addEventListener('click', () => setZoom(state.scale + 0.1));
        elements.btnZoomOut.addEventListener('click', () => setZoom(state.scale - 0.1));
        if (elements.btnZoomFit) elements.btnZoomFit.addEventListener('click', zoomFit);
        elements.btnResetView.addEventListener('click', () => {
            setZoom(1.0);
            elements.canvasViewport.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
        });
        elements.btnAutoLayout.addEventListener('click', autoLayoutGraph);

        // Undo / Redo
        if (elements.btnUndo) elements.btnUndo.addEventListener('click', undo);
        if (elements.btnBottomUndo) elements.btnBottomUndo.addEventListener('click', undo);
        if (elements.btnRedo) elements.btnRedo.addEventListener('click', redo);
        if (elements.btnBottomRedo) elements.btnBottomRedo.addEventListener('click', redo);

        // Palette Search Filter
        if (elements.paletteSearchInput) {
            elements.paletteSearchInput.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase().trim();
                const container = elements.paletteNodesList || document.getElementById('paletteNodesList') || document.querySelector('.palette-scroll-container');
                if (!container) return;
                const categories = container.querySelectorAll('.palette-category, .palette-category-group');
                categories.forEach(cat => {
                    let catHasMatches = false;
                    const items = cat.querySelectorAll('.palette-node-item');
                    items.forEach(item => {
                        const title = (item.querySelector('.palette-label, .palette-item-title')?.textContent || '').toLowerCase();
                        const desc = (item.querySelector('.palette-desc, .palette-item-desc')?.textContent || '').toLowerCase();
                        const type = (item.getAttribute('data-type') || '').toLowerCase();
                        const matches = !query || title.includes(query) || desc.includes(query) || type.includes(query);
                        item.style.display = matches ? 'flex' : 'none';
                        if (matches) catHasMatches = true;
                    });
                    cat.style.display = catHasMatches ? 'block' : 'none';
                });
            });
        }

        // Palette Add buttons & HTML5 Drag Support
        const paletteContainer = elements.paletteNodesList || document.getElementById('paletteNodesList') || document.querySelector('.palette-scroll-container');
        if (paletteContainer) {
            paletteContainer.querySelectorAll('.palette-node-item').forEach(item => {
                const type = item.getAttribute('data-type');
                const triggerType = item.getAttribute('data-trigger-type') || null;
                const addBtn = item.querySelector('.btn-add-node');
                if (addBtn) {
                    addBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        addNewNode(type, null, triggerType ? { trigger_type: triggerType } : null);
                    });
                }
                item.addEventListener('click', (e) => {
                    if (e.target.closest('.btn-add-node')) return;
                    addNewNode(type, null, triggerType ? { trigger_type: triggerType } : null);
                });

                // HTML5 Drag Support
                item.setAttribute('draggable', 'true');
                item.addEventListener('dragstart', (e) => {
                    e.dataTransfer.setData('application/json', JSON.stringify({
                        type: type,
                        triggerType: triggerType
                    }));
                    e.dataTransfer.effectAllowed = 'copy';
                });
            });
        }

        // Canvas drop target for dragging nodes from palette
        if (elements.canvasViewport) {
            elements.canvasViewport.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'copy';
            });

            elements.canvasViewport.addEventListener('drop', (e) => {
                e.preventDefault();
                try {
                    const rawData = e.dataTransfer.getData('application/json');
                    if (!rawData) return;
                    const dragData = JSON.parse(rawData);
                    if (!dragData.type) return;

                    const viewportRect = elements.canvasViewport.getBoundingClientRect();
                    const dropX = Math.round((e.clientX - viewportRect.left + elements.canvasViewport.scrollLeft) / state.scale);
                    const dropY = Math.round((e.clientY - viewportRect.top + elements.canvasViewport.scrollTop) / state.scale);

                    addNewNode(
                        dragData.type,
                        { x: Math.max(20, dropX - 100), y: Math.max(20, dropY - 40) },
                        dragData.triggerType ? { trigger_type: dragData.triggerType } : null
                    );
                } catch (err) {
                    console.error('Canvas drop error:', err);
                }
            });
        }

        // Inspector Form Submit & Debounced Live Auto-Sync
        elements.inspectorForm.addEventListener('submit', (e) => {
            e.preventDefault();
            applyInspectorChanges(true);
        });

        let inspectorSyncTimer = null;
        elements.inspectorForm.addEventListener('input', () => {
            clearTimeout(inspectorSyncTimer);
            inspectorSyncTimer = setTimeout(() => {
                applyInspectorChanges(false);
            }, 250);
        });
        elements.inspectorForm.addEventListener('change', () => {
            clearTimeout(inspectorSyncTimer);
            inspectorSyncTimer = setTimeout(() => {
                applyInspectorChanges(false);
            }, 100);
        });

        elements.btnCloseInspector.addEventListener('click', () => {
            selectNode(null);
        });
        elements.btnDeleteNode.addEventListener('click', deleteSelectedNode);

        // Live Preview on Body Input
        if (elements.editNodeBody) {
            elements.editNodeBody.addEventListener('input', () => {
                updateLivePreview();
                setSaveStatus('unsaved');
            });
        }

        // Variable Picker Modal
        if (elements.btnOpenVariablePicker) {
            elements.btnOpenVariablePicker.addEventListener('click', () => {
                if (elements.varPickerBackdrop) elements.varPickerBackdrop.style.display = 'flex';
            });
        }
        if (elements.btnCloseVarPicker) {
            elements.btnCloseVarPicker.addEventListener('click', () => {
                if (elements.varPickerBackdrop) elements.varPickerBackdrop.style.display = 'none';
            });
        }
        if (elements.varPickerBackdrop) {
            elements.varPickerBackdrop.addEventListener('click', (e) => {
                if (e.target === elements.varPickerBackdrop) {
                    elements.varPickerBackdrop.style.display = 'none';
                }
            });
            elements.varPickerBackdrop.querySelectorAll('.var-tag-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const tag = btn.getAttribute('data-var');
                    if (tag && elements.editNodeBody) {
                        insertAtCursor(elements.editNodeBody, tag);
                        updateLivePreview();
                        setSaveStatus('unsaved');
                    }
                    elements.varPickerBackdrop.style.display = 'none';
                });
            });
        }

        // Inspector Variable Chips
        document.querySelectorAll('.var-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const varText = chip.getAttribute('data-var');
                insertAtCursor(elements.editNodeBody, varText);
                updateLivePreview();
                setSaveStatus('unsaved');
            });
        });

        // Add Button in Inspector
        elements.btnAddOptionBtn.addEventListener('click', () => {
            const node = (state.currentFlow?.flow_data?.nodes || []).find(n => n.id === state.selectedNodeId);
            if (node) {
                if (!node.options) node.options = [];
                if (node.options.length < 3) {
                    node.options.push({
                        id: `opt_${node.options.length + 1}`,
                        title: `Option ${node.options.length + 1}`,
                        next_node_id: null
                    });
                    renderButtonsOptionsEditor(node.options);
                    recordHistory();
                }
            }
        });

        // Add Program row in Inspector
        elements.btnAddListRowBtn.addEventListener('click', () => {
            const node = (state.currentFlow?.flow_data?.nodes || []).find(n => n.id === state.selectedNodeId);
            if (node) {
                if (!node.sections) node.sections = [{ title: 'Programs', rows: [] }];
                const rows = node.sections[0].rows || [];
                rows.push({
                    id: `row_${rows.length + 1}`,
                    title: `New Program`,
                    description: `Program details`
                });
                renderListRowsEditor(node.sections);
                recordHistory();
            }
        });

        // Canvas Viewport Deselect & Scroll for minimap
        elements.canvasViewport.addEventListener('click', (e) => {
            if (e.target === elements.canvasViewport || e.target === elements.canvasPlane || e.target === elements.canvasSvgLayer) {
                selectNode(null);
                selectEdge(null);
            }
        });
        elements.canvasViewport.addEventListener('scroll', updateMinimap);

        // AI Flow Assistant Modal
        if (elements.btnOpenAIAssistant) {
            elements.btnOpenAIAssistant.addEventListener('click', () => {
                if (elements.aiAssistantModal) {
                    elements.aiAssistantModal.style.display = 'flex';
                    if (elements.aiFlowNameInput && !elements.aiFlowNameInput.value) {
                        elements.aiFlowNameInput.value = 'AI Generated Flow';
                    }
                    if (elements.aiPromptInput) {
                        elements.aiPromptInput.focus();
                    }
                }
            });
        }
        if (elements.btnCloseAIAssistant) {
            elements.btnCloseAIAssistant.addEventListener('click', () => {
                if (elements.aiAssistantModal) elements.aiAssistantModal.style.display = 'none';
            });
        }
        if (elements.btnCancelAIAssistant) {
            elements.btnCancelAIAssistant.addEventListener('click', () => {
                if (elements.aiAssistantModal) elements.aiAssistantModal.style.display = 'none';
            });
        }
        if (elements.btnGenerateFromPrompt) {
            elements.btnGenerateFromPrompt.addEventListener('click', async () => {
                const prompt = elements.aiPromptInput ? elements.aiPromptInput.value.trim() : '';
                const name = elements.aiFlowNameInput ? elements.aiFlowNameInput.value.trim() : 'AI Workflow';
                if (!prompt) {
                    showToast('Please enter a description for the AI assistant.', true);
                    return;
                }
                const originalHtml = elements.btnGenerateFromPrompt.innerHTML;
                elements.btnGenerateFromPrompt.disabled = true;
                elements.btnGenerateFromPrompt.innerHTML = '<span>⚡ Synthesizing Workflow...</span>';

                try {
                    const resp = await fetch('/api/flows/generate-from-prompt/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            prompt: prompt,
                            name: name,
                            business_account_id: state.selectedBusinessAccountId
                        })
                    });
                    if (!resp.ok) {
                        const errData = await resp.json().catch(() => ({}));
                        throw new Error(errData.error || 'Failed to generate flow');
                    }
                    const data = await resp.json();
                    if (data.flow) {
                        state.currentFlow = data.flow;
                        renderFlowMetadata();
                        renderCanvas();
                        recordHistory();
                        setSaveStatus('unsaved');
                        if (elements.aiAssistantModal) elements.aiAssistantModal.style.display = 'none';
                        showToast(`✨ Generated "${name}" with ${data.flow.flow_data?.nodes?.length || 0} nodes!`);
                    }
                } catch (err) {
                    console.error('AI Flow Generator error:', err);
                    showToast(err.message || 'Error generating workflow.', true);
                } finally {
                    elements.btnGenerateFromPrompt.disabled = false;
                    elements.btnGenerateFromPrompt.innerHTML = originalHtml;
                }
            });
        }

        // Simulator Drawer Controls
        elements.btnOpenSimulator.addEventListener('click', openSimulator);
        elements.btnCloseSimulator.addEventListener('click', closeSimulator);
        elements.simulatorBackdrop.addEventListener('click', closeSimulator);
        elements.btnRestartSimulation.addEventListener('click', restartSimulation);
        elements.btnCloseSimSheet.addEventListener('click', () => elements.simListSheet.classList.remove('open'));

        // Simulator Telemetry Drawer Collapse/Expand
        if (elements.simDebugHeader) {
            elements.simDebugHeader.addEventListener('click', () => {
                const isOpen = elements.simDebugContent.style.display !== 'none';
                elements.simDebugContent.style.display = isOpen ? 'none' : 'block';
                if (elements.simDebugToggleIcon) {
                    elements.simDebugToggleIcon.textContent = isOpen ? '▶' : '▼';
                }
            });
        }

        // Create New Draft Version
        if (elements.btnCreateDraft) {
            elements.btnCreateDraft.addEventListener('click', createNewDraft);
        }

        // Dynamic Source dropdown toggles
        if (elements.editListSource) {
            elements.editListSource.addEventListener('change', (e) => {
                elements.customListRowsContainer.style.display = e.target.value === 'database' ? 'none' : 'block';
            });
        }
        if (elements.editMediaSource) {
            elements.editMediaSource.addEventListener('change', (e) => {
                elements.customMediaFields.style.display = e.target.value === 'selected_course_brochure' ? 'none' : 'block';
            });
        }
        if (elements.editLocationSource) {
            elements.editLocationSource.addEventListener('change', (e) => {
                elements.customLocationFields.style.display = e.target.value === 'dynamic_branch' ? 'none' : 'block';
            });
        }
        if (elements.editLeadStatus) {
            elements.editLeadStatus.addEventListener('change', (e) => {
                elements.groupFollowUpHours.style.display = e.target.value === CRM_FOLLOW_UP ? 'block' : 'none';
            });
        }
        if (elements.editAssignMode) {
            elements.editAssignMode.addEventListener('change', (e) => {
                elements.groupAssignTelecaller.style.display = e.target.value === 'specific' ? 'block' : 'none';
            });
        }

        // Validation Modal Dismissal
        if (elements.btnCloseValidationModal) {
            elements.btnCloseValidationModal.addEventListener('click', () => {
                elements.validationModalBackdrop.style.display = 'none';
            });
        }
        if (elements.btnAcknowledgeValidation) {
            elements.btnAcknowledgeValidation.addEventListener('click', () => {
                elements.validationModalBackdrop.style.display = 'none';
            });
        }

        elements.simChatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const text = elements.simChatInput.value;
            elements.simChatInput.value = '';
            handleSimUserInput(text);
        });

        // Global Keyboard Shortcuts
        document.addEventListener('keydown', (e) => {
            const isEditing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);

            // Delete Selected Node or Edge
            if ((e.key === 'Delete' || e.key === 'Backspace') && !isEditing) {
                if (state.selectedEdgeId) {
                    e.preventDefault();
                    deleteEdge(state.selectedEdgeId);
                } else if (state.selectedNodeId && state.selectedNodeId !== 'START' && state.selectedNodeId !== 'trigger_1') {
                    e.preventDefault();
                    deleteSelectedNode();
                }
            }

            // Undo: Ctrl+Z / Cmd+Z
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
                e.preventDefault();
                undo();
            }

            // Redo: Ctrl+Y or Ctrl+Shift+Z
            if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) {
                e.preventDefault();
                redo();
            }

            // Save Draft: Ctrl+S / Cmd+S
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
                e.preventDefault();
                saveDraft();
            }

            // Escape
            if (e.key === 'Escape') {
                if (elements.varPickerBackdrop && elements.varPickerBackdrop.style.display === 'flex') {
                    elements.varPickerBackdrop.style.display = 'none';
                } else if (elements.confirmDialogModal && elements.confirmDialogModal.style.display === 'flex') {
                    elements.confirmDialogModal.style.display = 'none';
                } else if (elements.validationModalBackdrop && elements.validationModalBackdrop.style.display === 'flex') {
                    elements.validationModalBackdrop.style.display = 'none';
                } else if (elements.newFlowModal && elements.newFlowModal.style.display === 'flex') {
                    elements.newFlowModal.style.display = 'none';
                } else if (elements.versionHistoryModal && elements.versionHistoryModal.style.display === 'flex') {
                    elements.versionHistoryModal.style.display = 'none';
                } else if (elements.aiAssistantModal && elements.aiAssistantModal.style.display === 'flex') {
                    elements.aiAssistantModal.style.display = 'none';
                } else if (state.simState.isOpen) {
                    closeSimulator();
                } else if (state.selectedEdgeId) {
                    selectEdge(null);
                } else if (state.selectedNodeId) {
                    selectNode(null);
                }
            }
        });

        // Prompt user before closing tab if there are unsaved workflow changes
        window.addEventListener('beforeunload', (e) => {
            if (state.saveStatus === 'unsaved') {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes in your WhatsApp workflow.';
                return e.returnValue;
            }
        });
    }

    /* ==========================================================================
       Utilities
       ========================================================================== */

    function showToast(msg, isError = false) {
        if (!elements.builderToast) return;
        if (elements.builderToastMsg) elements.builderToastMsg.textContent = msg;
        const icon = elements.builderToast.querySelector('.toast-icon');
        if (icon) {
            icon.textContent = isError ? '!' : '✓';
            icon.style.background = isError ? '#ef4444' : '#10b981';
        }
        elements.builderToast.classList.add('show');
        setTimeout(() => elements.builderToast.classList.remove('show'), 3000);
    }

    function insertAtCursor(input, text) {
        const start = input.selectionStart;
        const end = input.selectionEnd;
        const value = input.value;
        input.value = value.substring(0, start) + text + value.substring(end);
        input.selectionStart = input.selectionEnd = start + text.length;
        input.focus();
    }

    function formatWhatsAppMarkdown(text) {
        if (!text) return '';
        let escaped = escapeHtml(text);
        escaped = escaped.replace(/\*(.*?)\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/_(.*?)_/g, '<em>$1</em>');
        escaped = escaped.replace(/\n/g, '<br>');
        return escaped;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // Initialize application when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
