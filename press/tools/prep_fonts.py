# One-off: pin the variable sources to the static faces the press uses,
# trimmed to Latin + the punctuation a newspaper needs.
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools import subset

src, out = sys.argv[1], sys.argv[2]
FACES = {
    "display": ("Newsreader[opsz,wght].ttf", {"wght": 800, "opsz": 72}),
    "head": ("Newsreader[opsz,wght].ttf", {"wght": 700, "opsz": 36}),
    "text": ("Newsreader[opsz,wght].ttf", {"wght": 400, "opsz": 16}),
    "textbold": ("Newsreader[opsz,wght].ttf", {"wght": 650, "opsz": 16}),
    "italic": ("Newsreader-Italic[opsz,wght].ttf", {"wght": 400, "opsz": 16}),
    "label": ("LibreFranklin[wght].ttf", {"wght": 600}),
    "mono": ("IBMPlexMono-Medium.ttf", None),
}
UNI = "U+0020-007E,U+00A0-00FF,U+2010-2027,U+2030-203A,U+2190-2199,U+2022,U+25A0-25FF,U+2600-27BF,U+2122,U+221E"
for name, (fn, loc) in FACES.items():
    f = TTFont(f"{src}/{fn}")
    if loc:
        f = instantiateVariableFont(f, loc)
    opts = subset.Options()
    opts.layout_features = ["kern", "liga", "onum", "lnum", "tnum", "smcp"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    s = subset.Subsetter(opts)
    s.populate(unicodes=subset.parse_unicodes(UNI))
    s.subset(f)
    f.save(f"{out}/{name}.ttf")
    cmap = f.getBestCmap()
    has = "".join(ch for ch in "▲▼●◆★✓→↗✂—–·•“”‘’…∞§№" if ord(ch) in cmap)
    print(f"{name:9} glyphs={len(f.getGlyphOrder()):4}  has: {has}")
