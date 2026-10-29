path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\chat\static\chat\js\flow_builder.js'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update choicesHtml for list node
target_1 = """        } else if (node.type === 'list' && Array.isArray(node.sections)) {
            const allRows = [];
            node.sections.forEach(s => (s.rows || []).forEach(r => allRows.push(r.title)));
            choicesHtml = `<div class="node-choices-preview">` +
                allRows.slice(0, 3).map(r => `
                    <div class="choice-chip">
                        <span>📋 ${escapeHtml(r)}</span>
                    </div>
                `).join('') +
                (allRows.length > 3 ? `<div class="choice-chip"><span>+ ${allRows.length - 3} more...</span></div>` : '') +
                `</div>`;
        }"""

repl_1 = """        } else if (node.type === 'list' && Array.isArray(node.sections)) {
            const allRows = [];
            node.sections.forEach(s => (s.rows || []).forEach(r => allRows.push(r)));
            if (allRows.length > 0) {
                choicesHtml = `<div class="node-choices-preview">` +
                    allRows.map((r, rIdx) => {
                        const targetId = r.next_node_id || getNodeTargetId(node.id, r.id || `row_${rIdx + 1}`) || (node.next_node_id || '');
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
        }"""

# 2. Update ports generation for list node
target_2 = """        } else if (node.type === 'buttons' && Array.isArray(node.options) && node.options.length > 0) {
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
        } else if (node.type !== 'end' && node.type !== 'human_handover') {"""

repl_2 = """        } else if (node.type === 'buttons' && Array.isArray(node.options) && node.options.length > 0) {
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
        } else if (node.type !== 'end' && node.type !== 'human_handover') {"""

# 3. Update addConnection for list node
target_3 = """            } else if (sourceNode.type === 'buttons' && Array.isArray(sourceNode.options)) {
                const opt = sourceNode.options.find(o => o.id === outPort);
                if (opt) opt.next_node_id = targetId;
            } else {
                sourceNode.next_node_id = targetId;
            }"""

repl_3 = """            } else if (sourceNode.type === 'buttons' && Array.isArray(sourceNode.options)) {
                const opt = sourceNode.options.find(o => o.id === outPort);
                if (opt) opt.next_node_id = targetId;
            } else if (sourceNode.type === 'list' && Array.isArray(sourceNode.sections)) {
                const row = (sourceNode.sections[0]?.rows || []).find(r => r.id === outPort);
                if (row) row.next_node_id = targetId;
                else sourceNode.next_node_id = targetId;
            } else {
                sourceNode.next_node_id = targetId;
            }"""

# 4. Update deleteEdge for list node
target_4 = """            } else if (sourceNode.type === 'buttons' && Array.isArray(sourceNode.options)) {
                const opt = sourceNode.options.find(o => o.id === removedConn.source_output);
                if (opt) opt.next_node_id = null;
            } else {
                if (sourceNode.next_node_id === removedConn.target) {
                    sourceNode.next_node_id = null;
                }
            }"""

repl_4 = """            } else if (sourceNode.type === 'buttons' && Array.isArray(sourceNode.options)) {
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
            }"""

# 5. Update drawConnectionLines for list node
target_5 = """                } else if (source.type === 'buttons' && Array.isArray(source.options)) {
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
                } else if (source.next_node_id && nodeMap[source.next_node_id]) {"""

repl_5 = """                } else if (source.type === 'buttons' && Array.isArray(source.options)) {
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
                } else if (source.next_node_id && nodeMap[source.next_node_id]) {"""

# 6. Update renderListRowsEditor with 24-character limit
target_6 = """    function renderListRowsEditor(sections) {
        elements.listRowsContainer.innerHTML = '';
        if (sections.length === 0) sections.push({ title: 'Available Programs', rows: [] });

        const section = sections[0];
        const rows = section.rows || [];

        rows.forEach((rowItem, idx) => {
            const rowEl = document.createElement('div');
            rowEl.className = 'inspector-option-row';
            rowEl.innerHTML = `
                <div class="option-row-inputs">
                    <input type="text" class="form-control list-title-input" placeholder="Course Title" value="${escapeHtml(rowItem.title)}">
                    <button type="button" class="option-remove-btn" title="Remove" data-idx="${idx}">&times;</button>
                </div>
                <input type="text" class="form-control list-desc-input" placeholder="Short description" value="${escapeHtml(rowItem.description || '')}" style="font-size: 11px;">
            `;

            rowEl.querySelector('.option-remove-btn').addEventListener('click', () => {
                rows.splice(idx, 1);
                renderListRowsEditor(sections);
            });

            elements.listRowsContainer.appendChild(rowEl);
        });
    }"""

repl_6 = """    function renderListRowsEditor(sections) {
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
    }"""

text_norm = text.replace('\r\n', '\n')
for i, (t, r) in enumerate([(target_1, repl_1), (target_2, repl_2), (target_3, repl_3), (target_4, repl_4), (target_5, repl_5), (target_6, repl_6)], 1):
    t_norm = t.replace('\r\n', '\n')
    assert t_norm in text_norm, f"Target {i} not found"
    text_norm = text_norm.replace(t_norm, r.replace('\r\n', '\n'), 1)

with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(text_norm)

print("Successfully updated flow_builder.js")
