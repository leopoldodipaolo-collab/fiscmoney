import sys
from html.parser import HTMLParser

class TagChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []
        self.self_closing = {
            'input', 'img', 'br', 'hr', 'meta', 'link', 'col', 'base', 'area', 'param'
        }

    def handle_starttag(self, tag, attrs):
        if tag not in self.self_closing:
            attr_dict = dict(attrs)
            elem_id = attr_dict.get('id', '')
            elem_cls = attr_dict.get('class', '')
            self.stack.append((tag, self.getpos(), elem_id, elem_cls))

    def handle_endtag(self, tag):
        if tag in self.self_closing:
            return
        if not self.stack:
            self.errors.append(f"Unexpected end tag </{tag}> at line {self.getpos()[0]}")
            return
        
        last_tag, pos, elem_id, elem_cls = self.stack[-1]
        if last_tag == tag:
            self.stack.pop()
        else:
            # Look up stack
            found = False
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    found = True
                    break
            if found:
                while self.stack and self.stack[-1][0] != tag:
                    unclosed, u_pos, u_id, u_cls = self.stack.pop()
                    self.errors.append(f"Unclosed tag <{unclosed} id='{u_id}' class='{u_cls}'> from line {u_pos[0]} closed by </{tag}> at line {self.getpos()[0]}")
                if self.stack:
                    self.stack.pop()
            else:
                self.errors.append(f"Unexpected end tag </{tag}> at line {self.getpos()[0]} (expected </{last_tag}> from line {pos[0]})")

with open('templates/transactions.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# Strip Jinja template tags roughly
import re
# replace {% ... %} with spaces
clean_html = re.sub(r'\{%.*?%\}', lambda m: ' ' * len(m.group(0)), html_content, flags=re.DOTALL)
# replace {{ ... }} with spaces
clean_html = re.sub(r'\{\{.*?\}\}', lambda m: ' ' * len(m.group(0)), clean_html, flags=re.DOTALL)

checker = TagChecker()
checker.feed(clean_html)

print("Errors found:", len(checker.errors))
for err in checker.errors:
    print(" ", err)

if checker.stack:
    print("Unclosed tags remaining on stack:", len(checker.stack))
    for tag, pos, elem_id, elem_cls in checker.stack:
        print(f"  <{tag} id='{elem_id}' class='{elem_cls}'> at line {pos[0]}")
