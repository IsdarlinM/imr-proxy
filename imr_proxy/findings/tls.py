from imr_proxy.models.finding import Finding
from . import references as ref
def analyze(flow):
    out=[]
    if flow.request.scheme!="https": return out
    if not flow.intercepted_tls: out.append(Finding(id="TLS-PASSTHROUGH",title="TLS passthrough mode observed",severity="info",confidence="high",affected_ids=[flow.id],evidence="not intercepted",explanation="Passthrough preserves end-to-end TLS.",impact="Application-layer TLS content is not visible.",remediation="Use --intercept-https only for authorized local testing.",references=[ref.MOZILLA_TLS]))
    tv=str(flow.tls_metadata.get("tls_version",""))
    if tv and any(x in tv for x in ["SSL","TLSv1.0","TLSv1.1"]): out.append(Finding(id="TLS-WEAK-VERSION-INDICATOR",title="Weak TLS version indicator",severity="medium",confidence="medium",affected_ids=[flow.id],evidence=tv,explanation="Legacy TLS detected.",impact="Protocol/compliance risk.",remediation="Use TLS 1.2+.",references=[ref.MOZILLA_TLS,ref.OWASP_ASVS]))
    return out
