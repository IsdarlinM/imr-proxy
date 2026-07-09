from imr_proxy.models.finding import Finding
from . import references as ref
def analyze(flow):
    if not flow.response: return []
    h={k.lower():v for k,v in flow.response.headers.items()}; out=[]; acao=h.get("access-control-allow-origin",""); acac=h.get("access-control-allow-credentials","")
    if acao=="*": out.append(Finding(id="CORS-WILDCARD-ORIGIN",title="Wildcard CORS origin",severity="low",confidence="high",affected_ids=[flow.id],evidence="Access-Control-Allow-Origin: *",explanation="Wildcard CORS allows any origin to read non-credentialed responses.",impact="Risky for sensitive browser APIs.",remediation="Use a trusted origin allowlist.",references=[ref.OWASP_CORS,ref.MDN_HEADERS],false_positive_notes="Public resources may intentionally use wildcard."))
    if acac.lower()=="true" and acao in {"","*","null"}: out.append(Finding(id="CORS-CREDENTIALS-RISKY-ORIGIN",title="Risky credentialed CORS",severity="medium",confidence="medium",affected_ids=[flow.id],evidence=f"ACAO={acao or '[missing]'} ACAC={acac}",explanation="Credentialed CORS requires careful origin validation.",impact="May permit cross-origin reads if server behavior is flawed.",remediation="Reflect only trusted origins and add Vary: Origin.",references=[ref.OWASP_CORS]))
    return out
