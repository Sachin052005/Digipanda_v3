import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MiniMap,
  BackgroundVariant,
  Connection,
  Edge,
  Node,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { Header } from './components/Header';
import { NodePalette } from './components/NodePalette';
import { InspectorDrawer } from './components/InspectorDrawer';
import { SimulatorModal } from './components/SimulatorModal';
import { nodeTypes } from './nodes/CustomNodes';
import { DeletableEdge } from './components/DeletableEdge';
import { PALETTE_NODES } from './constants';
import {
  FlowDefinition,
  FlowVersion,
  BusinessLineOption,
  BranchOption,
  FlowNodeData,
  SimulatorState,
  FlowNodeType,
} from './types';

// Helper to get CSRF token
function getCookie(name: string): string {
  let cookieValue = '';
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + '=') {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

const DEFAULT_FLOW_FALLBACK: FlowDefinition = {
  id: 1,
  name: 'Admissions & Training Flow',
  slug: 'admissions-training-flow',
  version: 1,
  status: 'draft',
  trigger_type: 'first_message',
  trigger_keywords: 'hi, hello, menu, start',
  is_active: true,
  flow_data: {
    nodes: [
      {
        id: 'trigger_1',
        type: 'trigger',
        position: { x: 100, y: 150 },
        data: {
          title: 'WhatsApp Message Trigger',
          trigger_type: 'first_message',
        },
      },
      {
        id: 'msg_welcome',
        type: 'message',
        position: { x: 380, y: 150 },
        data: {
          title: 'Welcome Greeting',
          body: 'Hello {{customer_name}}! Welcome to DigiPanda Tech Academy.',
        },
      },
    ],
    edges: [
      {
        id: 'e_trig_msg',
        source: 'trigger_1',
        target: 'msg_welcome',
        sourceHandle: 'default',
        type: 'smoothstep',
        animated: true,
      },
    ],
  },
};

const edgeTypes = {
  default: DeletableEdge,
  smoothstep: DeletableEdge,
  deletable: DeletableEdge,
};

export const FlowBuilderApp: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<FlowNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const [flow, setFlow] = useState<FlowDefinition>(DEFAULT_FLOW_FALLBACK);
  const [versions, setVersions] = useState<FlowVersion[]>([]);
  const [businessLines, setBusinessLines] = useState<BusinessLineOption[]>([]);
  const [branches, setBranches] = useState<BranchOption[]>([]);
  const [selectedLine, setSelectedLine] = useState<number | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<number | null>(null);

  const [selectedNode, setSelectedNode] = useState<Node<FlowNodeData> | null>(null);
  const [isPaletteCollapsed, setIsPaletteCollapsed] = useState(false);


  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'unsaved'>('saved');
  const [isPublishing, setIsPublishing] = useState(false);
  const [isUnpublishing, setIsUnpublishing] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  const [history, setHistory] = useState<{ nodes: Node<FlowNodeData>[]; edges: Edge[] }[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  // Simulator State
  const [simulator, setSimulator] = useState<SimulatorState>({
    isOpen: false,
    currentNodeId: null,
    collectedData: {},
    messages: [],
    crmActions: [],
    waitingForInput: false,
    isComplete: false,
    isLoading: false,
  });

  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition, fitView } = useReactFlow();

  const showToast = (text: string, type: 'success' | 'error' | 'info' = 'success') => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleEdgeDoubleClick = useCallback((_event: React.MouseEvent, edge: Edge) => {
    setEdges((eds) => eds.filter((e) => e.id !== edge.id));
    setSaveStatus('unsaved');
    showToast('Connection line deleted', 'info');
  }, [setEdges]);

  // 1. Initial Flow Load
  useEffect(() => {
    const rootEl = document.getElementById('root') || document.getElementById('builderApp');
    const flowIdFromDom = (window as any).__INITIAL_FLOW_ID__ || rootEl?.getAttribute('data-flow-id');
    const urlParams = new URLSearchParams(window.location.search);
    const flowId = flowIdFromDom || urlParams.get('id') || '';

    loadInitialData(flowId);
  }, []);

  const loadInitialData = async (flowId: string) => {
    try {
      let targetId = flowId;
      let flowRes = targetId ? await fetch(`/api/flows/${targetId}/`) : null;

      // If flow was not found (404) or missing, fallback to first available flow from list
      if (!flowRes || flowRes.status === 404) {
        const listRes = await fetch('/api/flows/');
        if (listRes.ok) {
          const allFlows = await listRes.json();
          const flowList = Array.isArray(allFlows) ? allFlows : allFlows.results || [];
          if (flowList.length > 0) {
            targetId = String(flowList[0].id);
            flowRes = await fetch(`/api/flows/${targetId}/`);
          }
        }
      }

      // 1. Process Flow Details
      if (flowRes && flowRes.ok) {
        const flowData: FlowDefinition = await flowRes.json();
        setFlow(flowData);
        setSelectedLine(flowData.business_account || null);

        const graph = flowData.flow_data || {};
        const initialNodes: Node<FlowNodeData>[] = (graph.nodes || []).map((n: any, idx: number) => ({
          id: n.id,
          type: n.type || 'message',
          position: n.position || { x: 100 + (idx % 4) * 260, y: 100 + Math.floor(idx / 4) * 180 },
          data: { ...n.data, ...n, type: n.type },
        }));

        const initialEdges: Edge[] = (graph.edges || graph.connections || []).map((e: any, idx: number) => ({
          id: e.id || `e_${idx}`,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle || e.source_output || 'default',
          type: 'deletable',
          animated: true,
          style: { strokeWidth: 2, stroke: '#64748b' },
        }));

        setNodes(initialNodes);
        setEdges(initialEdges);
        setTimeout(() => fitView({ padding: 0.2 }), 200);

        // 2. Fetch Versions for targetId
        const verRes = await fetch(`/api/flows/${targetId}/versions/`);
        if (verRes.ok) {
          const vList = await verRes.json();
          setVersions(Array.isArray(vList) ? vList : []);
        }
      } else {
        // Fallback
        setNodes(DEFAULT_FLOW_FALLBACK.flow_data.nodes);
        setEdges(DEFAULT_FLOW_FALLBACK.flow_data.edges || []);
      }

      // 3. Fetch Lines & Branches
      let linesRes = await fetch('/api/business-accounts/');
      if (!linesRes.ok) {
        linesRes = await fetch('/api/whatsapp/business-accounts/');
      }
      if (linesRes.ok) {
        const linesData = await linesRes.json();
        setBusinessLines(Array.isArray(linesData) ? linesData : linesData.results || []);
      }

      const branchRes = await fetch('/api/branches/');
      if (branchRes.ok) {
        const branchData = await branchRes.json();
        setBranches(Array.isArray(branchData) ? branchData : branchData.results || []);
      }
    } catch (err) {
      console.error('Failed to load initial flow data:', err);
      // Fallback
      setNodes(DEFAULT_FLOW_FALLBACK.flow_data.nodes);
      setEdges(DEFAULT_FLOW_FALLBACK.flow_data.edges || []);
    }
  };

  // Connect Edges
  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            type: 'deletable',
            animated: true,
            style: { strokeWidth: 2, stroke: '#10b981' },
          },
          eds
        )
      );
      setSaveStatus('unsaved');
    },
    [setEdges]
  );

  // Drag & Drop Nodes from Palette
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData('application/reactflow/type') as FlowNodeType;
      if (!nodeType) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      addNodeAtPosition(nodeType, position);
    },
    [screenToFlowPosition]
  );

  const addNodeAtPosition = (nodeType: FlowNodeType, position: { x: number; y: number }) => {
    const def = PALETTE_NODES.find((p) => p.type === nodeType) || PALETTE_NODES[1];
    const newNodeId = `${nodeType}_${Date.now().toString().slice(-6)}`;

    const newNode: Node<FlowNodeData> = {
      id: newNodeId,
      type: nodeType,
      position,
      data: {
        ...def.defaultData,
        type: nodeType,
        title: def.label,
      },
    };

    setNodes((nds) => nds.concat(newNode));
    setSelectedNode(newNode);
    setSaveStatus('unsaved');
    showToast(`Added ${def.label}`, 'info');
  };

  // Add from palette button (center of canvas)
  const handleAddNodeFromPalette = (type: FlowNodeType) => {
    const centerPos = {
      x: 300 + Math.random() * 80,
      y: 200 + Math.random() * 80,
    };
    addNodeAtPosition(type, centerPos);
  };

  // Selection
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node as Node<FlowNodeData>);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Update Node Data from Inspector
  const handleUpdateNodeData = (nodeId: string, newData: Partial<FlowNodeData>) => {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === nodeId) {
          const updated = {
            ...n,
            data: { ...n.data, ...newData },
          };
          if (selectedNode?.id === nodeId) {
            setSelectedNode(updated);
          }
          return updated;
        }
        return n;
      })
    );
    setSaveStatus('unsaved');
  };

  // Delete Node
  const handleDeleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    if (selectedNode?.id === nodeId) {
      setSelectedNode(null);
    }
    setSaveStatus('unsaved');
    showToast('Step deleted', 'info');
  };

  // Save Draft (Ctrl+S)
  const handleSaveDraft = async () => {
    setSaveStatus('saving');
    const csrfToken = getCookie('csrftoken');

    const isPublished = flow.status === 'published';
    const payload = {
      name: flow.name,
      business_account: selectedLine,
      auto_fork_draft: isPublished,
      flow_data: {
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position,
          data: n.data,
          ...n.data,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle || 'default',
        })),
      },
    };

    try {
      const res = await fetch(`/api/flows/${flow.id}/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const saved: FlowDefinition = await res.json();
        setFlow(saved);
        setSaveStatus('saved');
        if (saved.id && saved.id !== flow.id) {
          const newUrl = `${window.location.pathname}?id=${saved.id}`;
          window.history.replaceState({ path: newUrl }, '', newUrl);
          showToast(`Working draft v${saved.version} created and saved!`);
        } else {
          showToast('Draft workflow saved successfully!');
        }
      } else {
        const err = await res.json().catch(() => ({}));
        if (err.code === 'PUBLISHED_IMMUTABLE') {
          await handleAutoForkDraft();
        } else {
          setSaveStatus('unsaved');
          let errorMsg = err.error || err.detail;
          if (!errorMsg && typeof err === 'object') {
            const fieldErrors = Object.entries(err)
              .map(([field, msg]) => `${field}: ${Array.isArray(msg) ? msg.join(', ') : msg}`)
              .join('; ');
            if (fieldErrors) errorMsg = `Validation error: ${fieldErrors}`;
          }
          showToast(errorMsg || 'Failed to save draft.', 'error');
        }
      }
    } catch (err: any) {
      setSaveStatus('unsaved');
      showToast('Error saving flow: ' + err.message, 'error');
    }
  };

  // Auto fork draft when editing published flow
  const handleAutoForkDraft = async () => {
    const csrfToken = getCookie('csrftoken');
    try {
      const payload = {
        name: flow.name,
        business_account: selectedLine,
        flow_data: {
          nodes: nodes.map((n) => ({
            id: n.id,
            type: n.type,
            position: n.position,
            data: n.data,
            ...n.data,
          })),
          edges: edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            sourceHandle: e.sourceHandle || 'default',
          })),
        },
      };

      const res = await fetch(`/api/flows/${flow.id}/create-draft/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const newDraft = await res.json();
        const created = newDraft.flow || newDraft;
        setFlow(created);
        setSaveStatus('saved');
        const newUrl = `${window.location.pathname}?id=${created.id}`;
        window.history.replaceState({ path: newUrl }, '', newUrl);
        showToast(`Created new working draft Version ${created.version || (flow.version + 1)}`);
      } else {
        setSaveStatus('unsaved');
        showToast('Failed to create draft version', 'error');
      }
    } catch (e: any) {
      setSaveStatus('unsaved');
      showToast('Failed to create draft version: ' + e.message, 'error');
    }
  };

  // Publish Flow
  const handlePublish = async () => {
    setIsPublishing(true);
    const csrfToken = getCookie('csrftoken');

    try {
      // First save current canvas
      await handleSaveDraft();

      const res = await fetch(`/api/flows/${flow.id}/publish/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
      });

      const data = await res.json();
      if (res.ok && data.valid) {
        setFlow(data.flow || { ...flow, status: 'published', version: flow.version + 1 });
        showToast(data.message || 'Workflow published to live WhatsApp successfully!');
      } else {
        showToast(data.error || (data.errors && data.errors.join(', ')) || 'Validation failed.', 'error');
      }
    } catch (err: any) {
      showToast('Failed to publish: ' + err.message, 'error');
    } finally {
      setIsPublishing(false);
    }
  };

  // Unpublish / Pause Flow
  const handleUnpublish = async () => {
    setIsUnpublishing(true);
    const csrfToken = getCookie('csrftoken');

    try {
      const res = await fetch(`/api/flows/${flow.id}/unpublish/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
      });

      const data = await res.json();
      if (res.ok) {
        setFlow(data.flow || { ...flow, status: 'draft' });
        showToast(data.message || 'Workflow paused and returned to draft status.');
      } else {
        showToast(data.error || 'Failed to pause workflow.', 'error');
      }
    } catch (err: any) {
      showToast('Failed to unpublish: ' + err.message, 'error');
    } finally {
      setIsUnpublishing(false);
    }
  };

  // Validate Graph
  const handleValidate = async () => {
    setIsValidating(true);
    const csrfToken = getCookie('csrftoken');

    const flowDataPayload = {
      nodes: nodes.map((n) => ({ id: n.id, type: n.type, data: n.data, ...n.data })),
      edges: edges.map((e) => ({ source: e.source, target: e.target, sourceHandle: e.sourceHandle })),
    };

    try {
      const res = await fetch('/api/flows/validate/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ flow_data: flowDataPayload }),
      });
      const data = await res.json();

      if (data.valid) {
        showToast('✓ Graph topology is valid! All steps properly connected.');
      } else {
        const issues = (data.errors || []).join(' • ');
        showToast(`Issues detected: ${issues}`, 'error');
      }
    } catch (err: any) {
      showToast('Validation request failed: ' + err.message, 'error');
    } finally {
      setIsValidating(false);
    }
  };

  // Restore Prior Version
  const handleRestoreVersion = async (versionId: number) => {
    const csrfToken = getCookie('csrftoken');
    try {
      const res = await fetch(`/api/flows/${versionId}/restore-version/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
      });
      if (res.ok) {
        const restored = await res.json();
        showToast('Restored historical version as new draft!');
        loadInitialData(String(restored.flow?.id || flow.id));
      }
    } catch (e: any) {
      showToast('Failed to restore version: ' + e.message, 'error');
    }
  };

  // Simulator Execution
  const handleOpenSimulator = () => {
    setSimulator({
      isOpen: true,
      currentNodeId: null,
      collectedData: {},
      messages: [],
      crmActions: [],
      waitingForInput: false,
      isComplete: false,
      isLoading: false,
    });
    // Trigger initial start
    handleSimulatorStep('hi', undefined, true);
  };

  const handleSimulatorStep = async (
    text: string,
    interactiveReply?: string,
    isInitial: boolean = false
  ) => {
    const userMsg = !isInitial ? {
      type: 'user_reply',
      sender: 'user' as const,
      body: text,
    } : null;

    setSimulator((prev) => ({
      ...prev,
      isLoading: true,
      messages: userMsg ? [...prev.messages, userMsg] : prev.messages,
    }));
    const csrfToken = getCookie('csrftoken');

    const flowDataPayload = {
      nodes: nodes.map((n) => ({ id: n.id, type: n.type, data: n.data, ...n.data })),
      edges: edges.map((e) => ({ source: e.source, target: e.target, sourceHandle: e.sourceHandle })),
    };

    try {
      const res = await fetch('/api/flows/simulate/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
          flow_data: flowDataPayload,
          current_node_id: isInitial ? null : simulator.currentNodeId,
          message_text: text,
          collected_data: simulator.collectedData,
          interactive_reply: interactiveReply,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setSimulator((prev) => ({
          ...prev,
          currentNodeId: data.current_node_id,
          waitingForInput: data.waiting_for_input,
          isComplete: data.is_complete,
          collectedData: data.collected_data || prev.collectedData,
          messages: [...prev.messages, ...(data.sim_messages || [])],
          crmActions: [...prev.crmActions, ...(data.crm_actions || [])],
          isLoading: false,
        }));
      } else {
        showToast(data.error || 'Simulation error', 'error');
        setSimulator((prev) => ({ ...prev, isLoading: false }));
      }
    } catch (e: any) {
      showToast('Simulator request failed: ' + e.message, 'error');
      setSimulator((prev) => ({ ...prev, isLoading: false }));
    }
  };

  // Keyboard Shortcuts (Ctrl+S)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSaveDraft();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nodes, edges, flow]);

  return (
    <div className="builder-app" id="builderApp" data-flow-id={flow.id}>
      {/* Top Navigation */}
      <Header
        flow={flow}
        versions={versions}
        businessLines={businessLines}
        branches={branches}
        selectedLine={selectedLine}
        selectedBranch={selectedBranch}
        saveStatus={saveStatus}
        isPublishing={isPublishing}
        isUnpublishing={isUnpublishing}
        isValidating={isValidating}
        onUnpublish={handleUnpublish}
        onUpdateFlowName={(name) => {
          setFlow((prev) => ({ ...prev, name }));
          setSaveStatus('unsaved');
        }}
        onSelectBusinessLine={(lineId) => {
          setSelectedLine(lineId);
          setSaveStatus('unsaved');
        }}
        onSelectBranch={(branchId) => {
          setSelectedBranch(branchId);
          setSaveStatus('unsaved');
        }}
        onSaveDraft={handleSaveDraft}
        onPublish={handlePublish}
        onValidate={handleValidate}
        onOpenSimulator={handleOpenSimulator}
        onRestoreVersion={handleRestoreVersion}
        canUndo={historyIndex > 0}
        canRedo={historyIndex < history.length - 1}
        onUndo={() => {}}
        onRedo={() => {}}
      />

      {/* Main Workspace Area (Palette + Canvas + Inspector) */}
      <div className="builder-main" ref={reactFlowWrapper}>
        {/* Left Draggable Palette */}
        <NodePalette
          onAddNode={handleAddNodeFromPalette}
          isCollapsed={isPaletteCollapsed}
          onToggleCollapse={() => setIsPaletteCollapsed(!isPaletteCollapsed)}
        />

        {/* Center Visual Flow Canvas */}
        <div className="builder-canvas-container" onDragOver={onDragOver} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onEdgeDoubleClick={handleEdgeDoubleClick}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            proOptions={{ hideAttribution: true }}
            snapToGrid
            snapGrid={[15, 15]}
            defaultEdgeOptions={{
              type: 'deletable',
              animated: true,
              interactionWidth: 30,
            }}
          >
            <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#334155" />
            <Controls position="bottom-left" showInteractive={false} />
            <MiniMap
              position="bottom-right"
              nodeColor="#1e293b"
              maskColor="rgba(15, 23, 42, 0.75)"
              className="builder-minimap"
            />
          </ReactFlow>
        </div>

        {/* Right Inspector Drawer */}
        {selectedNode && (
          <InspectorDrawer
            node={selectedNode}
            onUpdateNodeData={handleUpdateNodeData}
            onDeleteNode={handleDeleteNode}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>

      {/* Mobile Simulator Modal */}
      <SimulatorModal
        simulator={simulator}
        onSendMessage={(text, interactiveReply) => handleSimulatorStep(text, interactiveReply, false)}
        onReset={handleOpenSimulator}
        onClose={() => setSimulator((prev) => ({ ...prev, isOpen: false }))}
      />

      {/* Toast Notification */}
      {toastMessage && (
        <div className={`builder-toast toast-${toastMessage.type}`}>
          <span>{toastMessage.text}</span>
        </div>
      )}
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ReactFlowProvider>
      <FlowBuilderApp />
    </ReactFlowProvider>
  );
};

export default App;
