#!/usr/bin/env bash
# Sync internal HA repo to public GitHub repo (clean history, no secrets).
#
# Usage:
#   ./sync-to-public.sh [--init]
#
#   --init   First-time setup: clone/create the public repo locally
#
# Prerequisites:
#   - gh CLI authenticated (for --init)
#   - git configured with push access to the public repo

set -euo pipefail

# ---------- Config ----------
INTERNAL_REPO="$(cd "$(dirname "$0")" && pwd)"
PUBLIC_REPO_DIR="${INTERNAL_REPO}/../ha-public"
PUBLIC_REMOTE="https://github.com/yzlnew/ha-config-as-code.git"

# Files/dirs to EXCLUDE from the public repo
EXCLUDE_PATTERNS=(
    ".env"
    ".env.*"
    "!.env.example"       # keep the example
    ".DS_Store"
    "__pycache__/"
    "*.pyc"
    ".venv/"
    ".claude/settings.local.json"
    ".gemini/settings.local.json"
)

# ---------- Functions ----------
init_public_repo() {
    if [[ -d "$PUBLIC_REPO_DIR" ]]; then
        echo "Public repo dir already exists: $PUBLIC_REPO_DIR"
        echo "Remove it first if you want to re-initialize."
        exit 1
    fi

    echo "==> Initializing public repo at $PUBLIC_REPO_DIR"
    mkdir -p "$PUBLIC_REPO_DIR"
    cd "$PUBLIC_REPO_DIR"
    git init
    git remote add origin "$PUBLIC_REMOTE"
    git checkout -b main
    echo "==> Public repo initialized. Run without --init to sync."
}

sync() {
    if [[ ! -d "$PUBLIC_REPO_DIR/.git" ]]; then
        echo "Error: Public repo not found at $PUBLIC_REPO_DIR"
        echo "Run with --init first."
        exit 1
    fi

    echo "==> Syncing from internal repo to public repo..."

    # Clean public repo (keep .git)
    find "$PUBLIC_REPO_DIR" -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +

    # Copy files tracked by git (respects .gitignore)
    cd "$INTERNAL_REPO"
    git ls-files -z | while IFS= read -r -d '' file; do
        dir=$(dirname "$file")
        mkdir -p "$PUBLIC_REPO_DIR/$dir"
        if [[ -L "$file" ]]; then
            # Preserve symlinks
            cp -a "$file" "$PUBLIC_REPO_DIR/$file"
        elif [[ -f "$file" ]]; then
            cp "$file" "$PUBLIC_REPO_DIR/$file"
        fi
    done

    # Also copy untracked files that should be public (none for now, add if needed)

    # Remove files that should NOT be in public repo
    cd "$PUBLIC_REPO_DIR"
    rm -f .DS_Store
    rm -rf __pycache__
    find . -name "*.pyc" -delete
    rm -f .claude/settings.local.json
    rm -f .gemini/settings.local.json

    # Verify no secrets leaked
    echo "==> Checking for potential secrets..."
    local has_secrets=0

    # Check for hardcoded tokens (JWT pattern)
    if grep -rE 'eyJ[a-zA-Z0-9_-]{20,}\.' --include="*.py" --include="*.yaml" --include="*.yml" --include="*.md" --include="*.json" . 2>/dev/null | grep -v '.git/'; then
        echo "WARNING: Possible JWT token found!"
        has_secrets=1
    fi

    # Check for hardcoded passwords (not in !secret or env references)
    if grep -rnE '^\s*(password|api_key|token)\s*[:=]\s*"[^!][^"]{6,}"' --include="*.yaml" --include="*.yml" . 2>/dev/null | grep -v '.git/' | grep -v 'example' | grep -v 'your_'; then
        echo "WARNING: Possible hardcoded password in YAML!"
        has_secrets=1
    fi

    if [[ $has_secrets -eq 1 ]]; then
        echo ""
        echo "ABORTING: Potential secrets detected. Review the warnings above."
        exit 1
    fi
    echo "    No secrets detected."

    # Show diff summary
    echo ""
    echo "==> Changes to be published:"
    git add -A
    if git diff --cached --quiet 2>/dev/null; then
        echo "    No changes to sync."
        git reset HEAD -- . >/dev/null 2>&1
        return
    fi
    git diff --cached --stat

    # Prompt for commit
    echo ""
    read -rp "Commit and push? [y/N] " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        # Use the latest internal commit message as reference
        local latest_msg
        latest_msg=$(cd "$INTERNAL_REPO" && git log -1 --pretty=format:"%s")
        read -rp "Commit message [$latest_msg]: " custom_msg
        local msg="${custom_msg:-$latest_msg}"

        git commit -m "$msg"
        git push -u origin main
        echo "==> Pushed to public repo."
    else
        echo "==> Aborted. Changes are staged in $PUBLIC_REPO_DIR"
        git reset HEAD -- . >/dev/null 2>&1
    fi
}

# ---------- Main ----------
case "${1:-}" in
    --init)
        init_public_repo
        ;;
    *)
        sync
        ;;
esac
