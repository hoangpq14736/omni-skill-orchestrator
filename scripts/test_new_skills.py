import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from resolver import resolve_skill

res1 = resolve_skill('cần điều phối subagent chạy song song theo plan')
print('Query 1 Top Skill:', res1[0]['skill']['name'], f"({res1[0]['skill']['source_type']})")

res2 = resolve_skill('gặp bug khó cần tìm root cause và systematic debugging')
print('Query 2 Top Skill:', res2[0]['skill']['name'], f"({res2[0]['skill']['source_type']})")

res3 = resolve_skill('thiết kế website chống AI slop theo chuẩn taste-skill')
print('Query 3 Top Skill:', res3[0]['skill']['name'], f"({res3[0]['skill']['source_type']})")
