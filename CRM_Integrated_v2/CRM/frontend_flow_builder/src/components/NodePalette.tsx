import React, { useState } from 'react';
import * as LucideIcons from 'lucide-react';
import { PALETTE_NODES, PaletteNodeDef } from '../constants';
import { FlowNodeType } from '../types';

interface NodePaletteProps {
  onAddNode: (type: FlowNodeType) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

const renderIcon = (iconName: string, color: string) => {
  const IconComponent = (LucideIcons as any)[iconName] || LucideIcons.Activity;
  return <IconComponent size={16} color={color} strokeWidth={2.2} />;
};

export const NodePalette: React.FC<NodePaletteProps> = ({
  onAddNode,
  isCollapsed,
  onToggleCollapse,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [collapsedCategories, setCollapsedCategories] = useState<Record<string, boolean>>({});

  const categories = ['Triggers', 'Messages', 'Logic', 'CRM', 'Integrations'] as const;

  const toggleCategory = (cat: string) => {
    setCollapsedCategories((prev) => ({
      ...prev,
      [cat]: !prev[cat],
    }));
  };

  const onDragStart = (event: React.DragEvent, nodeType: FlowNodeType) => {
    event.dataTransfer.setData('application/reactflow/type', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  const filteredNodes = PALETTE_NODES.filter(
    (n) =>
      n.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
      n.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside className={`builder-palette ${isCollapsed ? 'is-collapsed' : ''}`}>
      {/* Palette Header */}
      <div className="palette-header">
        <div className="palette-header-title">
          <LucideIcons.Layers size={16} className="text-emerald-400" />
          <span>Nodes Palette</span>
        </div>
        <button
          type="button"
          onClick={onToggleCollapse}
          className="palette-collapse-toggle"
          title={isCollapsed ? 'Expand Palette' : 'Collapse Palette'}
        >
          {isCollapsed ? <LucideIcons.ChevronRight size={16} /> : <LucideIcons.ChevronLeft size={16} />}
        </button>
      </div>

      {!isCollapsed && (
        <>
          {/* Search Bar */}
          <div className="palette-search-wrap">
            <LucideIcons.Search size={14} className="palette-search-icon" />
            <input
              type="text"
              placeholder="Search steps (e.g. Buttons, Webhook)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="palette-search-input"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm('')}
                className="palette-search-clear"
              >
                ✕
              </button>
            )}
          </div>

          {/* Node Categories List */}
          <div className="palette-categories-scroll">
            {categories.map((category) => {
              const nodesInCat = filteredNodes.filter((n) => n.category === category);
              if (nodesInCat.length === 0) return null;

              const isCatCollapsed = collapsedCategories[category];

              return (
                <div key={category} className="palette-category-group">
                  <button
                    type="button"
                    className="palette-category-header"
                    onClick={() => toggleCategory(category)}
                  >
                    <span>{category}</span>
                    <span className="cat-count-pill">{nodesInCat.length}</span>
                    {isCatCollapsed ? (
                      <LucideIcons.ChevronRight size={12} className="cat-chevron" />
                    ) : (
                      <LucideIcons.ChevronDown size={12} className="cat-chevron" />
                    )}
                  </button>

                  {!isCatCollapsed && (
                    <div className="palette-items-list">
                      {nodesInCat.map((item) => (
                        <div
                          key={item.type}
                          className="palette-node-item"
                          draggable
                          onDragStart={(e) => onDragStart(e, item.type)}
                          onClick={() => onAddNode(item.type)}
                          title={`Drag onto canvas or click to add ${item.label}`}
                        >
                          <div
                            className="palette-item-icon"
                            style={{ backgroundColor: `${item.accentColor}18` }}
                          >
                            {renderIcon(item.iconName, item.accentColor)}
                          </div>
                          <div className="palette-item-info">
                            <h5 className="palette-item-title">{item.label}</h5>
                            <p className="palette-item-desc">{item.description}</p>
                          </div>
                          <button
                            type="button"
                            className="palette-item-add-btn"
                            title="Add node to canvas"
                            onClick={(e) => {
                              e.stopPropagation();
                              onAddNode(item.type);
                            }}
                          >
                            <LucideIcons.Plus size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </aside>
  );
};
