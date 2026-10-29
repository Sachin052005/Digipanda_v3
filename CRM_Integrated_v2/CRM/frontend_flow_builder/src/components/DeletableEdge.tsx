import React, { useState } from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  EdgeProps,
  useReactFlow,
} from '@xyflow/react';

export const DeletableEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  selected,
}) => {
  const { setEdges } = useReactFlow();
  if (typeof sourceX !== 'number' || typeof targetX !== 'number' || isNaN(sourceX) || isNaN(targetX)) {
    return null;
  }
  const [isHovered, setIsHovered] = useState(false);

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 16,
  });

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEdges((edges) => edges.filter((edge) => edge.id !== id));
  };

  const showButton = selected || isHovered;

  const edgeStyle = {
    ...style,
    stroke: selected ? '#ef4444' : isHovered ? '#38bdf8' : (style.stroke || '#64748b'),
    strokeWidth: selected ? 3.5 : isHovered ? 2.5 : 2,
    transition: 'stroke 0.2s, stroke-width 0.2s',
  };

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={edgeStyle}
        interactionWidth={30}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
            zIndex: 1000,
          }}
          className="nodrag nopan"
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          {showButton ? (
            <button
              type="button"
              className="edge-delete-btn"
              onClick={handleDelete}
              title="Delete connection line"
            >
              ✕
            </button>
          ) : (
            /* Invisible hover hit-zone in the middle so hovering near the center pops up the delete button */
            <div
              style={{
                width: 24,
                height: 24,
                cursor: 'pointer',
              }}
              onClick={() => setIsHovered(true)}
            />
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

export default DeletableEdge;
