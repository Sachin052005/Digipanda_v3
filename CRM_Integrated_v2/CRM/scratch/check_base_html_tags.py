from html.parser import HTMLParser
import re

file_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/templates/base.html'
with open(file_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Strip Django template tags {% ... %} and {{ ... }}
clean_html = re.sub(r'\{%.*?%\}', '', html, flags=re.DOTALL)
clean_html = re.sub(r'\{\{.*?\}\}', '', clean_html, flags=re.DOTALL)

class TagStackChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() not in self.void_tags:
            self.stack.append((tag.lower(), self.getpos(), dict(attrs).get('id', '')))

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in self.void_tags:
            return
        if not self.stack:
            self.errors.append(f"Unexpected closing tag </{t}> at line {self.getpos()[0]}")
            return
        top, pos, top_id = self.stack[-1]
        if top == t:
            self.stack.pop()
        else:
            # Look back in stack
            found = False
            for i in range(len(self.stack)-1, -1, -1):
                if self.stack[i][0] == t:
                    found = True
                    # Everything above it was unclosed
                    for j in range(len(self.stack)-1, i, -1):
                        self.errors.append(f"Unclosed tag <{self.stack[j][0]} id='{self.stack[j][2]}'> from line {self.stack[j][1][0]} when closing </{t}> at line {self.getpos()[0]}")
                    self.stack = self.stack[:i]
                    break
            if not found:
                self.errors.append(f"Spurious closing tag </{t}> at line {self.getpos()[0]} (top was <{top} id='{top_id}'> from line {pos[0]})")

parser = TagStackChecker()
parser.feed(clean_html)
print(f"Total remaining unclosed tags: {len(parser.stack)}")
for item in parser.stack[-10:]:
    print(f"  - <{item[0]} id='{item[2]}'> opened at line {item[1][0]}")
print(f"\nErrors reported: {len(parser.errors)}")
for err in parser.errors[:10]:
    print(f"  ! {err}")
