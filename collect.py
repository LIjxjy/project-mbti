#!/usr/bin/env python3
"""收集项目的客观信号，输出 JSON。只读，不修改项目。

用法: python3 collect.py <项目路径>
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist",
             "build", ".next", "target", ".idea", ".vscode", "vendor"}
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c",
            ".cpp", ".h", ".cs", ".rb", ".php", ".kt", ".swift", ".vue", ".sh"}
DOC_EXT = {".md", ".rst", ".txt"}
MAX_BYTES = 500_000

TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
ABSTRACT_RE = re.compile(
    r"\b(abstract|interface|Factory|Registry|Plugin|Adapter|Strategy|Protocol|"
    r"Generic|metaclass|Provider|Manager|Handler)\b")
DECL_RE = re.compile(r"^\s*(export\s+)?(abstract\s+)?(class|interface|trait|protocol)\s+\w+")
CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|docs|chore|refactor|test|style|perf|ci|build|revert)(\(.+\))?!?:")
LAZY_RE = re.compile(r"^(update|fix|tmp|wip|test|add|ok|\.+|\d+|修改|更新|调试|测试)$", re.I)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def iter_files(root: Path):
    """遍历文件，并直接跳过 node_modules 等目录，避免大仓库变慢。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


def is_test(path: Path) -> bool:
    name = path.name.lower()
    parts = {p.lower() for p in path.parts}
    return (name.startswith("test_") or ".test." in name or ".spec." in name
            or name.endswith("_test.go") or "tests" in parts or "test" in parts or "__tests__" in parts)


def git_log(root: Path):
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "-n", "100", "--format=%s"],
            capture_output=True, text=True, timeout=15)
        if out.returncode != 0:
            return None
        return [l for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return None


def count_deps(root: Path) -> int:
    n = 0
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            n += len(data.get("dependencies", {})) + len(data.get("devDependencies", {}))
        except Exception:
            pass
    req = root / "requirements.txt"
    if req.exists():
        n += sum(1 for l in req.read_text(encoding="utf-8", errors="ignore").splitlines()
                 if l.strip() and not l.startswith("#"))
    return n


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: collect.py <项目路径>")
    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        sys.exit(f"不是目录: {root}")

    code_files, test_files, doc_files = [], [], []
    total_lines = comment_lines = todo = abstract = 0
    ext_count = {}

    for p in iter_files(root):
        ext = p.suffix.lower()
        ext_count[ext] = ext_count.get(ext, 0) + 1
        if ext in DOC_EXT:
            doc_files.append(p)
        if ext not in CODE_EXT:
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = text.splitlines()
        code_files.append((p, len(lines)))
        if is_test(p.relative_to(root)):
            test_files.append(p)
        total_lines += len(lines)
        comments = [l for l in lines if l.strip().startswith(("#", "//", "/*", "*"))]
        comment_lines += len(comments)
        # 待办标记只在注释行里数，抽象只在类/接口声明里数，避免把字符串当成信号
        todo += sum(len(TODO_RE.findall(l)) for l in comments)
        decls = [l for l in lines if DECL_RE.match(l)]
        abstract += len(decls) + sum(len(ABSTRACT_RE.findall(l)) for l in decls)

    readme = next((p for p in root.iterdir() if p.name.lower().startswith("readme")), None) \
        if root.exists() else None
    readme_text = readme.read_text(encoding="utf-8", errors="ignore") if readme else ""

    def has(*names):
        return any((root / n).exists() for n in names)

    kloc = max(total_lines / 1000, 0.001)
    commits = git_log(root)
    git = None
    if commits is not None:
        n = len(commits)
        git = {
            "commits_sampled": n,
            "avg_msg_len": round(sum(len(c) for c in commits) / n, 1) if n else 0,
            "conventional_ratio": round(sum(bool(CONVENTIONAL_RE.match(c)) for c in commits) / n, 2) if n else 0,
            "lazy_msg_ratio": round(sum(bool(LAZY_RE.match(c.strip())) for c in commits) / n, 2) if n else 0,
            "sample": commits[:8],
        }

    top = sorted(code_files, key=lambda x: -x[1])[:5]
    result = {
        "root": str(root),
        "code_files": len(code_files),
        "code_lines": total_lines,
        "ext_count": dict(sorted(ext_count.items(), key=lambda x: -x[1])[:8]),
        "test_file_ratio": round(len(test_files) / len(code_files), 2) if code_files else 0,
        "comment_ratio": round(comment_lines / total_lines, 2) if total_lines else 0,
        "todo_total": todo,
        "todo_per_kloc": round(todo / kloc, 1),
        "abstraction_per_kloc": round(abstract / kloc, 1),
        "dependencies": count_deps(root),
        "doc_files": len(doc_files),
        "readme": {
            "exists": bool(readme),
            "chars": len(readme_text),
            "emoji": len(EMOJI_RE.findall(readme_text)),
            "exclamations": readme_text.count("!") + readme_text.count("！"),
            "has_usage_section": bool(re.search(r"(usage|使用|quick ?start|getting ?started|快速开始|开始)", readme_text, re.I)),
        },
        "config": {
            "ci": has(".github/workflows", ".gitlab-ci.yml", "Jenkinsfile", ".circleci"),
            "lint_or_format": has(".eslintrc", ".eslintrc.json", ".flake8", "ruff.toml",
                                  ".pre-commit-config.yaml", ".prettierrc", ".editorconfig"),
            "type_check": has("tsconfig.json", "mypy.ini", "py.typed"),
            "changelog": has("CHANGELOG.md", "CHANGELOG"),
            "contributing": has("CONTRIBUTING.md"),
            "license": has("LICENSE", "LICENSE.md"),
            "docker": has("Dockerfile", "docker-compose.yml"),
            "docs_dir": has("docs", "doc"),
            "examples_dir": has("examples", "example", "demo"),
        },
        "git": git,
        "largest_code_files": [{"path": str(p.relative_to(root)), "lines": n} for p, n in top],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
