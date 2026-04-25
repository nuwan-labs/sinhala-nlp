"""Patch extract_pdf.py with the updated _fix_iskoola_pota function."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

with open('extract_pdf.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '# ── IskoolaPota font correction'
end_marker   = '\n\n\n# ── PDF extraction'

start_idx = content.find(start_marker)
end_idx   = content.find(end_marker, start_idx)
if start_idx == -1 or end_idx == -1:
    sys.exit(f'Markers not found: start={start_idx} end={end_idx}')

# Build the replacement using actual Unicode code points for sentinels
PH_O  = ''
PH_OO = ''

new_section = (
    '# ── IskoolaPota font correction ────────────────────────────────────────────\n'
    '# IskoolaPota ToUnicode errors confirmed by OCR comparison (50 pages, n≥10):\n'
    '#   1. Pre-vowel ෙ glyph   → U+0DC0 ව  (spurious VA; should be absent)\n'
    '#   2. Long-ā vowel glyph  → U+0DDC ො  (O-vowel sign; should be U+0DCF ා)\n'
    '#\n'
    '# Both vowel families with a visual pre-vowel ෙ component are affected:\n'
    '#   ො (O-vowel):    C+ො → "ව ො" (ව=ෙ-glyph, SPACE=lost C, ො=ā-glyph)\n'
    '#   ෝ (long-O):     C+ෝ → "වCෝ" (ව=ෙ-glyph, C=consonant, ෝ=long-ā-glyph)\n'
    '#\n'
    '# Insight: standalone ො in PDF ALWAYS = misencoded ා, because genuine O-vowel\n'
    '# always arrives with a preceding ව artefact which our rules strip first.\n'
    '\n'
    "_IKP_PH_O  = '\\ue000'  # private-use sentinels; never appear in real Sinhala text\n"
    "_IKP_PH_OO = '\\ue001'\n"
    '\n'
    '\n'
    'def _fix_iskoola_pota(text):\n'
    '    """\n'
    '    Fix IskoolaPota ToUnicode errors.  Applied per-span before tokenisation.\n'
    '\n'
    '    Pass 1 ─ ෝ (long-O, U+0DDD):\n'
    '      Strip spurious ව artefact before consonant sequence ending in ෝ.\n'
    "      Pattern: ව + [non-space, non-ව run] + ෝ  →  run + ෝ\n"
    "      e.g. 'වයෝගය' → 'යෝගය' ('yෝgy' label)\n"
    '\n'
    '    Pass 2 ─ ො (O-vowel, U+0DDC):\n'
    '      a) ව + single-consonant + ො  →  consonant + sentinel\n'
    '      b) ව + SPACE + ො            →  sentinel  (consonant was lost to SPACE)\n'
    '      c) standalone ො (not sentinel)   →  ා     (misencoded long-ā)\n'
    '      d) restore sentinel                  →  ො\n'
    '    """\n'
    '    # Pass 1: long-O family\n'
    "    text = re.sub(r'ව([^ව\\s]+?)ෝ', r'\\1' + _IKP_PH_OO, text)\n"
    "    text = text.replace('ව ෝ', _IKP_PH_OO)\n"
    '\n'
    '    # Pass 2: O-vowel family\n'
    "    text = re.sub(r'ව([ක-ෆ])ො', r'\\1' + _IKP_PH_O, text)\n"
    "    text = text.replace('ව ො', _IKP_PH_O)\n"
    "    text = text.replace('ො', 'ා')   # standalone ො = misencoded ා\n"
    '    text = text.replace(_IKP_PH_O,  \'ො\')\n'
    '    text = text.replace(_IKP_PH_OO, \'ෝ\')\n'
    '    return text'
)

content = content[:start_idx] + new_section + content[end_idx:]

with open('extract_pdf.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patched successfully.')
# Quick verify
idx = content.find('_IKP_PH_O')
print(content[idx:idx+300])
