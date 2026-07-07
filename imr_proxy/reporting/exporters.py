import csv, json
from pathlib import Path
from imr_proxy.reporting.har import flows_to_har
from imr_proxy.reporting.html import render_html_report
from imr_proxy.reporting.markdown import render_markdown_report
from imr_proxy.version import get_version
def export_json(flows, output: Path)->Path:
    output.write_text(json.dumps({"tool":"imr-proxy","version":get_version(),"flows":[f.model_dump(mode="json") for f in flows]}, indent=2, ensure_ascii=False), encoding="utf-8"); return output
def export_csv(flows, output: Path)->Path:
    with output.open("w", newline="", encoding="utf-8") as fh:
        wr=csv.DictWriter(fh, fieldnames=["id","method","url","status","duration_ms","highest_severity","findings"]); wr.writeheader()
        for f in flows: wr.writerow({"id":f.id,"method":f.request.method,"url":f.request.url,"status":f.response.status_code if f.response else "","duration_ms":f.duration_ms or "","highest_severity":f.highest_severity(),"findings":len(f.findings)})
    return output
def export_har(flows, output: Path)->Path: output.write_text(json.dumps(flows_to_har(flows), indent=2, ensure_ascii=False), encoding="utf-8"); return output
def export_markdown(flows, output: Path)->Path: output.write_text(render_markdown_report(flows), encoding="utf-8"); return output
def export_html(flows, output: Path)->Path: output.write_text(render_html_report(flows), encoding="utf-8"); return output
def export_flows(flows, fmt: str, output: Path)->Path:
    output=output.expanduser().resolve(); output.parent.mkdir(parents=True, exist_ok=True); fmt=fmt.lower()
    return {"json":export_json,"csv":export_csv,"har":export_har,"md":export_markdown,"markdown":export_markdown,"html":export_html}[fmt](flows, output)
