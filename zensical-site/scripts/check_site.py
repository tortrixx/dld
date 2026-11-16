"""Validate the rendered publication at /dld/, including anchors and CSS assets."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'zensical-site/site'
ORIGIN = 'https://tortrixx.github.io'
BASE = ORIGIN + '/dld/'

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.ids=set(); self.refs=[]; self.canonical=[]
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if a.get('id'): self.ids.add(a['id'])
        for key in ('href','src','poster'):
            if a.get(key): self.refs.append(a[key])
        if tag=='link' and a.get('rel')=='canonical': self.canonical.append(a['href'])

def main():
    errors=[]
    pages={p:Page(p.read_text()) for p in SITE.rglob('*.html')}
    checked=0
    for p, page in pages.items():
        rel=p.relative_to(SITE).as_posix()
        url=BASE+(rel[:-10] if rel.endswith('index.html') else rel)
        for ref in page.refs:
            target=urlsplit(urljoin(url,ref))
            if target.scheme not in ('http','https') or target.netloc!=urlsplit(ORIGIN).netloc: continue
            path=unquote(target.path)
            if not path.startswith('/dld/'):
                errors.append(f'{rel}: escapes /dld/: {ref}');continue
            f=SITE/path[len('/dld/'):]
            if path.endswith('/'): f=f/'index.html'
            if not f.is_file(): errors.append(f'{rel}: missing {ref}');continue
            if target.fragment and f in pages and unquote(target.fragment) not in pages[f].ids:
                errors.append(f'{rel}: missing anchor {ref}')
            checked+=1
        if rel!='404.html' and page.canonical!=[url]: errors.append(f'{rel}: incorrect canonical {page.canonical}')
    for css in SITE.rglob('*.css'):
        for ref in re.findall(r'url\([\'"]?([^\)\'\"]+)',css.read_text()):
            if ref.startswith(('data:','http:','https:','#')):continue
            f=(css.parent/unquote(ref.split('?')[0])).resolve()
            if not f.is_relative_to(SITE.resolve()) or not f.is_file():errors.append(f'{css.name}: missing CSS asset {ref}')
    manifest=json.loads((SITE/'publication-manifest.json').read_text())
    for name, digest in manifest.items():
        # Markdown is rendered; copied image/style bytes must remain identical.
        if name.endswith('.md'): continue
        f=SITE/name
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=digest: errors.append(f'Publication byte mismatch: {name}')
    for p in SITE.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(SITE).as_posix()
        if any(x in p.parts for x in ('refs','report','rounds','图')) or p.suffix in ('.pdf','.docx','.typ','.md','.log','.vwf','.vhd'):
            errors.append(f'Unpublished material in output: {rel}')
    for p in pages:
        text=p.read_text()
        if '答辩问答' in text or re.search(r'>Q[1-9]',text):errors.append(f'Q&A leaked: {p.name}')
    if errors: raise SystemExit('\n'.join(errors))
    print(f'PASS: {len(pages)} HTML pages; {checked} local references and anchors; CSS assets; publication byte hashes; /dld/ boundary.')

if __name__=='__main__': main()
