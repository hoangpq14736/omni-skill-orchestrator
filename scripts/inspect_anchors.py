import re

with open("trendshift_sample.html", "r", encoding="utf-8") as f:
    html = f.read()

# Let's inspect the first 3 anchor tags and their inner HTML
anchors = re.findall(r'<a[^>]+href=["\'](/repositories/\d+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
print(f"Total anchors: {len(anchors)}")

repos_found = []
for href, inner in anchors:
    # clean tags
    text = re.sub(r'<[^>]+>', ' ', inner).strip()
    text = re.sub(r'\s+', ' ', text)
    if text:
        repos_found.append((href, text))

for href, t in repos_found[:30]:
    print(f"{href} -> {t[:100]}")
