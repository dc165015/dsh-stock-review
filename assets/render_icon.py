"""Render the plugin icon raster (market icon must be png/webp/jpg, svg not accepted)."""

from PIL import Image, ImageDraw

S = 180
K = 6  # supersample factor
W = S * K


def rounded_rect(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def main():
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # background card
    rounded_rect(d, (2 * K, 2 * K, W - 2 * K, W - 2 * K), radius=42 * K, fill=(13, 24, 44, 255))
    rounded_rect(
        d,
        (2 * K, 2 * K, W - 2 * K, W - 2 * K),
        radius=42 * K,
        outline=(245, 192, 99, 140),
        width=3 * K,
    )

    gold = (245, 192, 99, 255)
    up = (255, 91, 91, 255)
    down = (46, 204, 143, 255)

    def bar(x, y, w, h, color, r=5 * K):
        rounded_rect(d, (x, y, x + w, y + h), radius=r, fill=color)

    # candles (scaled from the 64px svg layout)
    bar(34 * K, 96 * K, 20 * K, 50 * K, up)
    bar(34 * K, 86 * K, 20 * K, 7 * K, (255, 91, 91, 150), r=3 * K)
    bar(65 * K, 73 * K, 20 * K, 73 * K, gold)
    bar(65 * K, 60 * K, 20 * K, 7 * K, (245, 192, 99, 170), r=3 * K)
    bar(96 * K, 107 * K, 20 * K, 39 * K, down)
    bar(96 * K, 96 * K, 20 * K, 7 * K, (46, 204, 143, 150), r=3 * K)

    # trend line
    pts = [(25 * K, 124 * K), (56 * K, 96 * K), (87 * K, 104 * K), (118 * K, 62 * K), (155 * K, 42 * K)]
    d.line(pts, fill=gold, width=7 * K, joint="curve")
    for p in (pts[0], pts[1], pts[2], pts[3], pts[4]):
        pass
    r = 9 * K
    cx, cy = pts[-1]
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=gold)
    r2 = 20 * K
    d.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), outline=(245, 192, 99, 90), width=4 * K)

    for size, name in ((180, "icon-180.png"), (512, "icon-512.png")):
        img.resize((size, size), Image.LANCZOS).save(f"assets/{name}")
        print("wrote assets/" + name)


if __name__ == "__main__":
    main()
