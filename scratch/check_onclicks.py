import re

with open('scratch/rendered_tx_auth.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Check for all onclick attributes
matches = re.findall(r'onclick=([\'"])(.*?)\1', content)
print(f"Total onclick handlers: {len(matches)}")

errors = []
for quote, val in matches:
    # Try basic JS validation
    # If quote is ", val shouldn't have raw unescaped "
    if '&#39;' in val or '&quot;' in val:
        errors.append(val)

print(f"Potentially problematic escaped onclicks: {len(errors)}")
if errors:
    print("Examples of escaped onclicks:")
    for e in errors[:5]:
        print("  -", e)
