import os, sys
from pathlib import Path
from typing import Any
import yaml
from imr_proxy.constants import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_WEB_HOST, DEFAULT_WEB_PORT, ENV_PREFIX
from imr_proxy.models.config import AppConfig
def default_config_path()->Path:
    return (Path(os.environ.get("APPDATA", Path.home()/"AppData"/"Roaming"))/"imr-proxy"/"config.yaml") if sys.platform.startswith("win") else Path.home()/".config"/"imr-proxy"/"config.yaml"
def default_storage_path()->Path:
    return (Path(os.environ.get("APPDATA", Path.home()/"AppData"/"Roaming"))/"imr-proxy"/"imr-proxy.sqlite3") if sys.platform.startswith("win") else Path.home()/".local"/"share"/"imr-proxy"/"imr-proxy.sqlite3"
def default_ca_dir()->Path:
    return Path.home()/".imr-proxy"/"ca"
def _coerce(v:str)->Any:
    if v.lower() in {"true","yes","1","on"}: return True
    if v.lower() in {"false","no","0","off"}: return False
    try: return int(v)
    except ValueError: return v
def load_config_file(path: Path|None=None)->dict[str,Any]:
    p=path or default_config_path()
    if not p.exists(): return {}
    if p.suffix.lower() in {".yaml",".yml"}:
        data=yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    elif p.suffix.lower()==".toml":
        import tomllib
        data=tomllib.loads(p.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"Unsupported config extension: {p.suffix}")
    if not isinstance(data, dict): raise ValueError("Config file must contain a mapping")
    return data
def load_env_config()->dict[str,Any]:
    return {k[len(ENV_PREFIX):].lower(): _coerce(v) for k,v in os.environ.items() if k.startswith(ENV_PREFIX)}
def build_config(config_file: Path|None=None, overrides: dict[str,Any]|None=None)->AppConfig:
    data={"host":DEFAULT_HOST,"port":DEFAULT_PORT,"web_host":DEFAULT_WEB_HOST,"web_port":DEFAULT_WEB_PORT,"storage":default_storage_path(),"ca_dir":default_ca_dir()}
    data.update(load_config_file(config_file)); data.update(load_env_config())
    if overrides: data.update({k:v for k,v in overrides.items() if v is not None})
    return AppConfig(**data)
def write_default_config(path: Path|None=None, force: bool=False)->Path:
    p=path or default_config_path()
    if p.exists() and not force: raise FileExistsError(f"Config already exists: {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    yaml.safe_dump({"host":DEFAULT_HOST,"port":DEFAULT_PORT,"web":True,"web_host":DEFAULT_WEB_HOST,"web_port":DEFAULT_WEB_PORT,"terminal":False,"allow_remote":False,"scope":[],"exclude":[],"intercept_https":False,"tls_passthrough":True,"cert_mode":"passthrough","redaction_level":"balanced","max_body_size":1048576,"capture_bodies":True}, p.open("w", encoding="utf-8"), sort_keys=False)
    return p
