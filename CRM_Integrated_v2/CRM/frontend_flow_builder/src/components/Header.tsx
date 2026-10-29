import React, { useState } from 'react';
import * as Icons from 'lucide-react';
import { FlowDefinition, BusinessLineOption, BranchOption, FlowVersion } from '../types';

interface HeaderProps {
  flow: FlowDefinition;
  versions: FlowVersion[];
  businessLines: BusinessLineOption[];
  branches: BranchOption[];
  selectedLine: number | null;
  selectedBranch: number | null;
  saveStatus: 'saved' | 'saving' | 'unsaved';
  isPublishing: boolean;
  isValidating: boolean;
  isUnpublishing?: boolean;
  onUnpublish?: () => void;
  onUpdateFlowName: (name: string) => void;
  onSelectBusinessLine: (lineId: number) => void;
  onSelectBranch: (branchId: number) => void;
  onSaveDraft: () => void;
  onPublish: () => void;
  onValidate: () => void;
  onOpenSimulator: () => void;
  onRestoreVersion: (versionId: number) => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  flow,
  versions,
  businessLines,
  branches,
  selectedLine,
  selectedBranch,
  saveStatus,
  isPublishing,
  isValidating,
  isUnpublishing,
  onUnpublish,
  onUpdateFlowName,
  onSelectBusinessLine,
  onSelectBranch,
  onSaveDraft,
  onPublish,
  onValidate,
  onOpenSimulator,
  onRestoreVersion,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
}) => {
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameInput, setNameInput] = useState(flow.name);
  const [showVersionDropdown, setShowVersionDropdown] = useState(false);

  const handleNameBlur = () => {
    setIsEditingName(false);
    if (nameInput.trim() && nameInput !== flow.name) {
      onUpdateFlowName(nameInput.trim());
    } else {
      setNameInput(flow.name);
    }
  };

  const handleNameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleNameBlur();
    } else if (e.key === 'Escape') {
      setNameInput(flow.name);
      setIsEditingName(false);
    }
  };

  return (
    <header className="builder-header">
      {/* Left: Back + Brand + Flow Name & Version */}
      <div className="header-left">
        <a href="/automations/" className="btn-back" title="Back to Automations Dashboard">
          <Icons.ArrowLeft size={16} />
          <span>Automations</span>
        </a>

        <div className="header-divider" />

        <div className="builder-brand">
          <div className="brand-icon">
            <Icons.Zap size={18} className="text-emerald-400" />
          </div>

          <div className="brand-meta">
            <div className="brand-title-wrap">
              {isEditingName ? (
                <input
                  type="text"
                  className="flow-name-input"
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  onBlur={handleNameBlur}
                  onKeyDown={handleNameKeyDown}
                  autoFocus
                />
              ) : (
                <h1
                  className="flow-name"
                  onClick={() => setIsEditingName(true)}
                  title="Click to rename flow"
                >
                  {flow.name}
                  <Icons.Pencil size={12} className="edit-pencil-icon" />
                </h1>
              )}

              {/* Version & Status Badge */}
              <div className="version-pill-container">
                <button
                  type="button"
                  className="version-tag-btn"
                  onClick={() => setShowVersionDropdown(!showVersionDropdown)}
                  title="View Version History"
                >
                  <span className="version-tag">v{flow.version || 1}</span>
                  <span className={`status-badge status-${flow.status}`}>
                    {flow.status === 'published' ? 'Published' : 'Draft'}
                  </span>
                  <Icons.ChevronDown size={12} />
                </button>

                {showVersionDropdown && (
                  <div className="version-history-dropdown">
                    <div className="version-dropdown-header">
                      <span>Version History</span>
                      <button
                        type="button"
                        onClick={() => setShowVersionDropdown(false)}
                        className="close-dropdown-btn"
                      >
                        ✕
                      </button>
                    </div>
                    <div className="version-list">
                      {versions.length === 0 ? (
                        <div className="version-empty-text">No prior versions recorded.</div>
                      ) : (
                        versions.map((ver) => (
                          <div
                            key={ver.id}
                            className={`version-item ${ver.version_number === flow.version ? 'is-current' : ''}`}
                          >
                            <div className="version-meta">
                              <span className="ver-num">v{ver.version_number}</span>
                              <span className={`ver-status status-${ver.status}`}>{ver.status}</span>
                              <span className="ver-date">
                                {new Date(ver.created_at).toLocaleDateString([], {
                                  month: 'short',
                                  day: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })}
                              </span>
                            </div>
                            {ver.change_summary && (
                              <p className="ver-summary">{ver.change_summary}</p>
                            )}
                            {ver.version_number !== flow.version && (
                              <button
                                type="button"
                                className="btn-restore-version"
                                onClick={() => {
                                  onRestoreVersion(ver.id);
                                  setShowVersionDropdown(false);
                                }}
                              >
                                Restore
                              </button>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Save Status Dot */}
            <div className="save-status-wrap">
              <span className={`save-status-dot ${saveStatus}`} />
              <span className="save-status-text">
                {saveStatus === 'saved' && 'Saved just now'}
                {saveStatus === 'saving' && 'Saving draft...'}
                {saveStatus === 'unsaved' && 'Unsaved changes (Ctrl+S)'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Center: Line & Branch Selectors */}
      <div className="header-center">
        <div className="header-line-branch-cluster">
          <div className="account-selector-wrap">
            <Icons.PhoneCall size={13} className="text-emerald-400" />
            <span className="selector-label">WhatsApp Line:</span>
            <select
              className="account-select"
              value={selectedLine || ''}
              onChange={(e) => onSelectBusinessLine(Number(e.target.value))}
            >
              <option value="">Default (All Numbers)</option>
              {businessLines.map((line) => (
                <option key={line.id} value={line.id}>
                  {line.name} ({line.phone_number})
                </option>
              ))}
            </select>
          </div>

          <div className="branch-selector-pill-wrap">
            <span className="branch-icon">🏢</span>
            <span className="selector-label">CRM Branch:</span>
            <select
              className="branch-select"
              value={selectedBranch || ''}
              onChange={(e) => onSelectBranch(Number(e.target.value))}
            >
              <option value="">Auto / Main Branch</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Right: Undo/Redo + Simulator + Validate + Save + Publish */}
      <div className="header-right">
        {/* Undo / Redo */}
        <div className="history-btn-group">
          <button
            type="button"
            className="header-icon-btn"
            title="Undo (Ctrl+Z)"
            disabled={!canUndo}
            onClick={onUndo}
          >
            <Icons.Undo2 size={16} />
          </button>
          <button
            type="button"
            className="header-icon-btn"
            title="Redo (Ctrl+Y)"
            disabled={!canRedo}
            onClick={onRedo}
          >
            <Icons.Redo2 size={16} />
          </button>
        </div>

        {/* Validate Graph */}
        <button
          type="button"
          className="header-action-btn btn-ghost"
          onClick={onValidate}
          disabled={isValidating}
          title="Verify graph connections & check for errors"
        >
          <Icons.ShieldCheck size={16} className="text-sky-400" />
          <span>{isValidating ? 'Validating...' : 'Validate'}</span>
        </button>

        {/* Test Simulator */}
        <button
          type="button"
          className="header-action-btn btn-simulator"
          onClick={onOpenSimulator}
          title="Safe dry-run in interactive WhatsApp mobile simulator"
        >
          <Icons.Smartphone size={16} className="text-amber-400" />
          <span>Test Flow</span>
        </button>

        {/* Save Draft */}
        <button
          type="button"
          className="header-action-btn btn-save"
          onClick={onSaveDraft}
          disabled={saveStatus === 'saving'}
          title="Save draft workflow (Ctrl+S)"
        >
          <Icons.Save size={16} />
          <span>Save Draft</span>
        </button>

        {/* Unpublish / Pause (when published) */}
        {flow.status === 'published' && onUnpublish && (
          <button
            type="button"
            className="header-action-btn btn-ghost"
            style={{ color: '#f59e0b', borderColor: 'rgba(245, 158, 11, 0.4)' }}
            onClick={onUnpublish}
            disabled={isUnpublishing}
            title="Pause and revert this live flow back to draft status"
          >
            <Icons.PauseCircle size={16} />
            <span>{isUnpublishing ? 'Pausing...' : 'Pause / Unpublish'}</span>
          </button>
        )}

        {/* Publish */}
        <button
          type="button"
          className="header-action-btn btn-publish"
          onClick={onPublish}
          disabled={isPublishing}
          title="Publish immutable version to live WhatsApp"
        >
          <Icons.Send size={16} />
          <span>{isPublishing ? 'Publishing...' : flow.status === 'published' ? 'Publish Update' : 'Publish Flow'}</span>
        </button>
      </div>
    </header>
  );
};
