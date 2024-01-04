import json
import pathlib as p
import re


pattern = re.compile(r'(?<=__version__ = \')(\d+\.\d+\.\d+)(?=\')')
root = p.Path(__file__).absolute().parents[1]
version = pattern.search((root/'app.py').read_text()).group()
for directory in (root/'cache').iterdir():
    path = directory / 'meta.json'
    meta = json.loads(path.read_text())
    meta['version'] = version
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
