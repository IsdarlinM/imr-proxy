from fnmatch import fnmatch
from urllib.parse import urlparse
def normalize_host(host: str)->str: return host.lower().strip().rstrip(".")
def _matches(pattern: str, host: str, url: str, path: str)->bool:
    p=pattern.lower().strip()
    if not p: return False
    if "://" in p: return fnmatch(url.lower(), p)
    if "/" in p: return fnmatch(path.lower(), p) or fnmatch(url.lower(), p)
    h=normalize_host(host); p=normalize_host(p)
    return fnmatch(h,p) or h==p or h.endswith("."+p)
class ScopeMatcher:
    def __init__(self, allow: list[str]|None=None, exclude: list[str]|None=None):
        self.allow=allow or []; self.exclude=exclude or []
    def in_scope(self, url: str, host: str|None=None, path: str|None=None)->bool:
        parsed=urlparse(url); host=host or parsed.hostname or ""; path=path or parsed.path or "/"
        if any(_matches(p,host,url,path) for p in self.exclude): return False
        return True if not self.allow else any(_matches(p,host,url,path) for p in self.allow)
