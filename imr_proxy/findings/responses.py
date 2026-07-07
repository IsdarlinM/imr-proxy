import re
from imr_proxy.models.finding import Finding
from . import references as ref
CHECKS=[(re.compile(r"Traceback \(most recent call last\)|PHP (Fatal error|Warning|Notice)|Stack trace",re.I),"RESP-STACK-TRACE","Stack trace or verbose error","medium"),(re.compile(r"debug mode|werkzeug debugger|django debug|laravel debug|xdebug",re.I),"RESP-DEBUG-INDICATOR","Debug mode indicator","medium"),(re.compile(r"\b(10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|192\.168\.\d+\.\d+|localhost|127\.0\.0\.1)\b",re.I),"RESP-INTERNAL-HOST-LEAK","Internal host/IP indicator","low"),(re.compile(r"169\.254\.169\.254|metadata\.google\.internal|latest/meta-data|IMDS",re.I),"RESP-CLOUD-METADATA-INDICATOR","Cloud metadata indicator","medium")]
def analyze(flow):
    if not flow.response or not flow.response.body_text: return []
    body=flow.response.body_text[:200000]; out=[]
    for rx,i,t,s in CHECKS:
        m=rx.search(body)
        if m: out.append(Finding(id=i,title=t,severity=s,confidence="medium",affected_ids=[flow.id],evidence=m.group(0)[:160],explanation=t,impact="Information disclosure may aid targeted testing.",remediation="Disable debug output and sanitize errors.",references=[ref.OWASP_WSTG,ref.OWASP_ASVS],false_positive_notes="Pattern matching is heuristic."))
    return out
