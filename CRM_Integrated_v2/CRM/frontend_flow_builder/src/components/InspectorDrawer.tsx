import React, { useState, useRef } from 'react';
import * as LucideIcons from 'lucide-react';
import { Node } from '@xyflow/react';
import { FlowNodeData, NodeOption } from '../types';
import { PALETTE_NODES } from '../constants';

interface InspectorDrawerProps {
  node: Node<FlowNodeData> | null;
  onUpdateNodeData: (nodeId: string, newData: Partial<FlowNodeData>) => void;
  onDeleteNode: (nodeId: string) => void;
  onClose: () => void;
}

const COMMON_VARIABLES = [
  'customer_name',
  'customer_phone',
  'qualification',
  'course_name',
  'course_id',
  'city',
  'email',
];

export const InspectorDrawer: React.FC<InspectorDrawerProps> = ({
  node,
  onUpdateNodeData,
  onDeleteNode,
  onClose,
}) => {
  if (!node) return null;

  const data = node.data || {};
  const def = PALETTE_NODES.find((p) => p.type === data.type) || PALETTE_NODES[1];
  const accentColor = def.accentColor || '#3b82f6';

  const handleChange = (field: keyof FlowNodeData, value: any) => {
    onUpdateNodeData(node.id, { [field]: value });
  };

  const insertVariable = (varName: string, field: 'body' | 'text' = 'body') => {
    const currentVal = data[field] || '';
    const insertion = `{{${varName}}}`;
    handleChange(field, `${currentVal} ${insertion}`);
  };

  // Button option handlers
  const handleAddButton = () => {
    const opts = [...(data.options || [])];
    if (opts.length >= 3) return;
    const newIdx = opts.length + 1;
    opts.push({ id: `btn_${Date.now()}`, title: `Option ${newIdx}` });
    handleChange('options', opts);
  };

  const handleUpdateButton = (index: number, title: string) => {
    const opts = [...(data.options || [])];
    opts[index] = { ...opts[index], title };
    handleChange('options', opts);
  };

  const handleRemoveButton = (index: number) => {
    const opts = [...(data.options || [])];
    opts.splice(index, 1);
    handleChange('options', opts);
  };

  // List row / custom answer handlers
  const listSections = Array.isArray(data.sections) && data.sections.length > 0 
    ? data.sections 
    : [{ title: 'Options', rows: [] }];
  const currentListRows: any[] = listSections[0]?.rows || [];

  const handleAddListRow = () => {
    const sections = Array.isArray(data.sections) && data.sections.length > 0 
      ? JSON.parse(JSON.stringify(data.sections)) 
      : [{ title: 'Options', rows: [] }];
    if (!sections[0].rows) sections[0].rows = [];
    if (sections[0].rows.length >= 10) return; // WhatsApp max 10 rows
    const idx = sections[0].rows.length + 1;
    sections[0].rows.push({
      id: `row_${Date.now()}_${idx}`,
      title: `Option ${idx}`,
      description: ''
    });
    handleChange('sections', sections);
  };

  const handleUpdateListRow = (rowIdx: number, field: string, value: string) => {
    const sections = Array.isArray(data.sections) && data.sections.length > 0 
      ? JSON.parse(JSON.stringify(data.sections)) 
      : [{ title: 'Options', rows: [] }];
    if (!sections[0].rows) sections[0].rows = [];
    if (sections[0].rows[rowIdx]) {
      sections[0].rows[rowIdx][field] = value;
      handleChange('sections', sections);
    }
  };

  const handleRemoveListRow = (rowIdx: number) => {
    const sections = Array.isArray(data.sections) && data.sections.length > 0 
      ? JSON.parse(JSON.stringify(data.sections)) 
      : [{ title: 'Options', rows: [] }];
    if (sections[0].rows) {
      sections[0].rows.splice(rowIdx, 1);
      handleChange('sections', sections);
    }
  };

  // PDF / Media upload state
  const [isUploadingMedia, setIsUploadingMedia] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingMedia(true);
    setUploadError(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/flows/upload-media/', {
        method: 'POST',
        body: formData,
      });
      const result = await res.json();
      if (res.ok && result.success) {
        handleChange('media_url', result.file_url);
        handleChange('url', result.file_url);
        handleChange('filename', result.filename);
        handleChange('source', 'custom_url');
      } else {
        setUploadError(result.error || 'Failed to upload PDF file.');
      }
    } catch (err: any) {
      setUploadError(err.message || 'Network error uploading PDF.');
    } finally {
      setIsUploadingMedia(false);
    }
  };

  return (
    <aside className="builder-inspector">
      {/* Drawer Header */}
      <div className="inspector-header">
        <div className="inspector-title-wrap">
          <span
            className="inspector-type-badge"
            style={{ backgroundColor: `${accentColor}25`, color: accentColor }}
          >
            {def.label}
          </span>
          <input
            type="text"
            className="inspector-title-input"
            value={data.title || data.label || ''}
            onChange={(e) => handleChange('title', e.target.value)}
            placeholder="Step title"
          />
        </div>
        <button type="button" onClick={onClose} className="inspector-close-btn" title="Close Panel">
          ✕
        </button>
      </div>

      {/* Drawer Form Body */}
      <div className="inspector-body">
        {/* Variable Helper Pills */}
        {['message', 'welcome', 'buttons', 'list', 'question', 'capture_answer', 'webhook'].includes(
          data.type
        ) && (
          <div className="inspector-form-group">
            <label className="inspector-label">
              <span>Insert Dynamic Variable:</span>
            </label>
            <div className="variable-pills-wrap">
              {COMMON_VARIABLES.map((v) => (
                <button
                  key={v}
                  type="button"
                  className="var-pill"
                  onClick={() => insertVariable(v)}
                  title={`Insert {{${v}}}`}
                >
                  +{v}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 0. TRIGGER NODE */}
        {['trigger', 'start'].includes(data.type) && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Trigger Activation Mode:</label>
              <select
                className="inspector-select"
                value={data.trigger_type || 'always_on'}
                onChange={(e) => handleChange('trigger_type', e.target.value)}
              >
                <option value="always_on">Always On / First Message</option>
                <option value="first_incoming_message">First Incoming Message Only</option>
                <option value="keyword">Keyword Matching</option>
              </select>
            </div>
            {data.trigger_type === 'keyword' && (
              <div className="inspector-form-group">
                <label className="inspector-label">Keywords (comma-separated):</label>
                <input
                  type="text"
                  className="inspector-input"
                  value={data.trigger_keywords || ''}
                  onChange={(e) => handleChange('trigger_keywords', e.target.value)}
                  placeholder="e.g. hi, hello, admission, fees, courses"
                />
              </div>
            )}
          </>
        )}

        {/* 1. MESSAGE / WELCOME / QUESTION BODY */}
        {['message', 'welcome', 'question', 'capture_answer', 'end', 'human_handover'].includes(
          data.type
        ) && (
          <div className="inspector-form-group">
            <label className="inspector-label">
              <span>Message Text:</span>
            </label>
            <textarea
              className="inspector-textarea"
              rows={4}
              value={data.body || data.text || ''}
              onChange={(e) => {
                handleChange('body', e.target.value);
                handleChange('text', e.target.value);
              }}
              placeholder="Enter WhatsApp message text..."
            />
          </div>
        )}

        {/* 2. BUTTONS NODE */}
        {data.type === 'buttons' && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Header (Optional):</label>
              <input
                type="text"
                className="inspector-input"
                value={data.header || ''}
                onChange={(e) => handleChange('header', e.target.value)}
                placeholder="e.g. DigiPanda Admissions"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Body Text:</label>
              <textarea
                className="inspector-textarea"
                rows={3}
                value={data.body || ''}
                onChange={(e) => handleChange('body', e.target.value)}
                placeholder="Please choose an option:"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Footer (Optional):</label>
              <input
                type="text"
                className="inspector-input"
                value={data.footer || ''}
                onChange={(e) => handleChange('footer', e.target.value)}
                placeholder="e.g. Tap an option below"
              />
            </div>
            <div className="inspector-form-group">
              <div className="flex-between">
                <label className="inspector-label">Buttons (Max 3):</label>
                {(data.options || []).length < 3 && (
                  <button type="button" onClick={handleAddButton} className="btn-add-mini">
                    + Add Button
                  </button>
                )}
              </div>
              <div className="buttons-editor-stack">
                {(data.options || []).map((opt, idx) => (
                  <div key={opt.id || idx} className="button-editor-row">
                    <span className="btn-idx-tag">{idx + 1}</span>
                    <input
                      type="text"
                      className="inspector-input"
                      value={opt.title}
                      maxLength={20}
                      onChange={(e) => handleUpdateButton(idx, e.target.value)}
                      placeholder={`Button ${idx + 1} text`}
                    />
                    <button
                      type="button"
                      onClick={() => handleRemoveButton(idx)}
                      className="btn-del-mini"
                      title="Remove button"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* 3. LIST MENU NODE */}
        {data.type === 'list' && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Menu Button Text:</label>
              <input
                type="text"
                className="inspector-input"
                value={data.button_text || 'View Menu'}
                maxLength={20}
                onChange={(e) => handleChange('button_text', e.target.value)}
                placeholder="e.g. View Programs"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Body Text:</label>
              <textarea
                className="inspector-textarea"
                rows={3}
                value={data.body || ''}
                onChange={(e) => handleChange('body', e.target.value)}
                placeholder="Select an option from the menu below:"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Menu Catalog Source:</label>
              <select
                className="inspector-select"
                value={data.source || 'static'}
                onChange={(e) => handleChange('source', e.target.value)}
              >
                <option value="static">Custom Static Options & Answers</option>
                <option value="database">Dynamic Active Courses (from CRM)</option>
              </select>
            </div>

            {/* Custom Answers / Options Editor */}
            {data.source !== 'database' && (
              <div className="inspector-form-group">
                <div className="flex-between" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label className="inspector-label" style={{ margin: 0 }}>Custom Options / Answers ({currentListRows.length}/10):</label>
                  {currentListRows.length < 10 && (
                    <button type="button" onClick={handleAddListRow} className="btn-add-mini" style={{ fontSize: '11px', padding: '4px 10px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '6px', cursor: 'pointer' }}>
                      + Add Option
                    </button>
                  )}
                </div>

                <div className="buttons-editor-stack" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {currentListRows.length === 0 ? (
                    <div style={{ padding: '12px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px', border: '1px dashed var(--border-color)', textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                      No custom answers added yet. Click <strong>+ Add Option</strong> to create list answers.
                    </div>
                  ) : (
                    currentListRows.map((row, idx) => (
                      <div key={row.id || idx} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8' }}>Option #{idx + 1}</span>
                          <button
                            type="button"
                            onClick={() => handleRemoveListRow(idx)}
                            style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '12px', padding: '2px 6px' }}
                            title="Remove this option"
                          >
                            ✕
                          </button>
                        </div>
                        <input
                          type="text"
                          className="inspector-input"
                          value={row.title || ''}
                          maxLength={24}
                          onChange={(e) => handleUpdateListRow(idx, 'title', e.target.value)}
                          placeholder="Option Title (max 24 chars)*"
                        />
                        <input
                          type="text"
                          className="inspector-input"
                          value={row.description || ''}
                          maxLength={72}
                          onChange={(e) => handleUpdateListRow(idx, 'description', e.target.value)}
                          placeholder="Description (optional, max 72 chars)"
                          style={{ fontSize: '12px' }}
                        />
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {/* 4. CONDITION NODE */}
        {data.type === 'condition' && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Variable Name:</label>
              <input
                type="text"
                className="inspector-input"
                value={data.variable || ''}
                onChange={(e) => handleChange('variable', e.target.value)}
                placeholder="e.g. interested_domain or score"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Comparison Operator:</label>
              <select
                className="inspector-select"
                value={data.operator || 'equals'}
                onChange={(e) => handleChange('operator', e.target.value as any)}
              >
                <option value="equals">Equals (Exact match)</option>
                <option value="not_equals">Does Not Equal</option>
                <option value="contains">Contains substring</option>
                <option value="not_contains">Does Not Contain</option>
                <option value="exists">Variable Exists (Not empty)</option>
                <option value="not_exists">Variable Does Not Exist</option>
              </select>
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Target Value:</label>
              <input
                type="text"
                className="inspector-input"
                value={data.value || ''}
                onChange={(e) => handleChange('value', e.target.value)}
                placeholder="e.g. Python or fullstack"
              />
            </div>
            <div className="inspector-info-banner">
              <LucideIcons.GitFork size={14} className="text-amber-400" />
              <span>Connect the green "YES" handle for True, or rose "NO" handle for False.</span>
            </div>
          </>
        )}

        {/* 5. DELAY NODE */}
        {data.type === 'delay' && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Wait Duration:</label>
              <div className="duration-input-row">
                <input
                  type="number"
                  min={1}
                  className="inspector-input input-number"
                  value={data.amount || 15}
                  onChange={(e) => {
                    const amt = Number(e.target.value);
                    const unit = data.unit || 'minutes';
                    let sec = amt * 60;
                    if (unit === 'seconds') sec = amt;
                    if (unit === 'hours') sec = amt * 3600;
                    if (unit === 'days') sec = amt * 86400;
                    handleChange('amount', amt);
                    handleChange('delay_seconds', sec);
                  }}
                />
                <select
                  className="inspector-select select-unit"
                  value={data.unit || 'minutes'}
                  onChange={(e) => {
                    const unit = e.target.value as any;
                    const amt = data.amount || 15;
                    let sec = amt * 60;
                    if (unit === 'seconds') sec = amt;
                    if (unit === 'hours') sec = amt * 3600;
                    if (unit === 'days') sec = amt * 86400;
                    handleChange('unit', unit);
                    handleChange('delay_seconds', sec);
                  }}
                >
                  <option value="seconds">Seconds</option>
                  <option value="minutes">Minutes</option>
                  <option value="hours">Hours</option>
                  <option value="days">Days</option>
                </select>
              </div>
            </div>
            <div className="inspector-info-banner banner-warning">
              <LucideIcons.AlertTriangle size={14} className="text-amber-400" />
              <span>
                Meta WhatsApp policy restricts freeform messaging outside the 24-hour service
                window. If delay exceeds customer activity window, session transitions to counselor.
              </span>
            </div>
          </>
        )}

        {/* 6. CAPTURE ANSWER / QUESTION */}
        {['question', 'capture_answer'].includes(data.type) && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Save Answer to Variable:</label>
              <input
                type="text"
                className="inspector-input"
                value={data.variable_name || ''}
                onChange={(e) => handleChange('variable_name', e.target.value)}
                placeholder="e.g. qualification or preferred_batch"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Expected Input Type:</label>
              <select
                className="inspector-select"
                value={data.expected_type || 'text'}
                onChange={(e) => handleChange('expected_type', e.target.value as any)}
              >
                <option value="text">General Text</option>
                <option value="number">Numeric</option>
                <option value="email">Email Address</option>
                <option value="phone">Phone Number</option>
              </select>
            </div>
          </>
        )}

        {/* 7. UPDATE LEAD / SAVE DATA */}
        {['save_data', 'update_lead', 'lead_status'].includes(data.type) && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">CRM Lead Status:</label>
              <select
                className="inspector-select"
                value={data.status || 'Qualified Interested'}
                onChange={(e) => handleChange('status', e.target.value)}
              >
                <option value="New Lead">New Lead</option>
                <option value="Qualified Interested">Qualified Interested</option>
                <option value="Counseling Scheduled">Counseling Scheduled</option>
                <option value="Walkin Expected">Walkin Expected</option>
                <option value="Enrolled">Enrolled</option>
                <option value="Not Interested">Not Interested</option>
              </select>
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Schedule Follow-Up (Hours):</label>
              <input
                type="number"
                min={1}
                className="inspector-input"
                value={data.follow_up_hours || 4}
                onChange={(e) => handleChange('follow_up_hours', Number(e.target.value))}
              />
            </div>
          </>
        )}

        {/* 8. WEBHOOK NODE */}
        {['webhook', 'api_request'].includes(data.type) && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Target URL (HTTPS Only):</label>
              <input
                type="url"
                className="inspector-input"
                value={data.url || ''}
                onChange={(e) => handleChange('url', e.target.value)}
                placeholder="https://api.externalcrm.com/v1/webhook"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">HTTP Method:</label>
              <select
                className="inspector-select"
                value={data.method || 'POST'}
                onChange={(e) => handleChange('method', e.target.value as any)}
              >
                <option value="POST">POST</option>
                <option value="GET">GET</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
                <option value="DELETE">DELETE</option>
              </select>
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">JSON Payload / Body:</label>
              <textarea
                className="inspector-textarea font-mono text-xs"
                rows={4}
                value={typeof data.payload === 'string' ? data.payload : JSON.stringify(data.payload || {}, null, 2)}
                onChange={(e) => handleChange('payload', e.target.value)}
                placeholder='{\n  "phone": "{{customer_phone}}"\n}'
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Save Response to Variable:</label>
              <input
                type="text"
                className="inspector-input"
                value={data.save_response_to || ''}
                onChange={(e) => handleChange('save_response_to', e.target.value)}
                placeholder="e.g. api_response"
              />
            </div>
            <div className="inspector-info-banner banner-safe">
              <LucideIcons.ShieldCheck size={14} className="text-emerald-400" />
              <span>SSRF Guard active: Connection-time IP validation blocks private addresses.</span>
            </div>
          </>
        )}

        {/* 9. MEDIA NODE */}
        {['media', 'brochure'].includes(data.type) && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Media Document Source:</label>
              <select
                className="inspector-select"
                value={data.source || 'custom_url'}
                onChange={(e) => handleChange('source', e.target.value)}
              >
                <option value="custom_url">Direct Upload / Custom PDF</option>
                <option value="selected_course_brochure">Dynamic Course Brochure (from CRM catalog)</option>
              </select>
            </div>

            {/* Direct PDF Uploader */}
            <div className="inspector-form-group">
              <label className="inspector-label">Attach PDF Document:</label>
              <input
                type="file"
                ref={fileInputRef}
                accept=".pdf,application/pdf,.png,.jpg,.jpeg,.doc,.docx"
                style={{ display: 'none' }}
                onChange={handleFileUpload}
              />
              <button
                type="button"
                className="btn-create-flow"
                style={{ width: '100%', justifyContent: 'center', padding: '9px 14px', background: '#0284c7' }}
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploadingMedia}
              >
                <LucideIcons.Upload size={14} />
                <span>{isUploadingMedia ? 'Uploading Document...' : '📎 Attach / Upload PDF from Computer'}</span>
              </button>
              {uploadError && <p style={{ color: '#ef4444', fontSize: '11px', marginTop: '4px' }}>{uploadError}</p>}
            </div>

            {/* Uploaded File Badge */}
            {(data.media_url || data.url) && (
              <div className="inspector-info-banner banner-safe" style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <LucideIcons.FileCheck size={16} className="text-emerald-400" />
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', overflow: 'hidden' }}>
                  <span style={{ fontWeight: 600, fontSize: '12px' }}>Attached: {data.filename || 'Document.pdf'}</span>
                  <a
                    href={data.media_url || data.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: '#38bdf8', fontSize: '11px', textDecoration: 'underline' }}
                  >
                    Preview Attached PDF ↗
                  </a>
                </div>
              </div>
            )}

            <div className="inspector-form-group">
              <label className="inspector-label">Document File URL (or CDN link):</label>
              <input
                type="url"
                className="inspector-input"
                value={data.media_url || data.url || ''}
                onChange={(e) => {
                  handleChange('media_url', e.target.value);
                  handleChange('url', e.target.value);
                }}
                placeholder="https://example.com/brochures/syllabus.pdf"
              />
            </div>

            <div className="inspector-form-group">
              <label className="inspector-label">Filename / Display Title:</label>
              <input
                type="text"
                className="inspector-input"
                value={data.filename || ''}
                onChange={(e) => handleChange('filename', e.target.value)}
                placeholder="e.g. Course_Curriculum.pdf"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Caption Text:</label>
              <textarea
                className="inspector-textarea"
                rows={3}
                value={data.caption || data.body || ''}
                onChange={(e) => {
                  handleChange('caption', e.target.value);
                  handleChange('body', e.target.value);
                }}
                placeholder="Here is the detailed syllabus and curriculum guide."
              />
            </div>
          </>
        )}

        {/* 10. LOCATION NODE */}
        {['location', 'branch_location'].includes(data.type) && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Location Source:</label>
              <select
                className="inspector-select"
                value={data.source || 'dynamic_branch'}
                onChange={(e) => handleChange('source', e.target.value)}
              >
                <option value="dynamic_branch">Dynamic Branch Location (from CRM)</option>
                <option value="custom">Custom Address & GPS Pin</option>
              </select>
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Location / Venue Name:</label>
              <input
                type="text"
                className="inspector-input"
                value={data.name || ''}
                onChange={(e) => handleChange('name', e.target.value)}
                placeholder="e.g. DigiPanda Tech Academy"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Street Address:</label>
              <textarea
                className="inspector-textarea"
                rows={2}
                value={data.address || ''}
                onChange={(e) => handleChange('address', e.target.value)}
                placeholder="e.g. 123 Anna Salai, Chennai, Tamil Nadu"
              />
            </div>
            <div className="duration-input-row">
              <div className="inspector-form-group" style={{ flex: 1 }}>
                <label className="inspector-label">Latitude:</label>
                <input
                  type="number"
                  step="0.0001"
                  className="inspector-input"
                  value={data.latitude ?? 13.0827}
                  onChange={(e) => handleChange('latitude', parseFloat(e.target.value))}
                />
              </div>
              <div className="inspector-form-group" style={{ flex: 1 }}>
                <label className="inspector-label">Longitude:</label>
                <input
                  type="number"
                  step="0.0001"
                  className="inspector-input"
                  value={data.longitude ?? 80.2707}
                  onChange={(e) => handleChange('longitude', parseFloat(e.target.value))}
                />
              </div>
            </div>
          </>
        )}

        {/* 11. ASSIGN TELECALLER / COUNSELOR */}
        {['assign_telecaller', 'assign_agent'].includes(data.type) && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Counselor Assignment Strategy:</label>
              <select
                className="inspector-select"
                value={data.mode || 'round_robin'}
                onChange={(e) => handleChange('mode', e.target.value)}
              >
                <option value="round_robin">Round-Robin Active Counselors</option>
                <option value="branch_counselor">Branch Primary Counselor</option>
              </select>
            </div>
            <div className="inspector-form-group">
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={data.only_if_unassigned !== false}
                  onChange={(e) => handleChange('only_if_unassigned', e.target.checked)}
                />
                <span>Only assign if lead does not already have an owner</span>
              </label>
            </div>
          </>
        )}

        {/* 12. SUBFLOW / GO TO */}
        {['subflow', 'goto_flow'].includes(data.type) && (
          <>
            <div className="inspector-form-group">
              <label className="inspector-label">Target Subflow ID:</label>
              <input
                type="number"
                className="inspector-input"
                value={data.flow_id || ''}
                onChange={(e) => handleChange('flow_id', e.target.value ? parseInt(e.target.value) : null)}
                placeholder="e.g. 12"
              />
            </div>
            <div className="inspector-form-group">
              <label className="inspector-label">Target Step ID (Optional):</label>
              <input
                type="text"
                className="inspector-input"
                value={data.target_node_id || ''}
                onChange={(e) => handleChange('target_node_id', e.target.value)}
                placeholder="e.g. welcome_step_1"
              />
            </div>
          </>
        )}
      </div>

      {/* Drawer Footer Actions */}
      <div className="inspector-footer">
        <button
          type="button"
          onClick={() => onDeleteNode(node.id)}
          className="btn-delete-node"
          title="Delete this step"
        >
          <LucideIcons.Trash2 size={14} />
          <span>Delete Step</span>
        </button>
      </div>
    </aside>
  );
};
