"""
Omni-Skill Orchestrator: Autonomous Stack & Intent Resolver with Arbitration
Zero-dependency, sub-5ms lookup, automatic conflict resolution and version selection.
"""

import os
import re
import json
import sys
import argparse
import datetime
import unicodedata

# Ensure script directory is on sys.path for sibling imports (indexer, etc.)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "registry.json")
LEARNED_PATH = os.path.join(os.path.dirname(__file__), "learned_affinities.json")

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
    "nhúng": ["embedded", "firmware", "hardware", "baremetal"],
    "mạch": ["circuit", "pcb", "schematic", "hardware"],
    "nạp": ["flash", "flashing", "bootloader", "firmware"],
    "máy chủ": ["server", "vps", "linux", "sysadmin", "infrastructure"],
    "dịch": ["translate", "translation", "layman"],
    # Office & Document Productivity
    "trình chiếu": ["slides", "presentation", "deck"],
    "thuyết trình": ["slides", "presentation", "deck"],
    "tiện ích mở rộng": ["extension", "chrome-extension", "plugin"],
    "khả năng tiếp cận": ["a11y", "accessibility", "aria"],
    "ảnh sang chữ": ["ocr", "image", "vision", "text"],
    "chuyển ảnh": ["ocr", "image", "vision", "extract"],
    "ocr": ["ocr", "image", "vision", "extract"],
    "hình ảnh": ["image", "ocr", "screenshot"],
    "chụp": ["screenshot", "image", "ocr"],
    "pdf": ["pdf"],
    "pdf sang word": ["pdf", "word", "docx", "converter"],
    "word": ["word", "docx", "document"],
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
    "chrome-extensions": 5, "chrome": 3, "typescript": 2, "javascript": 1, "web": 1,
    # Backend / Frameworks
    "fastapi": 4, "django": 4, "flask": 3, "springboot": 4, "laravel": 4, "express": 3,
    "python": 1, "java": 1, "php": 1, "nodejs": 1, "golang": 1, "rust": 1, "csharp": 1,
    # Mobile
    "flutter": 3, "react-native": 3, "compose": 3, "swiftui": 3, "android": 2, "ios": 2, "dart": 1, "swift": 1, "kotlin": 1,
    # Database / Data
    "bigquery-sql": 5, "bigquery": 3, "prisma": 4, "drizzle": 3, "postgres": 2, "mysql": 2, "database": 1,
    # Review / Standards
    "ponytail": 5, "code-reviewer": 2, "coding-standards": 1,
    # Hardware & Embedded
    "baremetal": 5, "embedded": 4, "firmware": 3,
    # Office & Google Suite
    "gslides": 4, "slides": 3, "gsheets": 4, "sheets": 3, "gdocs": 4, "docs": 2, "gcalendar": 4, "calendar": 3,
    # Accessibility & Quality
    "a11y": 4, "accessibility": 4,
}

# Scope priority bonus
SCOPE_PRIORITY = {
    "workspace": 40,
    "user_active": 20,
    "plugin": 20,
    "builtin": 15,
    "library": 5
}

# Domain Inferred Rules (Implicit Entailment Graph)
DOMAIN_INFERRED_RULES = {
    "web": [
        "Web Security Invariants (OWASP Top 10, XSS/CSRF Prevention, Content-Security-Policy)",
        "Input Trust Boundary (Never trust client-supplied params; sanitize all inputs)",
        "Modern Web Standards (Semantic HTML, Accessible ARIA, no obsolete patterns)"
    ],
    "frontend": [
        "Client-Side State Integrity (No plaintext secrets or private keys in JS bundle)",
        "Accessibility Invariants (Keyboard navigation, contrast, tap targets)"
    ],
    "python": [
        "Reliable Error Handling (Fail loudly with diagnostic context; never silent pass)",
        "Standard Library Precedence (Zero-dependency first; YAGNI)"
    ],
    "fastapi": [
        "FastAPI Lifespan Pattern (Use lifespan context manager, avoid deprecated on_event)",
        "Pydantic v2 Strict Validation at all ingress/egress boundaries",
        "Upload Security (Magic bytes check, UUID storage, no path traversal)"
    ],
    "database": [
        "SQL Injection Immunity (Parameterized queries only; no raw string concatenation)",
        "Transactional Safety (Atomic operations, migration reversibility, no raw drop table)"
    ],
    "docker": [
        "Least Privilege Container (Run as non-root user; minimal base images)",
        "Multi-Stage Build (Zero build tools or secrets left in final production image)"
    ],
    "vps": [
        "Host Security Guardrails (Non-root user, UFW/Fail2ban, key-only SSH)",
        "Resource Quotas (cgroups limits, swap/zram, process supervision)"
    ],
    "embedded": [
        "Hardware Safety Guardrails (Safe voltage, timing delays, timeout watchdog)",
        "Memory Bounds & Safe Register Access"
    ],
    "cad": [
        "Design for Additive Manufacturing (Check overhangs, wall thickness, manifold geometry)",
        "Parametric Constraint Integrity"
    ]
}

# Domain Inferred MCP Drivers (Plug-and-Play Tools)
DOMAIN_INFERRED_MCP = {
    "web": ["chrome-devtools (DOM, Network, A11y, Performance inspection)"],
    "frontend": ["chrome-devtools (Console & Element inspector)"],
    "cad": ["solidcraft (Parametric 3D CAD engine)", "text-to-cad_cad"],
    "cloud": ["gcloud (Cloud platform CLI validation & guardrails)"],
    "api": ["gemini-api_gemini-api-docs (Upstream live documentation inspection)"]
}


RULE_DOMAIN_ALIASES = {
    "web": ["web", "html", "css", "frontend", "dom", "browser", "lcp", "a11y", "chrome"],
    "frontend": ["frontend", "ui", "react", "vue", "svelte", "nextjs", "component"],
    "python": ["python", "py", "fastapi", "django", "flask"],
    "fastapi": ["fastapi", "pydantic", "starlette", "restful", "api"],
    "database": ["database", "sql", "postgres", "postgresql", "mysql", "prisma", "migration", "sqlite", "bigquery"],
    "docker": ["docker", "container", "compose", "dockerfile"],
    "vps": ["vps", "server", "linux", "ubuntu", "debian", "ssh", "fail2ban", "ufw"],
    "embedded": ["embedded", "hardware", "firmware", "baremetal", "stm32", "esp32", "serial", "uart", "modbus", "rust"],
    "cad": ["cad", "3d", "step", "stl", "manifold", "solidcraft", "3mf", "overhang"]
}


def infer_domain_rules_and_mcp(target_tokens):
    """
    Cognitive Entailment Graph:
    Infers mandatory security, reliability invariants and relevant MCP tools
    even if the user prompt omitted explicit keywords.
    """
    inferred_rules = []
    inferred_mcp = []
    
    tokens_lower = set(t.lower() for t in target_tokens)
    
    for domain, rules in DOMAIN_INFERRED_RULES.items():
        aliases = RULE_DOMAIN_ALIASES.get(domain, [domain])
        if any(a in tokens_lower or any(a in t for t in tokens_lower) for a in aliases):
            for r in rules:
                if r not in inferred_rules:
                    inferred_rules.append(r)
                    
    for domain, tools in DOMAIN_INFERRED_MCP.items():
        aliases = RULE_DOMAIN_ALIASES.get(domain, [domain])
        if any(a in tokens_lower or any(a in t for t in tokens_lower) for a in aliases):
            for tool in tools:
                if tool not in inferred_mcp:
                    inferred_mcp.append(tool)
                    
    # Always enforce Kernel Ring 0 Core Invariants
    ring0_invariants = [
        "Kernel Ring 0 Security (Zero-trust, validate input at trust boundaries, no secrets)",
        "Kernel Ring 0 Reliability (Fail loudly, immutability, no silent exception swallow)",
        "Kernel Ring 0 Ponytail (Shortest working diff, YAGNI, standard library first)"
    ]
    for inv in reversed(ring0_invariants):
        if inv not in inferred_rules:
            inferred_rules.insert(0, inv)
            
    return inferred_rules, inferred_mcp


def build_cognitive_pre_flight(intent_text, workspace_dir, top_skills, inferred_rules, inferred_mcp):
    """
    Constructs the 4-Dimensional Cognitive Pre-Flight Assessment (Lợi - Hại - Đủ - Thiếu).
    """
    top_name = top_skills[0]["skill"]["name"] if top_skills else "ponytail"
    
    return {
        "loi_value": f"Apply minimal diff via '{top_name}' prioritizing standard library and zero bloat.",
        "hai_risks": [
            "Breaking existing callers or schemas without backwards compatibility",
            "Exposing secrets or introducing unvalidated trust boundaries"
        ],
        "du_completeness": [
            "Ensure full coverage across callers, configuration, and automated assertions",
            "Verify all error states are handled with diagnostic context"
        ],
        "thieu_implicit": {
            "mandatory_inferred_rules": inferred_rules[:3],
            "suggested_mcp_drivers": inferred_mcp if inferred_mcp else ["Standard OS/Shell tools"]
        }
    }


def load_learned_affinities(path=None):
    """Loads learned affinities and stats from disk in <0.2ms."""
    path = path or LEARNED_PATH
    if not os.path.exists(path):
        return {"version": "1.1.0", "affinities": {}, "skill_stats": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"version": "1.1.0", "affinities": {}, "skill_stats": {}}
            data.setdefault("affinities", {})
            data.setdefault("skill_stats", {})
            return data
    except Exception:
        return {"version": "1.1.0", "affinities": {}, "skill_stats": {}}


def save_learned_affinities(data, path=None):
    """Safely saves learned affinities and stats to disk."""
    path = path or LEARNED_PATH
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        temp_path = f"{path}.tmp.{os.getpid()}"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if os.path.exists(path):
            os.replace(temp_path, path)
        else:
            os.rename(temp_path, path)
        return True
    except Exception:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False


def record_feedback(intent_text="", workspace_dir=None, chosen_skill="", rejected_skills=None, affinities_path=None):
    """
    Self-Learning / Meta-Evolution:
    Records positive reinforcement for chosen_skill and optional dampening for rejected_skills.
    Learns associations between target tokens (intent + workspace markers) and skill name.
    """
    if not chosen_skill:
        return {"status": "error", "message": "chosen_skill is required"}

    path = affinities_path or LEARNED_PATH
    data = load_learned_affinities(path)
    affinities = data["affinities"]
    stats = data["skill_stats"]

    # Gather target tokens
    query_tokens = extract_query_tokens(intent_text) if intent_text else set()
    stack_tags = set(detect_workspace_stack(workspace_dir)) if workspace_dir else set()
    all_tokens = query_tokens.union(stack_tags)

    # Fallback to tokens from skill name if prompt and stack are empty
    if not all_tokens:
        all_tokens = set(re.findall(r'\b[\w\-]+\b', chosen_skill.lower()))

    # Positive reinforcement for chosen skill
    chosen_lower = chosen_skill.lower()
    for tok in all_tokens:
        tok_lower = tok.lower()
        if tok_lower not in affinities:
            affinities[tok_lower] = {}
        curr = affinities[tok_lower].get(chosen_lower, 0.0)
        # Boost by +15.0 per feedback event, capped at +60.0 to prevent runaway bias
        affinities[tok_lower][chosen_lower] = min(60.0, curr + 15.0)

    # Optional dampening for rejected skills
    if rejected_skills:
        if isinstance(rejected_skills, str):
            rejected_skills = [rejected_skills]
        for rej in rejected_skills:
            rej_lower = rej.lower()
            if rej_lower and rej_lower != chosen_lower:
                for tok in all_tokens:
                    tok_lower = tok.lower()
                    if tok_lower in affinities and rej_lower in affinities[tok_lower]:
                        curr = affinities[tok_lower][rej_lower]
                        affinities[tok_lower][rej_lower] = max(-30.0, curr - 10.0)

    # Update stats
    skill_stat = stats.setdefault(chosen_lower, {"chosen_count": 0, "rejected_count": 0, "last_chosen": ""})
    skill_stat["chosen_count"] += 1
    skill_stat["last_chosen"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if rejected_skills:
        for rej in rejected_skills:
            rej_lower = rej.lower()
            if rej_lower and rej_lower != chosen_lower:
                rstat = stats.setdefault(rej_lower, {"chosen_count": 0, "rejected_count": 0, "last_chosen": ""})
                rstat["rejected_count"] += 1

    data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_learned_affinities(data, path)

    return {
        "status": "ok",
        "chosen_skill": chosen_lower,
        "tokens_boosted": sorted(list(all_tokens)),
        "total_associations": len(affinities)
    }


def reset_learning(affinities_path=None):
    """Resets the learned affinities database."""
    path = affinities_path or LEARNED_PATH
    data = {"version": "1.1.0", "affinities": {}, "skill_stats": {}}
    save_learned_affinities(data, path)
    return {"status": "ok", "message": "Learned affinities database reset"}


def get_learned_stats(affinities_path=None):
    """Returns self-learning statistics."""
    path = affinities_path or LEARNED_PATH
    data = load_learned_affinities(path)
    affinities = data.get("affinities", {})
    stats = data.get("skill_stats", {})
    
    top_reinforced = sorted(
        stats.items(),
        key=lambda item: item[1].get("chosen_count", 0),
        reverse=True
    )
    return {
        "total_tokens_learned": len(affinities),
        "total_tracked_skills": len(stats),
        "top_skills": top_reinforced[:10],
        "updated_at": data.get("updated_at", "Never")
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
        elif base.endswith(".html") or base == "index.html":
            tags.update(["web", "frontend", "html"])
        elif base.endswith(".py") and "python" not in tags:
            tags.update(["python"])
        elif base == "plugin.json":
            tags.update(["plugin", "antigravity", "customization"])

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


def strip_accents(text):
    """Normalizes and strips Vietnamese diacritics for cross-lingual query resilience."""
    if not text:
        return ""
    text_nfd = unicodedata.normalize('NFD', text)
    text_clean = ''.join(c for c in text_nfd if unicodedata.category(c) != 'Mn')
    text_clean = text_clean.replace('đ', 'd').replace('Đ', 'D')
    return unicodedata.normalize('NFC', text_clean)


def extract_query_tokens(text):
    """Extracts Unicode words, compound phrases, strips accents, and expands technical synonyms."""
    if not text:
        return set()
    text_lower = text.lower()
    text_unaccented = strip_accents(text_lower)
    raw_words = re.findall(r'\b[\w\-]+\b', text_lower, re.UNICODE)
    raw_words_unaccented = re.findall(r'\b[\w\-]+\b', text_unaccented, re.UNICODE)
    tokens = set([w for w in raw_words + raw_words_unaccented if len(w) >= 2])
    
    # Expand with synonyms (matches both accented and unaccented variations)
    for phrase, syns in VI_EN_SYNONYMS.items():
        phrase_unaccented = strip_accents(phrase)
        if phrase in text_lower or phrase_unaccented in text_unaccented:
            tokens.update(syns)
            
    return tokens


def resolve_skill(intent_text="", workspace_dir=None, registry=None, top_k=3, affinities_path=None, unified=False):
    if registry is None:
        registry = load_registry()

    skills = registry.get("skills", [])
    token_index = registry.get("token_index", {})
    stack_tags = detect_workspace_stack(workspace_dir)

    # Load learned affinities for meta-evolution (<0.2ms)
    learned_data = load_learned_affinities(affinities_path)
    affinities = learned_data.get("affinities", {})

    query_tokens = extract_query_tokens(intent_text) if intent_text else set()
    all_target_tokens = query_tokens.union(set(stack_tags))

    # Cognitive Entailment: Infer mandatory rules & MCP drivers
    inferred_rules, inferred_mcp = infer_domain_rules_and_mcp(all_target_tokens)

    # Workspace Assimilator: Discover local skills and rules non-destructively
    if workspace_dir and os.path.exists(workspace_dir):
        try:
            from assimilator import assimilate_workspace
            workspace_data = assimilate_workspace(workspace_dir)
            for wr in workspace_data.get("rules", []):
                rule_str = f"Workspace Rule ({wr['source']}): {wr['summary']}"
                if rule_str not in inferred_rules:
                    inferred_rules.append(rule_str)
        except Exception:
            pass

    candidate_scores = {}
    name_to_idx = {s["name"].lower(): i for i, s in enumerate(skills)}

    for token in all_target_tokens:
        token_lower = token.lower()
        matching_indices = set(token_index.get(token_lower, []))
        is_query = token_lower in query_tokens
        is_stack = token_lower in stack_tags
        
        weight = 15 if is_query else 6
        if is_query and is_stack:
            weight = 25

        for idx in matching_indices:
            candidate_scores[idx] = candidate_scores.get(idx, 0) + weight

        # Pull candidates learned from past agent/user feedback for this token
        tok_affinities = affinities.get(token_lower, {})
        for aff_skill, aff_weight in tok_affinities.items():
            if aff_skill in name_to_idx:
                s_idx = name_to_idx[aff_skill]
                candidate_scores[s_idx] = candidate_scores.get(s_idx, 0) + max(0, int(aff_weight))

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

        # Meta-Learned affinity boost across all target tokens
        learned_boost = 0.0
        for t in all_target_tokens:
            t_lower = t.lower()
            if t_lower in affinities and name in affinities[t_lower]:
                learned_boost += affinities[t_lower][name]
        
        # Bounded between -40.0 and +80.0
        learned_boost = max(-40.0, min(80.0, learned_boost))
        score += learned_boost

        candidates.append({
            "skill": s,
            "raw_score": score,
            "specificity": spec,
            "learned_boost": learned_boost
        })

    # Merge assimilated workspace skills into candidate pool
    if workspace_dir and 'workspace_data' in locals() and workspace_data:
        for wsk in workspace_data.get("skills", []):
            wsk_name = wsk["name"].lower()
            wsk_desc = wsk["description"].lower()
            wsk_tokens = set(wsk.get("tokens", []))
            common = wsk_tokens.intersection(all_target_tokens)
            if common or wsk_name in query_tokens or any(qt in wsk_name for qt in query_tokens if len(qt) > 2):
                ws_score = len(common) * 15 + SCOPE_PRIORITY.get("workspace", 40) + 10
                for qt in query_tokens:
                    if qt and qt == wsk_name:
                        ws_score += 80
                    elif qt and qt in wsk_name:
                        ws_score += 35
                    elif qt and qt in wsk_desc:
                        ws_score += 10
                candidates.append({
                    "skill": wsk,
                    "raw_score": ws_score,
                    "specificity": 5,
                    "learned_boost": 0.0
                })

    if not candidates:
        default_res = []
        for s in skills:
            if s["name"] == "ponytail":
                default_res = [{"skill": s, "raw_score": 100, "arbitration_reason": "Defaulted to Ponytail (YAGNI & minimal changes)"}]
                break
        if not default_res:
            for s in skills:
                if s["name"] == "coding-standards":
                    default_res = [{"skill": s, "raw_score": 100, "arbitration_reason": "Defaulted to general coding standards"}]
                    break
        
        pre_flight = build_cognitive_pre_flight(intent_text, workspace_dir, default_res, inferred_rules, inferred_mcp)
        try:
            from dual_tier import calculate_task_complexity
            tier_assessment = calculate_task_complexity(intent_text, workspace_dir)
        except Exception:
            tier_assessment = {
                "score": 0, "tier": 1, "tier_name": "L1 Reflex",
                "recommend_subagent": False, "subagent_role": None, "factors": []
            }
        try:
            from experiential_memory import recall_traces
            proven_traces = recall_traces(intent_text, workspace_dir=workspace_dir, top_k=2)
        except Exception:
            proven_traces = []
        try:
            from mcp_gateway import route_mcp_tool
            dynamic_mcp_tools = route_mcp_tool(intent_text, top_k=2)
        except Exception:
            dynamic_mcp_tools = []

        if unified:
            return {
                "skills": default_res,
                "inferred_rules": inferred_rules,
                "suggested_mcp": inferred_mcp,
                "cognitive_pre_flight": pre_flight,
                "tier_assessment": tier_assessment,
                "proven_traces": proven_traces,
                "mcp_tools": dynamic_mcp_tools
            }
        for cand in default_res:
            cand["inferred_rules"] = inferred_rules
            cand["suggested_mcp"] = inferred_mcp
            cand["cognitive_pre_flight"] = pre_flight
            cand["tier_assessment"] = tier_assessment
            cand["proven_traces"] = proven_traces
            cand["mcp_tools"] = dynamic_mcp_tools
        return default_res

    # Sort descending
    candidates.sort(key=lambda c: c["raw_score"], reverse=True)

    # Arbitration
    top_candidates = candidates[:20]
    arbitrated = _arbitrate_candidates(top_candidates, stack_tags, query_tokens)
    top_skills = arbitrated[:top_k]

    pre_flight = build_cognitive_pre_flight(intent_text, workspace_dir, top_skills, inferred_rules, inferred_mcp)

    # Dual-Tier Cognitive Routing & Quota Guard Assessment (<0.2ms)
    try:
        from dual_tier import calculate_task_complexity
        tier_assessment = calculate_task_complexity(intent_text, workspace_dir)
    except Exception:
        tier_assessment = {
            "score": 0, "tier": 1, "tier_name": "L1 Reflex",
            "recommend_subagent": False, "subagent_role": None, "factors": []
        }

    # Cross-Session Experiential Memory Recall (<0.3ms)
    try:
        from experiential_memory import recall_traces
        proven_traces = recall_traces(intent_text, workspace_dir=workspace_dir, top_k=2)
    except Exception:
        proven_traces = []

    # Dynamic MCP Tool Routing via Omni-MCP Virtual Bus (<0.3ms)
    try:
        from mcp_gateway import route_mcp_tool
        dynamic_mcp_tools = route_mcp_tool(intent_text, top_k=2)
    except Exception:
        dynamic_mcp_tools = []

    if unified:
        return {
            "skills": top_skills,
            "inferred_rules": inferred_rules,
            "suggested_mcp": inferred_mcp,
            "cognitive_pre_flight": pre_flight,
            "tier_assessment": tier_assessment,
            "proven_traces": proven_traces,
            "mcp_tools": dynamic_mcp_tools
        }

    for cand in top_skills:
        cand["inferred_rules"] = inferred_rules
        cand["suggested_mcp"] = inferred_mcp
        cand["cognitive_pre_flight"] = pre_flight
        cand["tier_assessment"] = tier_assessment
        cand["proven_traces"] = proven_traces
        cand["mcp_tools"] = dynamic_mcp_tools

    return top_skills


def _arbitrate_candidates(candidates, stack_tags, query_tokens):
    selected = []
    seen_domains = {}

    for cand in candidates:
        s = cand["skill"]
        name = s["name"]
        spec = cand["specificity"]
        ver = s.get("version", "1.0.0")
        learned_boost = cand.get("learned_boost", 0.0)
        boost_suffix = f" [Meta-Boost: +{learned_boost:.1f}]" if learned_boost > 0 else ""

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
                reason = f"Arbitration: Selected {name} (Score: {cand['raw_score']:.1f}) over {existing['skill']['name']} (Score: {existing['raw_score']:.1f}){boost_suffix}"
                cand["arbitration_reason"] = reason
                selected.remove(existing)
                selected.append(cand)
                seen_domains[domain_key] = cand
                continue
            elif spec > existing["specificity"]:
                reason = f"Arbitration: Replaced {existing['skill']['name']} with {name} (Higher specificity: {spec} > {existing['specificity']}){boost_suffix}"
                cand["arbitration_reason"] = reason
                selected.remove(existing)
                selected.append(cand)
                seen_domains[domain_key] = cand
                continue
            elif spec == existing["specificity"]:
                v_cmp = compare_versions(ver, existing["skill"].get("version"))
                if v_cmp > 0:
                    reason = f"Arbitration: Selected {name} (v{ver}) over older {existing['skill']['name']} (v{existing['skill'].get('version')}){boost_suffix}"
                    cand["arbitration_reason"] = reason
                    selected.remove(existing)
                    selected.append(cand)
                    seen_domains[domain_key] = cand
                    continue
                else:
                    continue
            else:
                continue

        cand["arbitration_reason"] = f"Optimal candidate for domain '{domain_key}'{boost_suffix}"
        seen_domains[domain_key] = cand
        selected.append(cand)

    return selected


def format_resolution_output(results, is_json=False):
    if is_json:
        return json.dumps(results, indent=2, ensure_ascii=False)
    
    if not results:
        return "No matching resources found."

    lines = []
    lines.append("⚡ OMNI-KERNEL v2.0 UNIFIED RESOURCE RESOLUTION\n" + "=" * 65)

    # If results is unified dict
    if isinstance(results, dict):
        skills = results.get("skills", [])
        rules = results.get("inferred_rules", [])
        mcps = results.get("suggested_mcp", [])
        pre_flight = results.get("cognitive_pre_flight", {})
    else:
        skills = results
        rules = skills[0].get("inferred_rules", []) if skills else []
        mcps = skills[0].get("suggested_mcp", []) if skills else []
        pre_flight = skills[0].get("cognitive_pre_flight", {}) if skills else {}

    # 1. Optimal Skills
    lines.append(f"\n1. OPTIMAL SKILLS (Process / Logic Layer - {len(skills)} found):")
    for i, res in enumerate(skills, 1):
        s = res["skill"]
        plugin_info = f" ({s.get('plugin_name')})" if s.get('plugin_name') else ""
        lines.append(f"   [{i}] {s['name']} (v{s.get('version', '1.0')})")
        lines.append(f"       - Source: {s['source_type'].upper()}{plugin_info}")
        lines.append(f"       - Path: {s['path']}")
        lines.append(f"       - Reason: {res.get('arbitration_reason', 'Top match')}")

    # 2. Inferred Rules
    lines.append(f"\n2. INFERRED KERNEL RULES & INVARIANTS (Security & Reliability):")
    for r in rules:
        lines.append(f"   🛡️ {r}")

    # 3. Suggested MCP Tool Drivers
    lines.append(f"\n3. SUGGESTED MCP TOOL DRIVERS (Dynamic I/O Bus):")
    for m in (mcps or ["Standard Workspace Environment"]):
        lines.append(f"   🔌 {m}")

    # 4. Cognitive Pre-Flight Loop
    if pre_flight:
        lines.append(f"\n4. COGNITIVE PRE-FLIGHT ASSESSMENT (Tự vấn Lợi - Hại - Đủ - Thiếu):")
        lines.append(f"   🧠 LỢI (Value & Simplicity): {pre_flight.get('loi_value', 'Minimal diff')}")
        lines.append(f"   ⚠️ HẠI (Risks to Prevent): {'; '.join(pre_flight.get('hai_risks', []))}")
        lines.append(f"   ✅ ĐỦ (Completeness Check): {'; '.join(pre_flight.get('du_completeness', []))}")
        thieu_rules = pre_flight.get("thieu_implicit", {}).get("mandatory_inferred_rules", [])
        lines.append(f"   🔍 THIẾU (Implicitly Inferred): {len(thieu_rules)} domain guardrails auto-attached.\n")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Omni-Kernel v2.0 Unified Resource Resolver CLI")
    parser.add_argument("--intent", "-i", type=str, default="", help="User prompt or intent")
    parser.add_argument("--workspace", "-w", type=str, default="", help="Workspace directory")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--top", "-k", type=int, default=3, help="Top K results")
    parser.add_argument("--unified", "-u", action="store_true", help="Output unified dictionary with skills, rules, mcp, preflight")
    parser.add_argument("--feedback", "-f", type=str, default="", help="Reinforce feedback for chosen skill")
    parser.add_argument("--reject", "-r", type=str, default="", help="Dampen affinity for rejected skill")
    parser.add_argument("--learn-stats", action="store_true", help="Display self-learning memory statistics")
    parser.add_argument("--reset-learning", action="store_true", help="Reset learned affinities memory")
    parser.add_argument("--last", action="store_true", help="Inspect the most recent Omni-Kernel hook activation")
    args = parser.parse_args()

    if args.last:
        last_file = os.path.join(os.path.dirname(__file__), "last_activation.json")
        if not os.path.exists(last_file):
            print("ℹ️ No previous hook activations recorded yet.")
            sys.exit(0)
        with open(last_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("⚡ OMNI-KERNEL LAST ACTIVATION INSPECTOR\n" + "=" * 65)
            print(f"🕒 Timestamp: {data.get('timestamp')}")
            print(f"💬 Prompt:    {data.get('user_input')}")
            print(f"📂 Workspace: {data.get('workspace_dir')}")
            tier = data.get("tier_assessment", {})
            t_name = tier.get("tier_name", "L1 Reflex")
            print(f"⚡ Cognitive Tier: {t_name} (Score: {tier.get('score', 0)}/100 - {tier.get('quota_guard', 'Active')})")
            if tier.get("factors"):
                print(f"   Triggers: {'; '.join(tier.get('factors', []))}")
            print(f"\n🎯 Top Candidate: {data.get('top_skill')}")
            for i, s in enumerate(data.get("skills", []), 1):
                reason = f" ({s.get('arbitration_reason')})" if s.get('arbitration_reason') else ""
                print(f"   [{i}] {s.get('name')} (v{s.get('version', '1.0')}, {s.get('source_type')}) - Score: {s.get('raw_score')}{reason}")
            print(f"\n🛡️ Active Inferred Rules ({len(data.get('inferred_rules', []))}):")
            for r in data.get("inferred_rules", []):
                print(f"   - {r}")
            print(f"\n🔌 Suggested MCP Tools:")
            for m in (data.get("suggested_mcp", []) or ["Standard Workspace Environment"]):
                print(f"   - {m}")
        sys.exit(0)

    if args.reset_learning:
        res = reset_learning()
        print(f"✅ {res['message']}")
        sys.exit(0)

    if args.learn_stats:
        stats = get_learned_stats()
        print("📊 Omni-Skill Self-Learning Statistics:")
        print(f"   - Total Learned Token Associations: {stats['total_tokens_learned']}")
        print(f"   - Total Skills Tracked: {stats['total_tracked_skills']}")
        print(f"   - Last Evolved: {stats['updated_at']}")
        if stats['top_skills']:
            print("   - Top Reinforced Skills:")
            for sk, sdata in stats['top_skills']:
                print(f"     * {sk}: chosen {sdata.get('chosen_count', 0)} times (rejected {sdata.get('rejected_count', 0)})")
        else:
            print("   - No skill feedback recorded yet.")
        sys.exit(0)

    if args.feedback:
        fb_res = record_feedback(args.intent, args.workspace, args.feedback, rejected_skills=args.reject)
        if not args.json:
            print(f"🎯 Omni-Skill Self-Learning: Feedback recorded successfully!")
            print(f"   - Reinforced Skill: {fb_res.get('chosen_skill')}")
            print(f"   - Boosted Tokens: {fb_res.get('tokens_boosted')}")
            print(f"   - Total Learned Associations: {fb_res.get('total_associations')}\n")

    res = resolve_skill(args.intent, args.workspace, top_k=args.top, unified=args.unified)
    print(format_resolution_output(res, args.json))
