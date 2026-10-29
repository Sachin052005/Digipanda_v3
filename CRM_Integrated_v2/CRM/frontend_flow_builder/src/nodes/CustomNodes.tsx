import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import * as LucideIcons from 'lucide-react';
import { PALETTE_NODES } from '../constants';
import { FlowNodeData } from '../types';

interface DynamicNodeProps extends NodeProps {
  data: FlowNodeData;
}

const getNodeDef = (type: string) => {
  return PALETTE_NODES.find((p) => p.type === type) || PALETTE_NODES[1];
};

const renderIcon = (iconName: string, color: string) => {
  const IconComponent = (LucideIcons as any)[iconName] || LucideIcons.Activity;
  return <IconComponent size={16} color={color} strokeWidth={2.2} />;
};

export const FlowNode = memo(({ id, data, selected }: DynamicNodeProps) => {
  const def = getNodeDef(data.type);
  const accentColor = def?.accentColor || '#3b82f6';

  const isTrigger = data.type === 'trigger' || data.type === 'start';
  const isEnd = data.type === 'end';
  const isCondition = data.type === 'condition';
  const isButtons = data.type === 'buttons';
  const isList = data.type === 'list';
  const listRows = Array.isArray(data.sections) && data.sections.length > 0 && Array.isArray(data.sections[0]?.rows)
    ? data.sections[0].rows
    : [];
  const isWebhook = data.type === 'webhook' || data.type === 'api_request';

  return (
    <div
      className={`flow-node-card ${selected ? 'is-selected' : ''}`}
      style={{
        borderTopColor: accentColor,
      }}
    >
      {/* Input Handle (if not trigger) */}
      {!isTrigger && (
        <Handle
          type="target"
          position={Position.Left}
          id="target"
          className="flow-node-handle handle-target"
        />
      )}

      {/* Node Header */}
      <div className="flow-node-header">
        <div
          className="flow-node-icon-wrap"
          style={{ backgroundColor: `${accentColor}20` }}
        >
          {renderIcon(def.iconName, accentColor)}
        </div>
        <div className="flow-node-title-group">
          <span className="flow-node-type-label" style={{ color: accentColor }}>
            {def.label}
          </span>
          <h4 className="flow-node-title">
            {data.title || data.label || def.label}
          </h4>
        </div>
      </div>

      {/* Node Body / Content Preview */}
      <div className="flow-node-body">
        {data.body && (
          <p className="flow-node-text-preview">
            {data.body.length > 85 ? `${data.body.substring(0, 85)}...` : data.body}
          </p>
        )}

        {/* Condition Node Visual Preview */}
        {isCondition && (
          <div className="flow-node-cond-preview">
            <span className="cond-var">{data.variable || 'variable'}</span>
            <span className="cond-op">{data.operator || 'equals'}</span>
            <span className="cond-val">{`"${data.value || ''}"`}</span>
          </div>
        )}

        {/* Delay Node Preview */}
        {data.type === 'delay' && (
          <div className="flow-node-badge-delay">
            <LucideIcons.Clock size={12} className="mr-1" />
            <span>
              Wait {data.amount || Math.round((data.delay_seconds || 60) / 60)}{' '}
              {data.unit || 'minutes'}
            </span>
          </div>
        )}

        {/* Webhook URL Preview */}
        {isWebhook && (
          <div className="flow-node-url-preview">
            <span className="webhook-method">{data.method || 'POST'}</span>
            <span className="webhook-url" title={data.url}>
              {data.url || 'https://api.example.com'}
            </span>
          </div>
        )}

        {/* Buttons List Preview */}
        {isButtons && data.options && (
          <div className="flow-node-buttons-stack">
            {data.options.slice(0, 3).map((opt, idx) => (
              <div key={opt.id || idx} className="flow-node-button-chip">
                <span>🔘 {opt.title}</span>
                {/* Specific source handle for this button option */}
                <Handle
                  type="source"
                  position={Position.Right}
                  id={opt.id}
                  className="flow-node-handle handle-button"
                  style={{ top: `${45 + (idx + 1) * 26}px` }}
                  title={`Branch: ${opt.title}`}
                />
              </div>
            ))}
          </div>
        )}

        {/* List Menu Options Preview & Specific Branch Handles */}
        {isList && (
          <div className="flow-node-buttons-stack">
            <div className="flow-node-list-pill">
              <LucideIcons.Menu size={12} className="inline mr-1 text-sky-400" />
              <span>{data.button_text || 'View Options'}</span>
            </div>
            {listRows.slice(0, 5).map((row: any, idx: number) => (
              <div key={row.id || idx} className="flow-node-button-chip">
                <span>📋 {row.title}</span>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={row.id}
                  className="flow-node-handle handle-button"
                  style={{ top: `${65 + (idx + 1) * 26}px` }}
                  title={`Branch: ${row.title}`}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Output Handles */}
      {!isEnd && !isCondition && !isWebhook && (
        <Handle
          type="source"
          position={Position.Right}
          id="default"
          className="flow-node-handle handle-source"
          title="Next step"
        />
      )}

      {/* Condition Node Branches */}
      {isCondition && (
        <>
          <div className="flow-node-branch-labels">
            <span className="branch-label-yes">YES</span>
            <span className="branch-label-no">NO</span>
          </div>
          <Handle
            type="source"
            position={Position.Right}
            id="YES"
            className="flow-node-handle handle-yes"
            style={{ top: '38%' }}
            title="Condition TRUE (YES)"
          />
          <Handle
            type="source"
            position={Position.Right}
            id="NO"
            className="flow-node-handle handle-no"
            style={{ top: '68%' }}
            title="Condition FALSE (NO)"
          />
        </>
      )}

      {/* Webhook Node Branches (Success / Error) */}
      {isWebhook && (
        <>
          <div className="flow-node-branch-labels">
            <span className="branch-label-yes">OK</span>
            <span className="branch-label-no">ERR</span>
          </div>
          <Handle
            type="source"
            position={Position.Right}
            id="default"
            className="flow-node-handle handle-yes"
            style={{ top: '38%' }}
            title="Success (2xx)"
          />
          <Handle
            type="source"
            position={Position.Right}
            id="error"
            className="flow-node-handle handle-no"
            style={{ top: '68%' }}
            title="Failure / Error"
          />
        </>
      )}
    </div>
  );
});

export const nodeTypes = {
  trigger: FlowNode,
  message: FlowNode,
  welcome: FlowNode,
  buttons: FlowNode,
  list: FlowNode,
  condition: FlowNode,
  delay: FlowNode,
  question: FlowNode,
  capture_answer: FlowNode,
  save_data: FlowNode,
  update_lead: FlowNode,
  lead_status: FlowNode,
  assign_telecaller: FlowNode,
  media: FlowNode,
  location: FlowNode,
  webhook: FlowNode,
  api_request: FlowNode,
  human_handover: FlowNode,
  subflow: FlowNode,
  goto: FlowNode,
  end: FlowNode,
};
