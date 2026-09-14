import sys
import re

files = [
    "D:/StayPut/README.md",
    "D:/StayPut/AGENTS.md",
    "D:/StayPut/AGENT_LOG.md",
]

replacements = {
    '—': '-',
    '→': '->',
    '≤': '<=',
    '–': '-',
    '”': '"',
    '“': '"',
    '’': "'",
    '‘': "'",
    '≠': '!=',
}

for file_path in files:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    for k, v in replacements.items():
        content = content.replace(k, v)

    with open(file_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

print("Done replacing non-ascii characters in docs.")
