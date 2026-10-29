path_html = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\chat\templates\chat\flow_builder.html'
with open(path_html, 'r', encoding='utf-8') as f:
    text_html = f.read()

target_html = """                        <!-- Sections & Rows for Interactive List -->
                        <div class="form-group" id="groupListRows" style="display: none;">
                            <label for="editListSource" class="form-label">Course List Source</label>
                            <select id="editListSource" class="form-control" style="margin-bottom: 10px;">
                                <option value="database">Dynamic from Courses (Database)</option>
                                <option value="custom">Manual Options</option>
                            </select>

                            <div class="source-info-pill" id="dbCourseInfoPill">
                                <span>✓ Automatically syncs active courses (up to 10)</span>
                            </div>

                            <div id="customListRowsContainer" style="display: none;">
                                <div class="group-header-row">
                                    <label class="form-label">Course Options</label>
                                    <button type="button" class="btn-sm-action" id="btnAddListRowBtn">+ Add Course</button>
                                </div>
                                <div class="list-rows-container" id="listRowsContainer"></div>
                            </div>
                        </div>"""

repl_html = """                        <!-- Sections & Rows for Interactive List -->
                        <div class="form-group" id="groupListRows" style="display: none;">
                            <label for="editListSource" class="form-label">Menu List Source</label>
                            <select id="editListSource" class="form-control" style="margin-bottom: 10px;">
                                <option value="custom">Manual Menu Options (Up to 10 choices)</option>
                                <option value="database">Dynamic from Courses (Database)</option>
                            </select>

                            <div class="source-info-pill" id="dbCourseInfoPill">
                                <span>✓ Automatically syncs active courses (up to 10)</span>
                            </div>

                            <div id="customListRowsContainer" style="display: none;">
                                <div class="group-header-row">
                                    <label class="form-label">Menu Options <span style="font-size: 0.75rem; color: var(--text-muted); font-weight: 400;">(Max 24 chars each)</span></label>
                                    <button type="button" class="btn-sm-action" id="btnAddListRowBtn">+ Add Option</button>
                                </div>
                                <div class="list-rows-container" id="listRowsContainer"></div>
                            </div>
                        </div>"""

text_html_norm = text_html.replace('\r\n', '\n')
target_html_norm = target_html.replace('\r\n', '\n')
assert target_html_norm in text_html_norm, "Target HTML not found"
text_html_norm = text_html_norm.replace(target_html_norm, repl_html.replace('\r\n', '\n'), 1)

with open(path_html, 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(text_html_norm)

print("Successfully updated flow_builder.html")
