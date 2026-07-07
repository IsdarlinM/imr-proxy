from imr_proxy.models.finding import Finding
from . import references as ref
def analyze(flow):
    out=[]
    if not flow.response: return out
    h={k.lower():v for k,v in flow.response.headers.items()}; fid=flow.id; ctype=h.get("content-type","")
    def f(id,title,sev,evi,rem,conf="medium"):
        out.append(Finding(id=id,title=title,severity=sev,confidence=conf,affected_ids=[fid],evidence=evi,explanation=title,impact="Defense-in-depth or exposure risk depending on context.",remediation=rem,references=[ref.OWASP_SECURE_HEADERS,ref.MDN_HEADERS],false_positive_notes="Validate context before escalating."))
    if flow.request.scheme=="https" and "strict-transport-security" not in h: f("HDR-MISSING-HSTS","Missing Strict-Transport-Security","low","HSTS missing","Add HSTS after HTTPS rollout.")
    if "text/html" in ctype and "content-security-policy" not in h: f("HDR-MISSING-CSP","Missing Content-Security-Policy","low","CSP missing","Deploy tested CSP, initially report-only.")
    if "x-content-type-options" not in h: f("HDR-MISSING-XCTO","Missing X-Content-Type-Options","info","XCTO missing","Add X-Content-Type-Options: nosniff.")
    if "referrer-policy" not in h: f("HDR-MISSING-REFERRER-POLICY","Missing Referrer-Policy","info","Referrer-Policy missing","Set strict-origin-when-cross-origin or stricter.")
    if "text/html" in ctype and "permissions-policy" not in h: f("HDR-MISSING-PERMISSIONS-POLICY","Missing Permissions-Policy","info","Permissions-Policy missing","Define least-privilege Permissions-Policy.")
    if any(x in h for x in ["server","x-powered-by"]): f("HDR-TECH-DISCLOSURE","Technology disclosure header","info",str({k:h[k] for k in h if k in ['server','x-powered-by']}),"Remove unnecessary version/framework headers.", "high")
    if any(k in h for k in ["authorization","proxy-authorization","x-api-key"]): f("HDR-AUTH-IN-RESPONSE","Authentication-related response header","medium","Auth-like response header present","Never return authentication secrets in response headers.", "high")
    cc=h.get("cache-control",""); u=flow.request.url.lower()
    if any(x in u for x in ["login","auth","account","token","session","admin"]) and not any(x in cc.lower() for x in ["no-store","private"]): f("HDR-WEAK-CACHE-SENSITIVE","Weak Cache-Control on sensitive-looking response","medium",cc or "[missing]","Use no-store or private where appropriate.","low")
    return out
