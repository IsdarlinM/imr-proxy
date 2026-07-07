py -3.11 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
pytest
