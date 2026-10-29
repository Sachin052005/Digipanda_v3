import { FlowNodeType } from './types';

export interface PaletteNodeDef {
  type: FlowNodeType;
  label: string;
  category: 'Triggers' | 'Messages' | 'Logic' | 'CRM' | 'Integrations';
  description: string;
  iconName: string;
  accentColor: string;
  defaultData: Record<string, any>;
}

export const PALETTE_NODES: PaletteNodeDef[] = [
  // TRIGGERS
  {
    type: 'trigger',
    label: 'Trigger / Start',
    category: 'Triggers',
    description: 'Entry point for customer WhatsApp inquiries',
    iconName: 'Zap',
    accentColor: '#10b981', // emerald
    defaultData: {
      title: 'WhatsApp Message Trigger',
      trigger_type: 'always_on',
      trigger_keywords: 'hi, hello, menu, start, admission',
    },
  },

  // MESSAGES
  {
    type: 'message',
    label: 'Text Message',
    category: 'Messages',
    description: 'Send plain or formatted WhatsApp text with variables',
    iconName: 'MessageSquare',
    accentColor: '#0ea5e9', // sky
    defaultData: {
      title: 'Send Text Message',
      body: 'Hello {{customer_name}}! Welcome to DigiPanda Training Academy.',
    },
  },
  {
    type: 'buttons',
    label: 'Interactive Buttons',
    category: 'Messages',
    description: 'Send quick-reply buttons (up to 3 options)',
    iconName: 'LayoutGrid',
    accentColor: '#6366f1', // indigo
    defaultData: {
      title: 'Choose Program Options',
      header: 'DigiPanda Admissions',
      body: 'Which domain would you like to explore today?',
      footer: 'Tap an option below',
      options: [
        { id: 'opt_courses', title: '🎓 Explore Courses' },
        { id: 'opt_fees', title: '💰 Fee Structure' },
        { id: 'opt_talk', title: '👤 Speak with Counselor' },
      ],
    },
  },
  {
    type: 'list',
    label: 'Interactive List Menu',
    category: 'Messages',
    description: 'Rich selection menu with multiple sections & items',
    iconName: 'ListOrdered',
    accentColor: '#8b5cf6', // purple
    defaultData: {
      title: 'Course Catalog Menu',
      header: 'Featured Programs',
      body: 'Select a program from the menu to receive the syllabus & fee details:',
      button_text: 'View Programs',
      source: 'database',
      sections: [
        {
          title: 'Full Stack Development',
          rows: [
            { id: 'fs_python', title: 'Python Full Stack', description: 'Django, React & PostgreSQL' },
            { id: 'fs_mern', title: 'MERN Stack Web Dev', description: 'MongoDB, Express, React, Node' },
          ],
        },
      ],
    },
  },
  {
    type: 'media',
    label: 'Media / Brochure',
    category: 'Messages',
    description: 'Send course brochure PDF, images, or documents',
    iconName: 'FileText',
    accentColor: '#ec4899', // pink
    defaultData: {
      title: 'Send Course Brochure',
      source: 'selected_course_brochure',
      caption: 'Here is the detailed syllabus and curriculum guide.',
      filename: 'Course_Curriculum.pdf',
    },
  },
  {
    type: 'location',
    label: 'Location / Branch GPS',
    category: 'Messages',
    description: 'Send interactive map pin and address to user',
    iconName: 'MapPin',
    accentColor: '#f43f5e', // rose
    defaultData: {
      title: 'Branch Location',
      source: 'dynamic_branch',
      name: 'DigiPanda Tech Academy',
      address: 'Anna Salai, Chennai, Tamil Nadu',
      latitude: 13.0827,
      longitude: 80.2707,
    },
  },

  // LOGIC & FLOW
  {
    type: 'condition',
    label: 'Condition / If–Else',
    category: 'Logic',
    description: 'Branch the workflow based on variables or student replies',
    iconName: 'GitFork',
    accentColor: '#f59e0b', // amber
    defaultData: {
      title: 'Check Lead Interest',
      variable: 'interested_domain',
      operator: 'contains',
      value: 'fullstack',
    },
  },
  {
    type: 'delay',
    label: 'Wait / Delay',
    category: 'Logic',
    description: 'Durable timer pause (e.g. follow-up after 10 mins)',
    iconName: 'Clock',
    accentColor: '#eab308', // yellow
    defaultData: {
      title: 'Follow-Up Wait Delay',
      amount: 15,
      unit: 'minutes',
      delay_seconds: 900,
    },
  },
  {
    type: 'question',
    label: 'Capture Answer',
    category: 'Logic',
    description: 'Ask a question and store the customer answer in a variable',
    iconName: 'HelpCircle',
    accentColor: '#14b8a6', // teal
    defaultData: {
      title: 'Capture Highest Degree',
      body: 'What is your highest educational qualification (e.g. B.Tech, BCA, Degree)?',
      variable_name: 'qualification',
      expected_type: 'text',
    },
  },
  {
    type: 'subflow',
    label: 'Go To / Subflow',
    category: 'Logic',
    description: 'Jump to another step or invoke a reusable subflow',
    iconName: 'CornerDownRight',
    accentColor: '#06b6d4', // cyan
    defaultData: {
      title: 'Call Subflow',
      flow_id: null,
      target_node_id: '',
    },
  },
  {
    type: 'end',
    label: 'End Flow',
    category: 'Logic',
    description: 'Complete session and return control',
    iconName: 'CheckCircle2',
    accentColor: '#64748b', // slate
    defaultData: {
      title: 'Complete Workflow',
      body: 'Thank you for reaching out to DigiPanda! Have a wonderful day.',
    },
  },

  // CRM ACTIONS
  {
    type: 'save_data',
    label: 'Update CRM Lead',
    category: 'CRM',
    description: 'Update lead status, follow-up schedule, or custom fields',
    iconName: 'UserCheck',
    accentColor: '#3b82f6', // blue
    defaultData: {
      title: 'Update Lead Pipeline',
      status: 'Qualified Interested',
      follow_up_hours: 4,
    },
  },
  {
    type: 'assign_telecaller',
    label: 'Assign Counselor',
    category: 'CRM',
    description: 'Assign lead to branch counselor via round-robin or auto',
    iconName: 'UserPlus',
    accentColor: '#2563eb', // blue-600
    defaultData: {
      title: 'Assign Counselor',
      mode: 'round_robin',
      only_if_unassigned: true,
    },
  },
  {
    type: 'human_handover',
    label: 'Human Handover',
    category: 'CRM',
    description: 'Silence the bot and alert admissions team to take over',
    iconName: 'Headphones',
    accentColor: '#d97706', // amber-600
    defaultData: {
      title: 'Transfer to Counselor',
      body: '👤 Connecting you with an admissions counselor right now. Please hold on a moment.',
    },
  },

  // INTEGRATIONS
  {
    type: 'webhook',
    label: 'Outbound Webhook / API',
    category: 'Integrations',
    description: 'Make secure outbound HTTP API requests to external webhooks',
    iconName: 'Globe',
    accentColor: '#10b981', // emerald
    defaultData: {
      title: 'External CRM Sync',
      url: 'https://api.example.com/leads/v1/sync',
      method: 'POST',
      headers: '{"Content-Type": "application/json"}',
      payload: '{\n  "name": "{{customer_name}}",\n  "phone": "{{customer_phone}}"\n}',
      save_response_to: 'webhook_result',
    },
  },
];
