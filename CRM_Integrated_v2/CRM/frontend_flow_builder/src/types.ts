export type FlowNodeType =
  | 'trigger'
  | 'message'
  | 'welcome'
  | 'buttons'
  | 'list'
  | 'condition'
  | 'delay'
  | 'question'
  | 'capture_answer'
  | 'save_data'
  | 'update_lead'
  | 'lead_status'
  | 'assign_telecaller'
  | 'media'
  | 'location'
  | 'webhook'
  | 'api_request'
  | 'human_handover'
  | 'subflow'
  | 'goto'
  | 'end';

export interface NodeOption {
  id: string;
  title: string;
  next_node_id?: string;
}

export interface ListRow {
  id: string;
  title: string;
  description?: string;
}

export interface ListSection {
  title: string;
  rows: ListRow[];
}

export interface FlowNodeData {
  label?: string;
  title?: string;
  type: FlowNodeType;
  text?: string;
  body?: string;
  header?: string;
  footer?: string;

  // Buttons
  options?: NodeOption[];

  // List
  button_text?: string;
  sections?: ListSection[];
  source?: 'static' | 'database';

  // Condition
  variable?: string;
  operator?: 'equals' | 'not_equals' | 'contains' | 'not_contains' | 'exists' | 'not_exists';
  value?: string;

  // Delay
  delay_seconds?: number;
  amount?: number;
  unit?: 'seconds' | 'minutes' | 'hours' | 'days';

  // Question / Capture Answer
  variable_name?: string;
  expected_type?: 'text' | 'number' | 'email' | 'phone';

  // Save Data / Lead Status / Assign
  status?: string;
  follow_up_hours?: number;
  mode?: 'auto' | 'round_robin' | 'manual';
  telecaller_id?: number | string;
  only_if_unassigned?: boolean;

  // Media
  media_url?: string;
  caption?: string;
  filename?: string;
  fallback_url?: string;

  // Location
  name?: string;
  address?: string;
  latitude?: number;
  longitude?: number;

  // Webhook
  url?: string;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  headers?: Record<string, string> | string;
  payload?: any;
  save_response_to?: string;

  // Subflow / Goto
  flow_id?: number;
  target_node_id?: string;

  // Generic metadata
  isInitial?: boolean;
  [key: string]: any;
}

export interface FlowVersion {
  id: number;
  version_number: number;
  status: 'draft' | 'published' | 'archived';
  change_summary?: string;
  created_by_name?: string;
  created_at: string;
  published_at?: string;
}

export interface FlowDefinition {
  id: number;
  name: string;
  slug: string;
  version: number;
  status: 'draft' | 'published';
  business_account?: number | null;
  trigger_type: string;
  trigger_keywords?: string;
  flow_data: {
    nodes: any[];
    edges?: any[];
    connections?: any[];
    viewport?: { x: number; y: number; zoom: number };
  };
  is_active: boolean;
  published_at?: string;
  updated_at?: string;
  versions?: FlowVersion[];
}

export interface BusinessLineOption {
  id: number;
  name: string;
  phone_number: string;
  branch_id?: number | null;
}

export interface BranchOption {
  id: number;
  name: string;
  code?: string;
}

export interface SimulatorMessage {
  type: string;
  sender?: 'bot' | 'user';
  body?: string;
  header?: string;
  footer?: string;
  options?: NodeOption[];
  sections?: ListSection[];
  button_text?: string;
  caption?: string;
  filename?: string;
  name?: string;
  address?: string;
  node_id?: string;
}

export interface SimulatorState {
  isOpen: boolean;
  currentNodeId: string | null;
  collectedData: Record<string, any>;
  messages: SimulatorMessage[];
  crmActions: string[];
  waitingForInput: boolean;
  isComplete: boolean;
  isLoading: boolean;
}
