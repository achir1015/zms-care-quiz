"""產生程式圖示：assets/icon.png（1024）、packaging/icon.ico、assets/icon.ico。

資料助秘系列的深藍到青綠圓角方塊；中間是「學科測驗」答案卷（A B C D 四個選項，C 打勾），
左下角愛心代表照顧服務，右上角金幣寫「照」。
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 1024


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shadow(img, shape_fn, blur=18, offset=(10, 20), alpha=100):
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shape_fn(ImageDraw.Draw(sh), offset, (0, 0, 0, alpha))
    return Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(blur)))


def font(size):
    try:
        f = ImageFont.truetype(os.path.join(HERE, "assets", "fonts", "NotoSansTC-VF.ttf"), size)
        try:
            f.set_variation_by_name("Black")
        except Exception:
            pass
        return f
    except Exception:
        return ImageFont.load_default()


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    c1, c2 = (15, 60, 110), (14, 150, 120)
    for y in range(S):
        gd.line([(0, y), (S, y)], fill=lerp(c1, c2, y / S) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([40, 40, S - 40, S - 40], radius=220, fill=255)
    img.paste(grad, (0, 0), mask)
    gloss = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(gloss).ellipse([-200, -520, S + 200, 420], fill=(255, 255, 255, 34))
    img = Image.alpha_composite(img, Image.composite(gloss, Image.new("RGBA", (S, S)), mask))

    # 後面一張淡色試卷（稍微旋轉）＋前面白色答案卷
    for color, angle, (dx, dy) in [((255, 214, 120), -8, (70, 10)), ((255, 255, 255), 0, (0, 0))]:
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle([190 + dx, 230 - dy, 730 + dx, 870 - dy], radius=54,
                                                fill=color + (255,))
        layer = layer.rotate(angle, center=(460, 550), resample=Image.BICUBIC)
        sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        sh.paste((0, 0, 0, 90), (14, 24), layer.getchannel("A"))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(20)))
        img = Image.alpha_composite(img, layer)
    d = ImageDraw.Draw(img)
    # 標題列「學科」
    d.rounded_rectangle([190, 230, 730, 360], radius=54, fill=(30, 77, 140, 255))
    d.rectangle([190, 300, 730, 360], fill=(30, 77, 140, 255))
    d.text((460, 292), "學科測驗", font=font(78), fill=(255, 255, 255, 255), anchor="mm")
    # 四個選項：A B C D，C 是正確答案（青綠實心＋勾）
    for i, letter in enumerate("ABCD"):
        y = 445 + i * 110
        right = letter == "C"
        if right:
            d.rounded_rectangle([225, y - 46, 695, y + 46], radius=24, fill=(220, 247, 240, 255))
        d.ellipse([245, y - 36, 317, y + 36], fill=((15, 162, 148) if right else (226, 232, 240)) + (255,))
        d.text((281, y - 2), letter, font=font(50), fill=((255, 255, 255) if right else (51, 65, 85)) + (255,),
               anchor="mm")
        d.rounded_rectangle([345, y - 15, (570 if right else 640) - (i % 2) * 90, y + 15], radius=15,
                            fill=((15, 162, 148) if right else (203, 213, 225)) + (255,))
        if right:
            d.line([(600, y), (628, y + 26), (676, y - 30)], fill=(22, 163, 74, 255), width=16, joint="curve")

    # 左下角愛心（照顧）
    hx, hy = 830, 830
    img = shadow(img, lambda d, o, f: d.ellipse([hx - 95 + o[0], hy - 95 + o[1], hx + 95 + o[0], hy + 95 + o[1]],
                                                fill=f), blur=14, offset=(8, 14), alpha=100)
    d = ImageDraw.Draw(img)
    d.ellipse([hx - 95, hy - 95, hx + 95, hy + 95], fill=(255, 255, 255, 255), outline=(255, 214, 214, 255), width=8)
    d.text((hx, hy + 4), "♥", font=font(130), fill=(225, 29, 72, 255), anchor="mm")

    # 金幣「照」
    cx, cy, r = 805, 225, 140
    img = shadow(img, lambda d, o, f: d.ellipse([cx - r + o[0], cy - r + o[1], cx + r + o[0], cy + r + o[1]], fill=f),
                 blur=16, offset=(10, 18), alpha=110)
    d = ImageDraw.Draw(img)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(240, 180, 40, 255), outline=(255, 226, 140, 255), width=14)
    d.ellipse([cx - r + 30, cy - r + 30, cx + r - 30, cy + r - 30], outline=(201, 138, 20, 255), width=6)
    d.text((cx, cy - 6), "照", font=font(140), fill=(20, 50, 92, 255), anchor="mm")
    img.putalpha(Image.composite(img.getchannel("A"), Image.new("L", (S, S), 0), mask))
    out = os.path.join(HERE, "assets", "icon.png")
    img.save(out)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    for p in (os.path.join(HERE, "packaging", "icon.ico"), os.path.join(HERE, "assets", "icon.ico")):
        img.save(p, sizes=sizes)
    print("ok", out)


if __name__ == "__main__":
    main()
