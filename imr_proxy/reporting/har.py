from imr_proxy.version import get_version
def _h(h): return [{"name":k,"value":v} for k,v in h.items()]
def flows_to_har(flows):
    entries=[]
    for f in flows:
        req=f.request; resp=f.response
        entries.append({"startedDateTime":f.started_at.isoformat(),"time":f.duration_ms or 0,"request":{"method":req.method,"url":req.url,"httpVersion":"HTTP/1.1","headers":_h(req.headers),"queryString":[],"cookies":[{"name":k,"value":v} for k,v in req.cookies.items()],"headersSize":-1,"bodySize":req.body_size,"postData":{"text":req.body_text or ""} if req.body_text else None},"response":{"status":resp.status_code if resp else 0,"statusText":resp.reason if resp else "","httpVersion":"HTTP/1.1","headers":_h(resp.headers if resp else {}),"cookies":[{"name":k,"value":v} for k,v in (resp.cookies if resp else {}).items()],"content":{"size":resp.body_size if resp else 0,"mimeType":(resp.headers.get("content-type","") if resp else ""),"text":(resp.body_text or "") if resp else ""},"redirectURL":f.redirect_to or "","headersSize":-1,"bodySize":resp.body_size if resp else 0},"cache":{},"timings":{"send":0,"wait":f.duration_ms or 0,"receive":0},"comment":f"imr-proxy findings={len(f.findings)}"})
    return {"log":{"version":"1.2","creator":{"name":"imr-proxy","version":get_version()},"entries":entries}}
