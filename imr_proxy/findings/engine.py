from imr_proxy.models.finding import Finding
from . import headers,cookies,cors,urls,redirects,responses,tls
CHECKS=[headers.analyze,cookies.analyze,cors.analyze,urls.analyze,redirects.analyze,responses.analyze,tls.analyze]
def analyze_flow(flow):
    findings=[]
    for check in CHECKS:
        try: findings.extend(check(flow))
        except Exception as exc: findings.append(Finding(id="ENGINE-CHECK-ERROR",title="Finding check failed",severity="info",confidence="high",affected_ids=[flow.id],evidence=f"{check.__module__}: {exc}",explanation="Local finding check failed.",impact="Incomplete analysis.",remediation="Run with --verbose."))
    flow.findings=findings; flow.tags=sorted({f.severity for f in findings}); return findings
