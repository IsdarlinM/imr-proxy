from imr_proxy.models.finding import Finding
from . import references as ref
def analyze(flow):
    if not flow.response: return []
    loc=flow.response.headers.get("Location") or flow.response.headers.get("location"); status=flow.response.status_code or 0; out=[]
    if status in {301,302,303,307,308} and loc:
        if flow.request.scheme=="https" and loc.lower().startswith("http://"): out.append(Finding(id="REDIRECT-HTTPS-DOWNGRADE",title="HTTPS redirects to HTTP",severity="medium",confidence="high",affected_ids=[flow.id],evidence=f"{status} Location: {loc}",explanation="Downgrade redirects weaken transport security.",impact="Sensitive data may continue over HTTP.",remediation="Redirect only to HTTPS.",references=[ref.OWASP_ASVS,ref.MDN_HEADERS]))
        if loc.startswith("//"): out.append(Finding(id="REDIRECT-SCHEME-RELATIVE",title="Scheme-relative redirect",severity="info",confidence="medium",affected_ids=[flow.id],evidence=loc,explanation="Scheme-relative redirect observed.",impact="May create mixed redirect behavior.",remediation="Prefer explicit HTTPS or relative paths.",references=[ref.RFC_9110]))
    return out
