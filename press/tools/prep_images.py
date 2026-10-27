# One-off: turn colour screenshots/photos into newsprint-ready greyscale
# plates. Usage: prep_images.py <src> <out-name> <width> [aspect w:h]
import sys
from PIL import Image, ImageEnhance, ImageOps

src, name, width = sys.argv[1], sys.argv[2], int(sys.argv[3])
aspect = sys.argv[4] if len(sys.argv) > 4 else None
im = Image.open(src).convert("RGB")
if aspect:
    aw, ah = map(int, aspect.split(":"))
    w, h = im.size
    if w / h > aw / ah:
        nw = round(h * aw / ah)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = round(w * ah / aw)
        im = im.crop((0, 0, w, nh))  # keep the top: headers carry the story
im = ImageOps.grayscale(im)
im = ImageOps.autocontrast(im, cutoff=1)
im = ImageEnhance.Contrast(im).enhance(1.12)
im = im.resize((width, round(width * im.size[1] / im.size[0])), Image.LANCZOS)
im.save(f"{sys.argv[0].rsplit('/', 2)[0]}/img/{name}.jpg", quality=70, optimize=True, progressive=True)
print(name, im.size)
