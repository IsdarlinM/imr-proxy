import re
from http.cookies import SimpleCookie
from imr_proxy.models.finding import Finding
from . import references as ref
SENS=re.compile(r"(session|sess|sid|token|auth|jwt|csrf|xsrf)", re.I)
def analyze(flow):
    out=[]
    if not flow.response: return out
    seen={}
    for raw in flow.response.set_cookies:
        c=SimpleCookie()
        try: c.load(raw)
        except Exception: continue
        for m in c.values():
            name=m.key; attrs={k.lower():m[k] for k in m.keys() if m[k]}; sensitive=bool(SENS.search(name)); seen[name.lower()]=seen.get(name.lower(),0)+1
            def add(id,title,sev,evi,rem,conf="medium"):
                out.append(Finding(id=id,title=title,severity=sev,confidence=conf,affected_ids=[flow.id],evidence=evi,explanation=title,impact="Cookie attributes affect browser session security.",remediation=rem,references=[ref.OWASP_SESSION,ref.RFC_6265],false_positive_notes="Name-based sensitivity is heuristic."))
            if sensitive and "secure" not in attrs: add("COOKIE-MISSING-SECURE","Sensitive-looking cookie missing Secure","medium" if flow.request.scheme=="https" else "high",name,"Add Secure and enforce HTTPS.")
            if sensitive and "httponly" not in attrs: add("COOKIE-MISSING-HTTPONLY","Sensitive-looking cookie missing HttpOnly","medium",name,"Add HttpOnly unless JavaScript access is required.")
            if sensitive and "samesite" not in attrs: add("COOKIE-MISSING-SAMESITE","Sensitive-looking cookie missing SameSite","low",name,"Set SameSite=Lax/Strict or None; Secure when needed.")
            if attrs.get("samesite","").lower()=="none" and "secure" not in attrs: add("COOKIE-SAMESITE-NONE-NO-SECURE","SameSite=None without Secure","medium",name,"Use SameSite=None; Secure.")
            if attrs.get("domain","").startswith("."): add("COOKIE-BROAD-DOMAIN","Cookie domain may be broad","low",attrs.get("domain",""),"Use host-only cookies where possible.")
            if sensitive and (len(m.value)<16 or len(set(m.value))<8): add("COOKIE-WEAK-LOOKING-ENTROPY","Weak-looking cookie entropy indicator","low",f"{name} length={len(m.value)}","Use cryptographically secure random identifiers.","low")
    for n,c in seen.items():
        if c>1: out.append(Finding(id="COOKIE-DUPLICATE-SETCOOKIE",title="Duplicate Set-Cookie name",severity="low",confidence="high",affected_ids=[flow.id],evidence=f"{n} count={c}",explanation="Duplicate cookie names can conflict.",impact="Browser behavior may be inconsistent.",remediation="Avoid duplicate cookie names unless deliberately scoped.",references=[ref.RFC_6265]))
    if flow.request.scheme=="http":
        for name in flow.request.cookies:
            if SENS.search(name): out.append(Finding(id="COOKIE-SENT-OVER-HTTP",title="Sensitive-looking cookie transmitted over HTTP",severity="high",confidence="medium",affected_ids=[flow.id],evidence=name,explanation="HTTP exposes cookies on the network.",impact="Session material may leak.",remediation="Use HTTPS and Secure cookies.",references=[ref.OWASP_SESSION]))
    return out
