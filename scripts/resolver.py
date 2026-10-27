"""
Omni-Skill Orchestrator: Autonomous Stack & Intent Resolver with Arbitration
Zero-dependency, sub-5ms lookup, automatic conflict resolution and version selection.
"""

import os
import re
import json
import sys
import argparse

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "registry.json")

# Vietnamese to technical terms synonyms map
VI_EN_SYNONYMS = {
    "kiểm tra": ["check", "review", "audit", "scan", "inspect"],
    "đánh giá": ["review", "audit", "eval", "evaluate"],
    "tối ưu": ["optimize", "optimization", "tuning", "performance"],
    "truy vấn": ["query", "queries", "sql"],
    "kiểm thử": ["test", "testing", "tdd", "unit"],
    "viết test": ["test", "testing", "tdd", "unit-test"],
    "bảo mật": ["security", "auth", "vulnerability", "audit"],
    "lỗi": ["error", "bug", "debug", "fix", "troubleshooting"],
    "gỡ lỗi": ["debug", "troubleshooting", "trace"],
    "triển khai": ["deploy", "deployment", "ci", "cd", "docker"],
    "cơ sở dữ liệu": ["database", "sql", "migration", "schema"],
    "tinh giản": ["ponytail", "minimal", "clean", "refactor"],
    "lười": ["ponytail", "minimal", "lazy"],
    "giao diện": ["ui", "frontend", "component", "widget"],
    "di động": ["mobile", "android", "ios", "flutter"],
    "xác thực": ["auth", "authentication", "verification"],
    "tài liệu": ["docs", "documentation"],
    # CSKH & Customer Support
    "khách hàng": ["customer", "client", "support", "ticket"],
    "cskh": ["customer", "support", "client", "service", "helpdesk"],
    "khiếu nại": ["complaint", "dispute", "de-escalation", "ticket"],
    "hoàn tiền": ["refund", "billing"],
    "xoa dịu": ["de-escalation", "deescalation", "empathy", "calm"],
    "tức giận": ["angry", "frustrated", "de-escalation", "escalation"],
    # Hardware & Embedded
    "phần cứng": ["hardware", "embedded", "firmware", "pcb", "circuit"],
    "mạch": ["circuit", "pcb", "schematic", "hardware"],
    "nạp": ["flash", "flashing", "bootloader", "firmware"],
    "dịch": ["translate", "translation", "layman"],
    # Office & Document Productivity
    "ảnh sang chữ": ["ocr", "image", "vision", "text"],
    "chuyển ảnh": ["ocr", "image", "vision", "extract"],
    "ocr": ["ocr", "image", "vision", "extract"],
    "hình ảnh": ["image", "ocr", "screenshot"],
    "chụp": ["screenshot", "image", "ocr"],
    "pdf": ["pdf", "converter", "word", "docx"],
    "pdf sang word": ["pdf", "word", "docx", "converter"],
    "word": ["word", "docx", "document", "pdf"],
    "excel": ["excel", "spreadsheet", "csv", "openpyxl", "pandas"],
    "bảng tính": ["excel", "spreadsheet", "sheets", "csv"],
    "gộp file": ["merge", "excel", "pdf", "combine"],
    "faq": ["faq", "knowledge", "guide", "manual", "curator"],
    "hướng dẫn sử dụng": ["guide", "manual", "faq", "knowledge"],
    "sop": ["sop", "procedure", "knowledge", "faq"],
}

# Domain hierarchy for specificity scoring
SPECIFICITY_MAP = {
    # Web / Frontend
    "nextjs": 4, "remix": 4, "nuxt": 4, "svelte": 3, "vue": 3, "react": 3, "angular": 3,
    "typescript": 2, "javascript": 1, "web": 1,
    # Backend / Frameworks
    "fastapi": 4, "django": 4, "flask": 3, "springboot": 4, "laravel": 4, "express": 3,
    "python": 1, "java": 1, "php": 1, "nodejs": 1, "golang": 1, "rust": 1, "csharp": 1,
    # Mobile
    "flutter": 3, "react-native": 3, "compose": 3, "swiftui": 3, "android": 2, "ios": 2, "dart": 1, "swift": 1, "kotlin": 1,
    # Database / Data
    "bigquery-sql": 5, "bigquery": 3, "prisma": 3, "drizzle": 3, "postgres": 2, "mysql": 2, "database": 1,
    # Review / Standards
    "ponytail": 5, "code-reviewer": 2, "coding-standards": 1,
}

# Scope priority bonus
SCOPE_PRIORITY = {
    "workspace": 40,
    "user_active": 20,
    "plugin": 20,
    "builtin": 15,
    "library": 5
}


def load_registry(registry_path=REGISTRY_PATH):
    if not os.path.exists(registry_path):
        from indexer import build_index
        return build_index(registry_path)
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        
        # Self-healing & auto-update: if files were added/modified, re-index automatically
        from indexer import is_registry_stale, build_index
        if is_registry_stale(registry):
            return build_index(registry_path)
        return registry
    except Exception:
        from indexer import build_index
        return build_index(registry_path)


def detect_workspace_stack(workspace_dir):
    """Inspects workspace marker files and dependencies to extract stack tags."""
    if not workspace_dir or not os.path.exists(workspace_dir):
        return []

    tags = set()
    files = []
    try:
        for entry in os.scandir(workspace_dir):
            files.append(entry.name)
            if entry.is_dir() and entry.name not in [".git", "node_modules", "dist", "build", "venv", ".venv"]:
                try:
                    for sub in os.scandir(entry.path):
                        files.append(f"{entry.name}/{sub.name}")
                except Exception:
                    pass
    except Exception:
        pass

    for f in files:
        base = os.path.basename(f)
        if base == "package.json":
            tags.update(["javascript", "nodejs", "web", "frontend"])
            _parse_package_json(os.path.join(workspace_dir, f), tags)
        elif base == "tsconfig.json":
            tags.add("typescript")
        elif base in ["pyproject.toml", "requirements.txt", "Pipfile"]:
            tags.update(["python", "backend"])
            _parse_python_deps(os.path.join(workspace_dir, f), tags)
        elif base == "Cargo.toml":
            tags.update(["rust", "systems"])
        elif base == "go.mod":
            tags.update(["golang", "go", "backend"])
        elif base == "pubspec.yaml":
            tags.update(["flutter", "dart", "mobile"])
        elif base == "Package.swift":
            tags.update(["swift", "ios", "macos", "mobile"])
        elif base in ["pom.xml", "build.gradle", "build.gradle.kts"]:
            tags.update(["java", "kotlin", "backend"])
            if "kts" in base or "kt" in base:
                tags.add("kotlin")
        elif base == "composer.json":
            tags.update(["php", "backend"])
        elif base in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]:
            tags.update(["docker", "devops", "container"])
        elif base.endswith(".prisma"):
            tags.update(["prisma", "database"])

    return list(tags)


def _parse_package_json(pkg_path, tags):
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            deps = {}
            deps.update(data.get("dependencies", {}))
            deps.update(data.get("devDependencies", {}))
            for dep in deps:
                dep_lower = dep.lower()
                if "react" in dep_lower: tags.add("react")
                if "next" in dep_lower: tags.update(["nextjs", "react"])
                if "vue" in dep_lower: tags.add("vue")
                if "nuxt" in dep_lower: tags.update(["nuxt", "vue"])
                if "svelte" in dep_lower: tags.add("svelte")
                if "tailwind" in dep_lower: tags.add("tailwind")
                if "prisma" in dep_lower: tags.update(["prisma", "database"])
                if "express" in dep_lower: tags.add("express")
                if "fastify" in dep_lower: tags.add("fastify")
    except Exception:
        pass


def _parse_python_deps(req_path, tags):
    try:
        with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().lower()
            if "fastapi" in content: tags.add("fastapi")
            if "django" in content: tags.add("django")
            if "flask" in content: tags.add("flask")
            if "torch" in content or "pytorch" in content: tags.update(["pytorch", "ml", "ai"])
            if "tensorflow" in content: tags.update(["tensorflow", "ml", "ai"])
            if "bigquery" in content: tags.update(["bigquery", "data"])
            if "pandas" in content: tags.update(["pandas", "data"])
    except Exception:
        pass


def compare_versions(v1, v2):
    """Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal/inconclusive."""
    if not v1 or not v2:
        return 0
    nums1 = [int(n) for n in re.findall(r'\d+', str(v1))]
    nums2 = [int(n) for n in re.findall(r'\d+', str(v2))]
    if not nums1 or not nums2:
        return 0
    for i in range(max(len(nums1), len(nums2))):
        n1 = nums1[i] if i < len(nums1) else 0
        n2 = nums2[i] if i < len(nums2) else 0
        if n1 > n2: return 1
        if n1 < n2: return -1
    return 0


def extract_query_tokens(text):
    """Extracts Unicode words, compound phrases, and adds English technical synonyms."""
    text_lower = text.lower()
    raw_words = re.findall(r'\b[\w\-]+\b', text_lower, re.UNICODE)
    tokens = set([w for w in raw_words if len(w) >= 2])
    
    # Expand with synonyms
    for phrase, syns in VI_EN_SYNONYMS.items():
        if phrase in text_lower:
            tokens.update(syns)
            
    return tokens


def resolve_skill(intent_text="", workspace_dir=None, registry=None, top_k=3):
    if registry is None:
        registry = load_registry()

    skills = registry.get("skills", [])
    token_index = registry.get("token_index", {})
    stack_tags = detect_workspace_stack(workspace_dir)

    query_tokens = extract_query_tokens(intent_text) if intent_text else set()
    all_target_tokens = query_tokens.union(set(stack_tags))

    candidate_scores = {}

    for token in all_target_tokens:
        token_lower = token.lower()
        matching_indices = token_index.get(token_lower, [])
        is_query = token_lower in query_tokens
        is_stack = token_lower in stack_tags
        
        weight = 15 if is_query else 6
        if is_query and is_stack:
            weight = 25

        for idx in matching_indices:
            candidate_scores[idx] = candidate_scores.get(idx, 0) + weight

    candidates = []
    for idx, score in candidate_scores.items():
        s = skills[idx]
        name = s["name"].lower()
        desc = s["description"].lower()

        # Bonus for exact word or substring in name
        for qt in query_tokens:
            if qt and qt == name:
                score += 80
            elif qt and qt in name:
                score += 35
            elif qt and qt in desc:
                score += 10

        # Stack alignment bonus
        for st in stack_tags:
            if st and (st in name or st in desc):
                score += 20

        # Scope priority bonus
        score += SCOPE_PRIORITY.get(s["source_type"], 5)

        # Cloud/Vendor penalty if specific vendor/service is NOT requested
        for vendor in ["gcs", "firebase", "gcp", "aws", "azure", "bigquery", "bigtable", "composer", "datastore"]:
            if vendor in name and vendor not in query_tokens and vendor not in stack_tags:
                score -= 40

        # Quality bonus
        score += (s.get("quality_score", 50) / 10.0)

        # Specificity score: only boost if the domain is explicitly in query or detected in workspace stack
        spec = 0
        for dom, pts in SPECIFICITY_MAP.items():
            if dom in name:
                # If domain is relevant to current task or workspace
                if dom in query_tokens or dom in stack_tags or any(st in dom for st in stack_tags):
                    spec = max(spec, pts)
                else:
                    # Mild default specificity
                    spec = max(spec, 1)
        score += spec * 10

        candidates.append({
            "skill": s,
            "raw_score": score,
            "specificity": spec,
        })

    if not candidates:
        for s in skills:
            if s["name"] == "ponytail":
                return [{"skill": s, "raw_score": 100, "arbitration_reason": "Defaulted to Ponytail (YAGNI & minimal changes)"}]
            if s["name"] == "coding-standards":
                return [{"skill": s, "raw_score": 100, "arbitration_reason": "Defaulted to general coding standards"}]
        return []

    # Sort descending
    candidates.sort(key=lambda c: c["raw_score"], reverse=True)

    # Arbitration
    top_candidates = candidates[:20]
    arbitrated = _arbitrate_candidates(top_candidates, stack_tags, query_tokens)

    return arbitrated[:top_k]


def _arbitrate_candidates(candidates, stack_tags, query_tokens):
    selected = []
    seen_domains = {}

    for cand in candidates:
        s = cand["skill"]
        name = s["name"]
        spec = cand["specificity"]
        ver = s.get("version", "1.0.0")

        domain_key = None
        for dom in SPECIFICITY_MAP:
            if dom in name:
                domain_key = dom
                break
        if not domain_key:
            domain_key = name.split("-")[0]

        if domain_key in seen_domains:
            existing = seen_domains[domain_key]
            # Higher score wins if within same domain
            if cand["raw_score"] > existing["raw_score"] + 10:
                reason = f"Arbitration: Selected {name} (Score: {cand['raw_score']:.1f}) over {existing['skill']['name']} (Score: {existing['raw_score']:.1f})"
                cand["arbitration_reason"] = reason
                selected.remove(existing)
                selected.append(cand)
                seen_domains[domain_key] = cand
                continue
            elif spec > existing["specificity"]:
                reason = f"Arbitration: Replaced {existing['skill']['name']} with {name} (Higher specificity: {spec} > {existing['specificity']})"
                cand["arbitration_reason"] = reason
                selected.remove(existing)
                selected.append(cand)
                seen_domains[domain_key] = cand
                continue
            elif spec == existing["specificity"]:
                v_cmp = compare_versions(ver, existing["skill"].get("version"))
                if v_cmp > 0:
                    reason = f"Arbitration: Selected {name} (v{ver}) over older {existing['skill']['name']} (v{existing['skill'].get('version')})"
                    cand["arbitration_reason"] = reason
                    selected.remove(existing)
                    selected.append(cand)
                    seen_domains[domain_key] = cand
                    continue
                else:
                    continue
            else:
                continue

        cand["arbitration_reason"] = f"Optimal candidate for domain '{domain_key}'"
        seen_domains[domain_key] = cand
        selected.append(cand)

    return selected


def format_resolution_output(results, is_json=False):
    if is_json:
        return json.dumps(results, indent=2, ensure_ascii=False)
    
    if not results:
        return "No matching skills found."

    lines = []
    lines.append(f"🎯 Omni-Skill Orchestrator: Found {len(results)} optimal skill(s)\n")
    for i, res in enumerate(results, 1):
        s = res["skill"]
        plugin_info = f" ({s.get('plugin_name')})" if s.get('plugin_name') else ""
        lines.append(f"[{i}] {s['name']} (v{s.get('version', '1.0')})")
        lines.append(f"    - Source: {s['source_type'].upper()}{plugin_info}")
        lines.append(f"    - Path: {s['path']}")
        lines.append(f"    - Reason: {res.get('arbitration_reason', 'Top match')}")
        lines.append(f"    - Description: {s['description'][:120]}...\n")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Omni-Skill Resolver CLI")
    parser.add_argument("--intent", "-i", type=str, default="", help="User prompt or intent")
    parser.add_argument("--workspace", "-w", type=str, default="", help="Workspace directory")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--top", "-k", type=int, default=3, help="Top K results")
    args = parser.parse_args()

    res = resolve_skill(args.intent, args.workspace, top_k=args.top)
    print(format_resolution_output(res, args.json))
