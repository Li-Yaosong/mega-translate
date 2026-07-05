#!/usr/bin/env python3
"""
MEGA 本地化工具 — 提取字符串 + 应用翻译

用法:
  python mega_cn.py extract [exe] [lang]       提取字符串到 translations/<lang>/
  python mega_cn.py patch [exe] [lang] [out]   应用翻译生成本地化EXE
  python mega_cn.py build [exe] [lang] [out]   提取+修补一步完成

lang: 语言代码，如 zh_CN, ja_JP, ko_KR 等，默认 zh_CN
"""
import struct, sys, os, glob
import xml.etree.ElementTree as ET
from xml.dom import minidom

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════
# PE 解析
# ═══════════════════════════════════════════

def parse_pe_sections(data):
    pe = struct.unpack('<I', data[0x3C:0x40])[0]
    ns = struct.unpack('<H', data[pe+6:pe+8])[0]
    ohs = struct.unpack('<H', data[pe+20:pe+22])[0]
    base = pe + 24 + ohs
    sections = {}
    for i in range(ns):
        o = base + i * 40
        name = data[o:o+8].decode('ascii', errors='ignore').strip('\x00')
        sections[name] = {
            'va': struct.unpack('<I', data[o+12:o+16])[0],
            'vs': struct.unpack('<I', data[o+8:o+12])[0],
            'rs': struct.unpack('<I', data[o+16:o+20])[0],
            'rp': struct.unpack('<I', data[o+20:o+24])[0],
        }
    return sections

def rva2raw(rva, sections):
    for sec in sections.values():
        if sec['va'] <= rva < sec['va'] + sec['vs']:
            return rva - sec['va'] + sec['rp']
    return None

def find_rcdata_forms(data, rsrc_raw, sections):
    rsrc_va = sections['.rsrc']['va']
    root = rsrc_raw
    total = struct.unpack('<H', data[root+12:root+14])[0] + struct.unpack('<H', data[root+14:root+16])[0]
    forms = {}
    for i in range(total):
        eo = root + 16 + i * 8
        nid = struct.unpack('<I', data[eo:eo+4])[0]
        drva = struct.unpack('<I', data[eo+4:eo+8])[0]
        if nid != 10 or not (drva >> 31): continue
        d2 = rsrc_raw + (drva & 0x7FFFFFFF)
        t2 = struct.unpack('<H', data[d2+12:d2+14])[0] + struct.unpack('<H', data[d2+14:d2+16])[0]
        for j in range(t2):
            eo2 = d2 + 16 + j * 8
            nid2 = struct.unpack('<I', data[eo2:eo2+4])[0]
            drva2 = struct.unpack('<I', data[eo2+4:eo2+8])[0]
            if not (drva2 >> 31): continue
            name = None
            if nid2 & 0x80000000:
                np = rsrc_raw + (nid2 & 0x7FFFFFFF)
                nl = struct.unpack('<H', data[np:np+2])[0]
                name = data[np+2:np+2+nl*2].decode('utf-16le', errors='ignore')
            if not name or not name.startswith('T') or name.endswith(('_150','_200')):
                continue
            ld = rsrc_raw + (drva2 & 0x7FFFFFFF)
            eo3 = ld + 16
            drva3 = struct.unpack('<I', data[eo3+4:eo3+8])[0]
            if drva3 >> 31: continue
            de = rsrc_raw + drva3
            rva = struct.unpack('<I', data[de:de+4])[0]
            sz = struct.unpack('<I', data[de+4:de+8])[0]
            fo = rva2raw(rva, sections)
            if fo is None: fo = rva - rsrc_va + sections['.rsrc']['rp']
            forms[name] = {'offset': fo, 'size': sz, 'rva': rva, 'de': de}
    return forms

# ═══════════════════════════════════════════
# LFM 字符串扫描
# ═══════════════════════════════════════════

PROPS = (b'Caption', b'Hint', b'Text', b'Title')
SKIP = {'ToolButton1','ToolButton2','ToolButton7','ToolButton11',
        'ToolButton14','ToolButton23','ToolButton26'}

def scan_lfm_strings(fd, trans=None):
    """扫描LFM可翻译字符串，trans={原文:翻译} 可选"""
    matches = []
    for prop in PROPS:
        plen = len(prop); pos = 0
        while pos < len(fd) - plen - 2:
            fp = fd.find(prop, pos)
            if fp == -1: break
            if fp == 0 or fd[fp-1] != plen: pos = fp+1; continue
            ap = fp + plen
            if ap >= len(fd) or fd[ap] != 0x06: pos = fp+1; continue
            sl = fd[ap+1]
            if sl == 0 or sl >= 255 or ap+2+sl > len(fd): pos = fp+1; continue
            try: text = fd[ap+2:ap+2+sl].decode('utf-8')
            except UnicodeDecodeError: pos = fp+1; continue
            if not text or not text.strip() or text.startswith(('ak','al','po')) or text in SKIP:
                pos = fp+1; continue
            t = trans.get(text, '') if trans else ''
            matches.append({'prop': prop.decode(), 'type_off': ap, 'data_off': ap+2,
                            'data_end': ap+2+sl, 'str_len': sl, 'original': text, 'trans': t})
            pos = fp + 1
    matches.sort(key=lambda m: m['data_off'])
    deduped = []
    for m in matches:
        if not deduped or m['type_off'] >= deduped[-1]['data_end']:
            deduped.append(m)
    return deduped

# ═══════════════════════════════════════════
# LFM 修补（原地 / 重建）
# ═══════════════════════════════════════════

def patch_in_place(data, offset, size, trans):
    fd = data[offset:offset+size]
    patches = []
    for m in scan_lfm_strings(fd, trans):
        if not m['trans']: continue
        tb = m['trans'].encode('utf-8')
        if len(tb) > m['str_len']: continue
        old = fd[m['data_off']:m['data_end']]
        new = tb + b'\x20' * (m['str_len'] - len(tb))
        patches.append((offset + m['data_off'], old, new))
    return patches

def rebuild_lfm(fd, trans):
    matches = scan_lfm_strings(fd, trans)
    if not matches: return bytes(fd)
    result = bytearray(); prev = 0
    for m in matches:
        if not m['trans']: continue
        result.extend(fd[prev:m['type_off']])
        tb = m['trans'].encode('utf-8')
        if len(tb) <= 255:
            result.append(0x06); result.append(len(tb))
        else:
            result.append(0x0C); result.extend(struct.pack('<I', len(tb)))
        result.extend(tb)
        prev = m['data_end']
    result.extend(fd[prev:])
    return bytes(result)

def needs_rebuild(fd, trans):
    for m in scan_lfm_strings(fd, trans):
        if m['trans'] and len(m['trans'].encode('utf-8')) > m['str_len']:
            return True
    return False

# ═══════════════════════════════════════════
# PE 扩展 / 签名移除
# ═══════════════════════════════════════════

RSRC_VA, RSRC_RAW = 0x01409000, 0x013D1E00
FILEALIGN, SECALIGN = 0x200, 0x1000

def expand_and_strip(data, expansions, pe):
    rawsize = struct.unpack('<I', data[0x2B0:0x2B4])[0]
    data = data[:RSRC_RAW + rawsize]
    sd = pe + 24 + 112 + 4*8
    data[sd:sd+8] = b'\x00'*8
    data[pe+24+64:pe+24+68] = b'\x00'*4
    for _, new_lfm, de in expansions:
        pad = (4 - len(data) % 4) % 4
        data.extend(b'\x00'*pad)
        new_rva = RSRC_VA + (len(data) - RSRC_RAW)
        data.extend(new_lfm)
        struct.pack_into('<I', data, de, new_rva)
        struct.pack_into('<I', data, de+4, len(new_lfm))
    new_rs = len(data) - RSRC_RAW
    new_rsa = (new_rs + FILEALIGN - 1) & ~(FILEALIGN - 1)
    new_vs = new_rs
    struct.pack_into('<I', data, 0x2A8, new_vs)
    struct.pack_into('<I', data, 0x2B0, new_rsa)
    data.extend(b'\x00' * (new_rsa - new_rs))
    struct.pack_into('<I', data, pe+24+56, (RSRC_VA+new_vs+SECALIGN-1)&~(SECALIGN-1))
    struct.pack_into('<I', data, pe+24+112+2*8+4, new_vs)
    return data

def strip_signature(data):
    pe = struct.unpack('<I', data[0x3C:0x40])[0]
    data[pe+24+64:pe+24+68] = b'\x00'*4
    sd = pe + 24 + 112 + 4*8
    sr, ss = struct.unpack('<I', data[sd:sd+4])[0], struct.unpack('<I', data[sd+4:sd+8])[0]
    if ss == 0: return data
    data[sd:sd+8] = b'\x00'*8
    if 0 < sr < len(data):
        end = min(sr+ss, len(data))
        data[sr:end] = b'\x00'*(end-sr)
    return data

# ═══════════════════════════════════════════
# .ts 文件读写
# ═══════════════════════════════════════════

def load_ts(path):
    """读单个 .ts → {source: translation}"""
    if not os.path.exists(path): return {}
    tree = ET.parse(path)
    d = {}
    ctx = tree.getroot().find('context')
    if ctx is None: return d
    for msg in ctx.findall('message'):
        src = msg.find('source').text or ''
        te = msg.find('translation')
        if te is not None and te.text and te.get('type') != 'unfinished':
            d[src] = te.text
    return d

def write_ts(path, form_name, strings, existing, lang):
    """写单个 .ts，strings=[(prop, max_bytes, source)]，保留已有翻译"""
    ts = ET.Element('TS')
    ts.set('version', '2.1'); ts.set('language', lang); ts.set('sourcelanguage', 'en')
    ctx = ET.SubElement(ts, 'context')
    ET.SubElement(ctx, 'name').text = form_name

    seen, translated, new = set(), 0, 0
    for prop, maxb, src in sorted(strings, key=lambda x: x[2]):
        if (src, prop) in seen: continue
        seen.add((src, prop))
        msg = ET.SubElement(ctx, 'message')
        ET.SubElement(msg, 'source').text = src
        ET.SubElement(msg, 'comment').text = f'{prop} (max {maxb} bytes)'
        tr = ET.SubElement(msg, 'translation')
        t = existing.get(src, '')
        if t:
            tr.text = t; tr.set('type', 'finished'); translated += 1
        else:
            tr.set('type', 'unfinished'); new += 1

    raw = ET.tostring(ts, encoding='unicode', xml_declaration=False)
    pretty = minidom.parseString(raw).toprettyxml(indent='  ')
    lines = [l for l in pretty.split('\n') if l.strip()]
    xml = '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n' + '\n'.join(lines)[len('<?xml version="1.0" ?>'):]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(xml)
    return translated, new

def load_all_ts(ts_dir):
    """读目录下所有 .ts → {form: {src: trans}}"""
    result = {}
    for path in sorted(glob.glob(os.path.join(ts_dir, '*.ts'))):
        fn = os.path.splitext(os.path.basename(path))[0]
        result[fn] = load_ts(path)
    return result

def ts_dir(lang):
    return os.path.join(SCRIPT_DIR, 'translations', lang)

# ═══════════════════════════════════════════
# 命令
# ═══════════════════════════════════════════

def cmd_extract(exe_path, lang):
    td = ts_dir(lang)
    print(f'读取 {exe_path}...')
    data = open(exe_path, 'rb').read()
    sections = parse_pe_sections(data)
    forms = find_rcdata_forms(data, sections['.rsrc']['rp'], sections)
    print(f'找到 {len(forms)} 个表单资源')

    os.makedirs(td, exist_ok=True)
    total_t, total_n, total_forms = 0, 0, 0

    for name in sorted(forms):
        info = forms[name]
        fd = data[info['offset']:info['offset']+info['size']]
        strings = scan_lfm_strings(fd)
        if not strings: continue

        ts_path = os.path.join(td, f'{name}.ts')
        existing = load_ts(ts_path)
        entries = [(m['prop'], m['str_len'], m['original']) for m in strings]
        t, n = write_ts(ts_path, name, entries, existing, lang)
        total_t += t; total_n += n; total_forms += 1

    print(f'\n完成！{total_forms} 个表单 → {td}/')
    print(f'  已有翻译: {total_t}  新增未翻译: {total_n}')

def cmd_patch(exe_path, lang, out_path):
    td = ts_dir(lang)
    print(f'读取 {exe_path}...')
    data = bytearray(open(exe_path, 'rb').read())

    print(f'加载翻译 {td}/...')
    translations = load_all_ts(td)
    if not translations:
        print(f'未找到翻译文件！请先运行 extract'); return
    print(f'  {len(translations)} 个表单有翻译')

    print('解析PE...')
    sections = parse_pe_sections(data)
    pe = struct.unpack('<I', data[0x3C:0x40])[0]
    forms = find_rcdata_forms(data, sections['.rsrc']['rp'], sections)
    print(f'找到 {len(forms)} 个表单资源')

    in_place, expansions = [], []
    n_applied = n_rebuilt = n_long = 0

    for fn, ft in sorted(translations.items()):
        if fn not in forms: continue
        fi = forms[fn]
        fd = bytes(data[fi['offset']:fi['offset']+fi['size']])
        if needs_rebuild(fd, ft):
            new = rebuild_lfm(fd, ft)
            if new != fd:
                expansions.append((fn, new, fi['de'])); n_rebuilt += 1
            n_applied += sum(1 for t in ft.values() if t)
        else:
            for off, old, new in patch_in_place(data, fi['offset'], fi['size'], ft):
                if bytes(data[off:off+len(old)]) == old:
                    in_place.append((off, new)); n_applied += 1
        n_long += sum(1 for o, t in ft.items() if t and len(t.encode('utf-8')) > len(o.encode('utf-8')))

    print(f'\n统计: 原地{len(in_place)} 重建{n_rebuilt} 过长{n_long}（已重建解决）')

    for off, new in in_place:
        data[off:off+len(new)] = new

    if expansions:
        print(f'扩展.rsrc（{len(expansions)}个）...')
        data = expand_and_strip(data, expansions, pe)
    else:
        print('移除签名...')
        data = bytearray(strip_signature(bytes(data)))

    open(out_path, 'wb').write(data)
    print(f'\n完成！{out_path} ({os.path.getsize(out_path):,} bytes)')

def cmd_build(exe_path, lang, out_path):
    cmd_extract(exe_path, lang)
    print()
    cmd_patch(exe_path, lang, out_path)

# ═══════════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)

    cmd = sys.argv[1]
    exe = sys.argv[2] if len(sys.argv) > 2 else r'd:\Software\MEGA12\MEGA_64.exe.bak'
    lang = sys.argv[3] if len(sys.argv) > 3 else 'zh_CN'

    # 输出文件名: MEGA_64.exe.bak + zh_CN → MEGA_64_zh_CN.exe
    base = exe.replace('.bak', '').rstrip('.')
    stem, ext = os.path.splitext(base)
    out = stem + '_' + lang + ext

    if cmd == 'extract':
        cmd_extract(exe, lang)
    elif cmd == 'patch':
        out = sys.argv[4] if len(sys.argv) > 4 else out
        cmd_patch(exe, lang, out)
    elif cmd == 'build':
        out = sys.argv[4] if len(sys.argv) > 4 else out
        cmd_build(exe, lang, out)
    else:
        print(f'未知命令: {cmd}'); print(__doc__); sys.exit(1)
