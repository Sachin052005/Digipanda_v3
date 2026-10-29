file_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/templates/base.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """        <span class="brand-wordmark-colored theme-light" style="font-size: 0.82rem;"><span class="part-digi">Digi</span><span class="part-p">p</span><span class="part-anda">anda</span><span class="part-crm">CRM</span></span>
      </div>
    </div>
  <!-- Dedicated Animated Logout Exit Overlay (Modern Glassmorphic UI) -->"""

replacement = """        <span class="brand-wordmark-colored theme-light" style="font-size: 0.82rem;"><span class="part-digi">Digi</span><span class="part-p">p</span><span class="part-anda">anda</span><span class="part-crm">CRM</span></span>
      </div>
    </div>
  </div>

  <!-- Dedicated Animated Logout Exit Overlay (Modern Glassmorphic UI) -->"""

if target in content:
    content = content.replace(target, replacement, 1)
    print("Found and replaced target with closing </div>")
else:
    # Try normalizing line breaks
    target_crlf = target.replace('\n', '\r\n')
    replacement_crlf = replacement.replace('\n', '\r\n')
    if target_crlf in content:
        content = content.replace(target_crlf, replacement_crlf, 1)
        print("Found and replaced CRLF target with closing </div>")
    else:
        print("Target not found!")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated base.html successfully.")
