from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from imr_proxy.version import get_version
def render_html_report(flows)->str:
    env=Environment(loader=FileSystemLoader(Path(__file__).parent/"templates"), autoescape=select_autoescape())
    return env.get_template("report.html.j2").render(flows=flows, version=get_version())
