"""Build an allowlisted, deterministic publication tree; never modify evidence."""
from pathlib import Path
from urllib.parse import quote
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'zensical-site'
SITE = PROJECT / '.generated'
MODULES = ('01_system_top', '02_clock_keypad', '03_game_fsm',
           '04_puzzle_engine', '05_rom_random', '06_display_audio')
ENTITIES = (('puzzle_top', 'puzzle_pkg'), ('clk_gen', 'keypad_scan'),
            ('game_fsm',), ('puzzle_ctrl',), ('pattern_rom', 'piece_rom', 'rng_lfsr'),
            ('disp_format', 'seg_scan', 'dot_matrix_scan', 'buzzer_ctrl'))
REPO = 'https://github.com/tortrixx/dld/blob/main/'

def source(path):
    assert (ROOT / path).is_file(), path
    return REPO + quote(path, safe='/')

def main():
    shutil.rmtree(SITE, ignore_errors=True)
    SITE.mkdir()
    facts = json.loads((ROOT / 'facts/facts.json').read_text())
    build = facts['build']
    totals = facts['sim']['totals']
    print('Simulation totals:', totals)
    values = {
        'LE': build['fit']['le'].split(' (')[0],
        'LAB': build['fit']['lab'].split(' (')[0],
        'FMAX': str(build['sta']['fmax_mhz']),
        'SETUP': str(build['sta']['setup_slack']),
        'HOLD': str(build['sta']['hold_slack']),
        'SIM_COUNT': str(totals['modules']),
        'BUILD_DATE': build['provenance']['timestamp'],
        'ASSERTIONS': str(sum(m['passed'] for m in facts['sim']['modules'].values())),
    }
    rows = []
    for name, m in sorted(facts['sim']['modules'].items()):
        rows.append(f"| `{name}` | r{m['round']} | {m['passed']} / {m['total']} | [{m['timestamp']}]({source(m['record_json'])}) | [测试台]({source(m['tb'])}) |")
    values['SIM_TABLE'] = '\n'.join(rows)
    values['RNG_CODE'] = (ROOT / 'rtl/rng_lfsr.vhd').read_text().split('architecture',1)[1]
    # Exact source excerpt, not a rewritten pseudocode sample.
    code = (ROOT / 'rtl/rng_lfsr.vhd').read_text().splitlines()
    start = next(i for i,l in enumerate(code) if 'fb :=' in l)
    values['RNG_CODE'] = '\n'.join(code[start:start+8])
    for p in sorted((PROJECT / 'docs').rglob('*')):
        if not p.is_file():
            continue
        assert p.suffix in {'.md', '.css', '.js'}, f'Unexpected authored file: {p}'
        target = SITE / p.relative_to(PROJECT / 'docs')
        target.parent.mkdir(parents=True, exist_ok=True)
        content = p.read_text()
        for key, value in values.items():
            content = content.replace('{{' + key + '}}', value)
        assert not re.search(r'\{\{[A-Z_]+\}\}', content), p
        target.write_text(content, encoding='utf-8')
    (SITE / 'modules').mkdir()
    for name, entities in zip(MODULES, ENTITIES):
        content = (ROOT / 'docs/subsystems' / (name + '.md')).read_text()
        # Remove only the Q&A section; retain later engineering sections if added.
        content = re.sub(r'(?ms)^##\s+5\.\s*答辩问答\s*\n.*?(?=^##\s|\Z)', '', content)
        content = re.sub(r'^# ([^（]+)（[^\n]+）', lambda m: '# '+m[1]+'\n\n'+' · '.join('`'+e+'`' for e in entities), content)
        content = content.replace('> **一句话**：', '> ')
        content = content.replace('**吃进**', '**输入**').replace('**吐出**', '**输出**').replace('**代价**', '**历史资源**')

        for old, new in [('1. 它管什么','接口与职责'),('2. 它在系统里的位置','信号流与连接'),
                         ('3. 三个设计选择','设计实现'),('4. 波形怎么读','波形分析'),
                         ('**少放它一个会怎样**','**集成影响**')]:
            content = content.replace(old, new)
        content = content.replace('老师要是问"碰撞的证据在哪"，答案是', '碰撞判定的验证证据见').replace('不在这一张图上——别硬在图上找。','此截图不包含这些内部观测点。')
        # Correct legacy caption association: architecture caption belongs to architecture.
        if name == '01_system_top':
            content = content.replace('游戏侧的完整决策流程（自检 → 待机 → 预览 → 对局循环 → 过关 / 失败 / 通关）如下：\n\n![游戏流程框图](../assets/images/fig_game_flow.png)\n\n', '')
            at = '\n顶层自己不存画面'
            content = content.replace(at, '\n![游戏流程框图](../assets/images/fig_game_flow.png)\n*游戏流程：自检、待机、预览、对局及胜负分支。*\n'+at)
        # Old line numbers predate the comment cleanup; link the file instead.
        content = re.sub(r'`(rtl/[a-z_]+\.vhd):[0-9-]+`', lambda m: f'[{m[1]}]({source(m[1])})', content)
        content = re.sub(r'（`(rtl/[a-z_]+\.vhd)` 第 [0-9～~—-]+ 行）', lambda m: f'（[{m[1]}]({source(m[1])})）', content)
        content = content.replace('所以不生成电路', '包本身没有独立实例；函数在调用处可能综合成逻辑')
        content = content.replace('芯片里没有存储块（片上 UFM 0 / 1）', '没有可用的片上 RAM 块；另有 UFM，但本设计未使用（UFM 0 / 1）')
        content += '\n## 源码与验证入口\n\n'
        content += '\n'.join(f'- [{e}.vhd]({source("rtl/"+e+".vhd")})' for e in entities)
        content += '\n\n[历史仿真记录与证据边界](../verification.md) · [资源读数口径](../resources.md)\n'
        (SITE / 'modules' / (name + '.md')).write_text(content, encoding='utf-8')
    # Copy only referenced images, never the course PDFs, report, logs or vendor tree.
    images = set()
    for p in SITE.rglob('*.md'):
        content = p.read_text()
        for match in re.finditer(r'!\[([^]]*)\]\(([^)]+)\)', content):
            path = (p.parent / match[2]).resolve()
            assert path.is_relative_to(SITE.resolve() / 'assets/images'), match[2]
            images.add(path.relative_to(SITE.resolve()))
        # Native figure semantics + native image lightbox; no custom client script.
        content = re.sub(r'(?m)^(!\[[^]]*\]\([^)]+\))\n(?:\n)?\*([^\n]+)\*\s*$',
                         r'<figure markdown="span">\n\n\1\n\n<figcaption markdown="span">\2</figcaption>\n\n</figure>', content)
        p.write_text(content, encoding='utf-8')
    for path in sorted(images):
        original = ROOT / 'docs' / path
        assert original.is_file(), original
        (SITE / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, SITE / path)
    manifest = {str(p.relative_to(SITE)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(SITE.rglob('*')) if p.is_file()}
    (SITE / 'publication-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(f'Prepared {len(list(SITE.rglob("*.md")))} pages, {len(images)} referenced images; allowlisted publication only.')

if __name__ == '__main__':
    main()
