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
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT HUP INT TERM

export GIT_TERMINAL_PROMPT=0
git config --global pack.threads 1 >/dev/null 2>&1 || true

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "Creating isolated Git checkout outside public_html."
  # A public repository and HTTPS require no credentials or SSH keys.
  git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=20 \
      clone -q --depth 1 --branch main "$REPO" "$REPO_DIR"
else
  echo "Checking latest GitHub main over HTTPS."
  git -C "$REPO_DIR" -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=20 \
      fetch -q --depth 1 origin main
  # This folder is dedicated to DLV deploy and contains no user edits.
  git -C "$REPO_DIR" reset --hard -q FETCH_HEAD
fi

NEW_REV=$(git -C "$REPO_DIR" rev-parse HEAD)
if [ -f "$LAST_REV" ] && [ -f "$SITE/index.html" ] &&
   [ "$(cat "$LAST_REV")" = "$NEW_REV" ]; then
  echo "DLV: no new GitHub commit, site unchanged."
  exit 0
fi

for needed in index.html sitemap.xml robots.txt favicon.svg uslugi/index.html; do
  if [ ! -f "$REPO_DIR/$needed" ]; then
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
  "$REPO_DIR/" "$SITE/"

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
