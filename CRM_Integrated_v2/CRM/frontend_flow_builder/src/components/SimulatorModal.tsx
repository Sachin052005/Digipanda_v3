import React, { useState } from 'react';
import * as Icons from 'lucide-react';
import { SimulatorState, NodeOption, ListSection, SimulatorMessage } from '../types';

interface SimulatorModalProps {
  simulator: SimulatorState;
  onSendMessage: (text: string, interactiveReply?: string) => void;
  onReset: () => void;
  onClose: () => void;
}

export const SimulatorModal: React.FC<SimulatorModalProps> = ({
  simulator,
  onSendMessage,
  onReset,
  onClose,
}) => {
  const [inputText, setInputText] = useState('');
  const [activeListMsg, setActiveListMsg] = useState<SimulatorMessage | null>(null);

  if (!simulator.isOpen) return null;

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onSendMessage(inputText.trim());
    setInputText('');
  };

  const handleSelectRow = (row: { id: string; title: string; description?: string }) => {
    setActiveListMsg(null);
    onSendMessage(row.title, row.id);
  };

  return (
    <div className="simulator-overlay">
      <div className="simulator-window">
        {/* Simulator Top Bar */}
        <div className="simulator-top-bar">
          <div className="sim-title-group">
            <Icons.Smartphone size={18} className="text-emerald-400" />
            <div>
              <h3 className="sim-window-title">WhatsApp Flow Simulator</h3>
              <p className="sim-window-sub">Safe dry-run preview (Zero live messages sent)</p>
            </div>
          </div>
          <div className="sim-top-actions">
            <button type="button" onClick={onReset} className="sim-btn-reset" title="Restart Simulator">
              <Icons.RotateCcw size={14} />
              <span>Reset</span>
            </button>
            <button type="button" onClick={onClose} className="sim-btn-close" title="Close Simulator">
              ✕
            </button>
          </div>
        </div>

        {/* Simulator Grid (Handset Mockup + Live Debug Panel) */}
        <div className="simulator-content-grid">
          {/* Mobile Screen Container */}
          <div className="simulator-phone-frame">
            {/* WhatsApp App Header */}
            <div className="phone-whatsapp-header">
              <div className="phone-wa-avatar">
                <Icons.Bot size={16} className="text-emerald-400" />
              </div>
              <div className="phone-wa-meta">
                <span className="phone-wa-name">DigiPanda CRM Bot</span>
                <span className="phone-wa-status">Automated flow active</span>
              </div>
            </div>

            {/* Conversation Messages Scroll */}
            <div className="phone-messages-container">
              {simulator.messages.length === 0 ? (
                <div className="sim-empty-state">
                  <Icons.MessageSquare size={32} className="text-slate-600 mb-2" />
                  <p>Send an initial message below to trigger the workflow.</p>
                </div>
              ) : (
                simulator.messages.map((msg, idx) => {
                  const isUser = msg.sender === 'user' || msg.type === 'user_reply';

                  if (isUser) {
                    return (
                      <div key={idx} className="sim-message-bubble-wrap sim-user-align">
                        <div className="sim-user-bubble">
                          <div className="sim-msg-body">{msg.body}</div>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div key={idx} className="sim-message-bubble-wrap">
                      {/* Bot Message Bubble */}
                      <div className="sim-bot-bubble">
                        {msg.header && <div className="sim-msg-header">{msg.header}</div>}
                        {msg.body && <div className="sim-msg-body">{msg.body}</div>}

                        {/* Interactive Buttons Preview */}
                        {msg.type === 'buttons' && msg.options && (
                          <div className="sim-interactive-buttons-stack">
                            {msg.options.map((opt: NodeOption) => (
                              <button
                                key={opt.id}
                                type="button"
                                className="sim-btn-option"
                                disabled={simulator.isLoading}
                                onClick={() => onSendMessage(opt.title, opt.id)}
                              >
                                🔘 {opt.title}
                              </button>
                            ))}
                          </div>
                        )}

                        {/* Interactive List Preview Button (Clickable!) */}
                        {msg.type === 'list' && (
                          <button
                            type="button"
                            className="sim-list-trigger-btn"
                            disabled={simulator.isLoading}
                            onClick={() => setActiveListMsg(msg)}
                            title="Click to view and choose an option"
                          >
                            <Icons.Menu size={14} className="text-sky-400" />
                            <span>📋 {msg.button_text || 'View Options'}</span>
                            <Icons.ChevronRight size={14} className="text-sky-400 ml-auto" />
                          </button>
                        )}

                        {/* Location Pin Preview */}
                        {msg.type === 'location' && (
                          <div className="sim-location-card">
                            <Icons.MapPin size={20} className="text-rose-400" />
                            <div>
                              <strong>{msg.name || 'Branch Campus'}</strong>
                              <p>{msg.address || 'Chennai, Tamil Nadu'}</p>
                            </div>
                          </div>
                        )}

                        {/* Media PDF Preview */}
                        {msg.type === 'media' && (
                          <div className="sim-media-card">
                            <Icons.FileText size={20} className="text-pink-400" />
                            <div>
                              <strong>{msg.filename || 'Brochure.pdf'}</strong>
                              {msg.caption && <p>{msg.caption}</p>}
                            </div>
                          </div>
                        )}

                        {msg.footer && <div className="sim-msg-footer">{msg.footer}</div>}
                      </div>
                    </div>
                  );
                })
              )}

              {simulator.isLoading && (
                <div className="sim-typing-indicator">
                  <span />
                  <span />
                  <span />
                </div>
              )}

              {simulator.isComplete && (
                <div className="sim-flow-completed-pill">
                  <Icons.CheckCircle2 size={14} className="text-emerald-400 mr-1" />
                  <span>Workflow Execution Completed</span>
                </div>
              )}
            </div>

            {/* Sliding WhatsApp List Menu Sheet inside Phone Frame */}
            {activeListMsg && (
              <div className="sim-list-sheet-backdrop" onClick={() => setActiveListMsg(null)}>
                <div className="sim-list-sheet" onClick={(e) => e.stopPropagation()}>
                  <div className="sim-list-sheet-header">
                    <div className="flex items-center gap-2">
                      <Icons.ListFilter size={15} className="text-emerald-400" />
                      <span className="sim-list-sheet-title">
                        {activeListMsg.header || activeListMsg.button_text || 'Select an Option'}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="sim-list-sheet-close"
                      onClick={() => setActiveListMsg(null)}
                      title="Close"
                    >
                      ✕
                    </button>
                  </div>

                  <div className="sim-list-sheet-body">
                    {(!activeListMsg.sections || activeListMsg.sections.length === 0 || activeListMsg.sections.every((s: any) => !s.rows || s.rows.length === 0)) ? (
                      <div className="sim-list-empty-note">
                        <Icons.AlertCircle size={16} className="text-amber-400 mb-1 inline" />
                        <p>No options configured for this list node.</p>
                      </div>
                    ) : (
                      activeListMsg.sections.map((sec: ListSection, sIdx: number) => (
                        <div key={sIdx} className="sim-list-sec-block">
                          {sec.title && <div className="sim-list-sec-name">{sec.title}</div>}
                          <div className="sim-list-rows-group">
                            {(sec.rows || []).map((row: any) => (
                              <button
                                key={row.id}
                                type="button"
                                className="sim-list-row-item"
                                disabled={simulator.isLoading}
                                onClick={() => handleSelectRow(row)}
                              >
                                <div className="sim-list-row-text">
                                  <span className="sim-list-row-main">{row.title}</span>
                                  {row.description && (
                                    <span className="sim-list-row-sub">{row.description}</span>
                                  )}
                                </div>
                                <div className="sim-list-row-arrow">
                                  <Icons.ChevronRight size={14} />
                                </div>
                              </button>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Simulated WhatsApp Reply Bar */}
            <form onSubmit={handleSend} className="phone-chat-input-bar">
              <input
                type="text"
                placeholder={simulator.isComplete ? 'Workflow finished' : 'Type simulated reply...'}
                value={inputText}
                disabled={simulator.isLoading}
                onChange={(e) => setInputText(e.target.value)}
                className="phone-chat-input"
              />
              <button
                type="submit"
                disabled={!inputText.trim() || simulator.isLoading}
                className="phone-chat-send-btn"
                title="Send simulated reply"
              >
                <Icons.Send size={15} />
              </button>
            </form>
          </div>

          {/* Right Live Debug & Variable State Panel */}
          <div className="simulator-debug-panel">
            <div className="debug-panel-section">
              <h4 className="debug-section-title">
                <Icons.Cpu size={14} className="text-sky-400" />
                <span>Execution State</span>
              </h4>
              <div className="debug-state-box">
                <div className="debug-row">
                  <span className="debug-label">Current Node:</span>
                  <span className="debug-value">{simulator.currentNodeId || 'trigger_1'}</span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Status:</span>
                  <span className={`debug-badge ${simulator.isComplete ? 'badge-complete' : 'badge-active'}`}>
                    {simulator.isComplete ? 'Completed' : 'Running'}
                  </span>
                </div>
              </div>
            </div>

            <div className="debug-panel-section">
              <h4 className="debug-section-title">
                <Icons.Database size={14} className="text-emerald-400" />
                <span>Collected Variables</span>
              </h4>
              <div className="debug-code-box">
                <pre>{JSON.stringify(simulator.collectedData, null, 2)}</pre>
              </div>
            </div>

            <div className="debug-panel-section">
              <h4 className="debug-section-title">
                <Icons.Activity size={14} className="text-amber-400" />
                <span>Simulated CRM Actions</span>
              </h4>
              <div className="debug-actions-list">
                {simulator.crmActions.length === 0 ? (
                  <p className="debug-empty-text">No CRM actions triggered yet.</p>
                ) : (
                  simulator.crmActions.map((act, idx) => (
                    <div key={idx} className="debug-action-item">
                      <Icons.Check size={12} className="text-emerald-400 mr-1.5" />
                      <span>{act}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
