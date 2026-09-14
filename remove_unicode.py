import sys
import re

file_path = "D:/StayPut/contracts/stayput.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace known unicode characters
replacements = {
    '—': '-',
    '→': '->',
    '≤': '<=',
    '–': '-',
    '”': '"',
    '“': '"',
    '’': "'",
    '‘': "'",
}

for k, v in replacements.items():
    content = content.replace(k, v)

# Fallback: remove any remaining non-ascii
content = re.sub(r'[^\x00-\x7F]+', '', content)

with open(file_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)

print("Done replacing non-ascii characters.")
