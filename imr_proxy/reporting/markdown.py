from collections import Counter
from imr_proxy.version import get_version
def render_markdown_report(flows)->str:
    c=Counter(f.highest_severity() for f in flows)
    lines=["# imr-proxy Report","",f"Version: `{get_version()}`","","## Summary","",f"Total flows: **{len(flows)}**","","| Severity | Flows |","|---|---:|"]
    for s in ["critical","high","medium","low","info"]: lines.append(f"| {s} | {c.get(s,0)} |")
    lines+=["","## Findings",""]
    for f in flows:
        for x in f.findings:
            lines += [f"### {x.severity.upper()} - {x.title}","",f"- Flow: `{f.id}`",f"- ID: `{x.id}`",f"- Evidence: `{x.evidence}`",f"- Remediation: {x.remediation}",""]
    return "\n".join(lines)
