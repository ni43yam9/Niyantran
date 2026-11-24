import os
import re

log_patterns = [
    re.compile(r'logger\.\w+\(.*?(password|token|secret).*?\)', re.IGNORECASE),
    re.compile(r'print\(.*?(password|token|secret).*?\)', re.IGNORECASE)
]

suspicious = []
for root, dirs, files in os.walk('backend/app'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8') as fp:
                for idx, line in enumerate(fp, 1):
                    for pat in log_patterns:
                        if pat.search(line):
                            # Exclude benign mentions like "token expired", "token payload"
                            if not any(b in line for b in ["token has expired", "Invalid authentication token", "token is missing"]):
                                suspicious.append((path, idx, line.strip()))

print(f"Total logging warnings: {len(suspicious)}")
for s in suspicious:
    print(" ", s)
