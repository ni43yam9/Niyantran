import os
import re

suspicious = []
secret_patterns = [
    re.compile(r'(?i)(secret_key|jwt_secret)\s*[:=]\s*[\'\"][^\'\"]+[\'\"]'),
    re.compile(r'-----BEGIN (RSA )?PRIVATE KEY-----')
]

for root, dirs, files in os.walk('src'):
    for f in files:
        if f.endswith(('.js', '.jsx', '.ts', '.tsx', '.json', '.html')):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                for idx, line in enumerate(fp, 1):
                    for pat in secret_patterns:
                        if pat.search(line):
                            if not any(ign in line.lower() for ign in ['type="password"', 'placeholder', 'input type']):
                                suspicious.append((path, idx, line.strip()[:80]))

print(f"Total suspicious patterns found in src/: {len(suspicious)}")
for s in suspicious:
    print(" ", s)
