#!/bin/sh
# DLV Automation — safe GitHub-to-Timeweb publishing, run ON Timeweb via SSH/Cron.
# All network traffic goes OUT from Timeweb over HTTPS/443, never plain FTP.
set -eu
umask 022

REPO="https://github.com/Rbastl/dlv-automation.git"
REPO_DIR="$HOME/.dlv-automation-source"
SITE="$HOME/dlvautomation/public_html"
LAST_REV="$HOME/.dlv-automation-last-revision"
LOCK="$HOME/.dlv-automation-publish-lock"

if [ ! -d "$SITE" ]; then
  echo "ERROR: Timeweb site folder not found: $SITE"
  exit 1
fi
if ! command -v git >/dev/null 2>&1 || ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: git and rsync are required on Timeweb."
  exit 1
fi
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "Another DLV sync is running (or an old lock exists); skipping."
  exit 0
fi
trap 'if [ -n "${TMP:-}" ]; then rm -rf "$TMP"; fi; rmdir "$LOCK" 2>/dev/null || true' EXIT HUP INT TERM

export GIT_TERMINAL_PROMPT=0
git config --global pack.threads 1 >/dev/null 2>&1 || true

SRC="$REPO_DIR"
TMP=""
NEW_REV=""
GIT_OK=0

if [ -d "$REPO_DIR/.git" ]; then
  echo "Checking latest GitHub main over HTTPS."
  if git -C "$REPO_DIR" -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=20 \
       fetch -q --depth 1 origin main; then
    git -C "$REPO_DIR" reset --hard -q FETCH_HEAD
    GIT_OK=1
  fi
else
  echo "Creating isolated Git checkout outside public_html."
  NEW_CLONE="$HOME/.dlv-automation-clone-$$"
  if git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=20 \
      clone -q --depth 1 --branch main "$REPO" "$NEW_CLONE"; then
    if [ -e "$REPO_DIR" ]; then
      echo "ERROR: Source repository path exists but is not a Git checkout."
      rm -rf "$NEW_CLONE"
      exit 1
    fi
    mv "$NEW_CLONE" "$REPO_DIR"
    GIT_OK=1
  else
    rm -rf "$NEW_CLONE" 2>/dev/null || true
  fi
fi

if [ "$GIT_OK" -eq 1 ]; then
  NEW_REV=$(git -C "$REPO_DIR" rev-parse HEAD)
else
  # Timeweb's free trial can reject outgoing Git even on HTTPS.
  # A public GitHub archive on HTTPS/443 allows a manual staging test.
  echo "Git transport unavailable; trying a public HTTPS archive."
  if ! command -v curl >/dev/null 2>&1 ||
     ! command -v unzip >/dev/null 2>&1; then
    echo "ERROR: git failed and curl/unzip fallback unavailable."
    exit 1
  fi
  TMP=$(mktemp -d "$HOME/.dlv-automation-archive.XXXXXX")
  curl -fLsS --connect-timeout 12 --max-time 90 \
      "https://codeload.github.com/Rbastl/dlv-automation/zip/refs/heads/main" \
      -o "$TMP/main.zip"
  unzip -q "$TMP/main.zip" -d "$TMP"
  SRC="$TMP/dlv-automation-main"
  if [ ! -d "$SRC" ]; then
    echo "ERROR: GitHub archive has an unexpected directory structure."
    exit 1
  fi
  NEW_REV="archive-$(date -u +%Y%m%d%H%M)"
fi

if [ -f "$LAST_REV" ] && [ -f "$SITE/index.html" ] &&
   [ "$(cat "$LAST_REV")" = "$NEW_REV" ]; then
  echo "DLV: no new GitHub commit, site unchanged."
  exit 0
fi

for needed in index.html sitemap.xml robots.txt favicon.svg uslugi/index.html; do
  if [ ! -f "$SRC/$needed" ]; then
    echo "ERROR: Missing required source file: $needed"
    exit 1
  fi
done

# Never copy .git, workflow secrets, private scripts or SEO research into webroot.
# Avoid '--delete' so that Timeweb's preexisting cgi-bin and server files remain.
rsync -rlt --prune-empty-dirs \
  --exclude='/.git/' \
  --exclude='/.github/' \
  --exclude='/scripts/' \
  --exclude='/seo/' \
  --exclude='/examples/' \
  --exclude='/.nojekyll' \
  --include='*/' \
  --include='*.html' \
  --include='*.htm' \
  --include='*.css' \
  --include='*.js' \
  --include='*.svg' \
  --include='*.png' \
  --include='*.jpg' \
  --include='*.jpeg' \
  --include='*.webp' \
  --include='*.gif' \
  --include='*.ico' \
  --include='*.xml' \
  --include='*.txt' \
  --include='*.woff' \
  --include='*.woff2' \
  --include='*.webmanifest' \
  --include='*.avif' \
  --exclude='*' \
  "$SRC/" "$SITE/"

# Apache's DirectoryIndex must override the Timeweb placeholder index.htm.
# Do not overwrite custom Timeweb configuration if one already exists.
if [ ! -f "$SITE/.htaccess" ]; then
  cat > "$SITE/.htaccess" <<'EOF'
DirectoryIndex index.html index.htm
ErrorDocument 404 /404.html
Redirect 301 /razrabotka-scada/ /scada-hmi/
Redirect 301 /en/scada-hmi-development/ /en/scada-hmi/
EOF
fi

printf '%s\n' "$NEW_REV" > "$LAST_REV"
printf '%s\n' "$NEW_REV" > "$SITE/dlv-deploy-revision.txt"
echo "SUCCESS: DLV public website synchronized from GitHub main."
echo "Repository version: $NEW_REV"
echo "Site directory: $SITE"
echo "NEXT: verify staging site and HTTPS before changing DNS."
