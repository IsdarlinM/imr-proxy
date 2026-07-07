import time, uuid
from http.cookies import SimpleCookie
from imr_proxy.findings.engine import analyze_flow
from imr_proxy.models.flow import FlowRecord, RequestRecord, ResponseRecord
from imr_proxy.proxy.capture import decode_body, headers_to_dict
from imr_proxy.proxy.redaction import redact_cookies, redact_headers, redact_text, redact_url
from imr_proxy.proxy.scope import ScopeMatcher
from imr_proxy.proxy.tls import extract_tls_metadata
def _cookies_to_dict(obj):
    try: return {str(k):str(v) for k,v in obj.items()}
    except Exception: return {}
def _parse_response_cookies(set_cookies):
    out={}
    for raw in set_cookies:
        c=SimpleCookie()
        try:
            c.load(raw)
            for k,m in c.items(): out[k]=m.value
        except Exception: pass
    return out
class ImrProxyAddon:
    def __init__(self, config, flow_repo, session_id: str, terminal=None):
        self.config=config; self.flow_repo=flow_repo; self.session_id=session_id; self.terminal=terminal; self.scope=ScopeMatcher(config.scope, config.exclude); self._started={}
    def request(self, flow): self._started[flow.id]=time.perf_counter()
    def response(self, flow):
        url=flow.request.pretty_url
        if not self.scope.in_scope(url, getattr(flow.request,"host",None), getattr(flow.request,"path",None)): return
        started=self._started.pop(flow.id, time.perf_counter()); duration=(time.perf_counter()-started)*1000
        rb,rs,rbin=decode_body(flow.request.raw_content or b"", self.config.max_body_size, self.config.capture_bodies)
        sb,ss,sbin=decode_body(flow.response.raw_content or b"", self.config.max_body_size, self.config.capture_bodies)
        reqh=redact_headers(headers_to_dict(flow.request.headers), self.config.redaction_level)
        resph=redact_headers(headers_to_dict(flow.response.headers), self.config.redaction_level)
        reqc=redact_cookies(_cookies_to_dict(flow.request.cookies), self.config.redaction_level)
        try: set_cookies=[redact_text(v,self.config.redaction_level) or "" for v in flow.response.headers.get_all("set-cookie")]
        except Exception: set_cookies=[resph.get("set-cookie","")] if resph.get("set-cookie") else []
        loc=flow.response.headers.get("location")
        rec=FlowRecord(id=str(uuid.uuid4()),session_id=self.session_id,duration_ms=duration,request=RequestRecord(method=flow.request.method,url=redact_url(url,self.config.redaction_level),scheme=flow.request.scheme,host=flow.request.host,port=flow.request.port,path=flow.request.path,query=str(getattr(flow.request,"query","")),headers=reqh,cookies=reqc,body_text=redact_text(rb,self.config.redaction_level),body_size=rs,is_binary=rbin),response=ResponseRecord(status_code=flow.response.status_code,reason=flow.response.reason,headers=resph,cookies=redact_cookies(_parse_response_cookies(set_cookies),self.config.redaction_level),set_cookies=set_cookies,body_text=redact_text(sb,self.config.redaction_level),body_size=ss,is_binary=sbin),redirect_to=redact_url(loc,self.config.redaction_level) if loc else None,intercepted_tls=not self.config.effective_tls_passthrough() and flow.request.scheme=="https",tls_metadata=extract_tls_metadata(flow))
        analyze_flow(rec); self.flow_repo.save(rec)
        if self.terminal: self.terminal.emit(rec)
