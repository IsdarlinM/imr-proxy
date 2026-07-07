from urllib.parse import parse_qsl, urlparse
from imr_proxy.models.finding import Finding
from . import references as ref
SENS=["token","access_token","refresh_token","id_token","session","sid","password","passwd","api_key","apikey","secret","key","reset"]
REDIRS={"next","url","redirect","redirect_uri","return","return_to","continue","target"}
def analyze(flow):
    out=[]; p=urlparse(flow.request.url)
    for k,v in parse_qsl(p.query, keep_blank_values=True):
        lk=k.lower()
        if any(x in lk for x in SENS): out.append(Finding(id="URL-SENSITIVE-PARAM",title="Sensitive parameter in URL query string",severity="medium",confidence="medium",affected_ids=[flow.id],evidence=k,explanation="URLs are logged and sent as referrers.",impact="Secrets in URLs can leak.",remediation="Move secrets to headers or body and redact logs.",references=[ref.OWASP_ASVS,ref.RFC_9110],false_positive_notes="Parameter name is heuristic."))
        if lk in REDIRS and (v.startswith("http://") or v.startswith("https://") or v.startswith("//")): out.append(Finding(id="URL-OPEN-REDIRECT-INDICATOR",title="Open redirect indicator",severity="low",confidence="low",affected_ids=[flow.id],evidence=f"{k}={v[:120]}",explanation="Redirect-like absolute URL parameter observed.",impact="May become open redirect if unvalidated.",remediation="Allowlist redirect targets.",references=[ref.OWASP_WSTG]))
    return out
