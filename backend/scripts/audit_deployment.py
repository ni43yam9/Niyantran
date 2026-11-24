import requests
import json
import os
import subprocess
import sys

def audit_deployment():
    results = {}
    
    # 1. Test Backend Public HTTPS Endpoint
    backend_url = "https://06d355e21c47db.app.lhr.life"
    try:
        r = requests.get(f"{backend_url}/health", timeout=10)
        results["backend_public_https_root_health"] = {
            "status_code": r.status_code,
            "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text,
            "headers": dict(r.headers)
        }
    except Exception as e:
        results["backend_public_https_root_health"] = {"error": str(e)}

    try:
        r = requests.get(f"{backend_url}/api/v1/health", timeout=10)
        results["backend_public_https_api_health"] = {
            "status_code": r.status_code,
            "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
        }
    except Exception as e:
        results["backend_public_https_api_health"] = {"error": str(e)}

    # 2. Test Frontend Public HTTPS Endpoint
    frontend_url = "https://e5bdf14ae7259f.app.lhr.life"
    try:
        r = requests.get(f"{frontend_url}/", timeout=10)
        has_manifest = "manifest.json" in r.text
        has_viewport = "viewport-fit=cover" in r.text
        results["frontend_public_https"] = {
            "status_code": r.status_code,
            "has_manifest": has_manifest,
            "has_viewport": has_viewport
        }
    except Exception as e:
        results["frontend_public_https"] = {"error": str(e)}

    # 3. Test Frontend Proxy to Backend (/health and /api/v1/health)
    try:
        r = requests.get(f"{frontend_url}/health", timeout=10)
        results["frontend_proxy_health"] = {
            "status_code": r.status_code,
            "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:100]
        }
    except Exception as e:
        results["frontend_proxy_health"] = {"error": str(e)}

    # 4. Check Alembic Migration Status
    try:
        proc = subprocess.run(["alembic", "current"], capture_output=True, text=True, cwd="backend")
        results["alembic_current"] = proc.stdout.strip()
    except Exception as e:
        results["alembic_current"] = {"error": str(e)}

    # 5. Check CORS response on Backend
    try:
        headers = {
            "Origin": "https://e5bdf14ae7259f.app.lhr.life",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type"
        }
        r = requests.options(f"{backend_url}/api/v1/sync/pull", headers=headers, timeout=5)
        results["cors_options_preflight"] = {
            "status_code": r.status_code,
            "allow_origin": r.headers.get("access-control-allow-origin"),
            "allow_methods": r.headers.get("access-control-allow-methods"),
            "allow_headers": r.headers.get("access-control-allow-headers")
        }
    except Exception as e:
        results["cors_options_preflight"] = {"error": str(e)}

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    audit_deployment()
