#!/usr/bin/env sh
# install.sh — install loci. Zero framework, just POSIX sh + ANSI.
# Honours NO_COLOR and non-tty (clean plain text, no spinners). Idempotent.
# It NEVER writes an API key anywhere.

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# --- palette (TokyoNight) ---------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR+x}" ] && [ "${TERM:-}" != "dumb" ]; then
  TTY=1
  CYAN='\033[38;2;125;207;255m'; BLUE='\033[38;2;122;162;247m'
  PURPLE='\033[38;2;187;154;247m'; GREEN='\033[38;2;158;206;106m'
  RED='\033[38;2;247;118;142m'; DIM='\033[38;2;86;95;137m'; RST='\033[0m'
else
  TTY=0; CYAN=; BLUE=; PURPLE=; GREEN=; RED=; DIM=; RST=
fi

ok()   { printf '  %b✓%b %s\n' "$GREEN" "$RST" "$1"; }
bad()  { printf '  %b✗%b %s\n' "$RED" "$RST" "$1"; }
info() { printf '  %b·%b %s\n' "$DIM" "$RST" "$1"; }
rule() { printf '%b── %s %b\n' "$BLUE" "$1" "$RST"; }

# Wordmark — figlet "ANSI Shadow". Single source; the colour pass (the shared
# izakaya/Athena per-char gradient) is done by Python when available, else plain.
ART='██╗      ██████╗  ██████╗██╗
██║     ██╔═══██╗██╔════╝██║
██║     ██║   ██║██║     ██║
██║     ██║   ██║██║     ██║
███████╗╚██████╔╝╚██████╗██║
╚══════╝ ╚═════╝  ╚═════╝╚═╝'
TAGLINE='✦ the genius of the place · summon with //'

banner() {
  printf '\n'
  BPY=
  for c in python3 python; do command -v "$c" >/dev/null 2>&1 && { BPY=$c; break; }; done
  if [ "$TTY" = 1 ] && [ -n "$BPY" ]; then
    LOCI_ART="$ART" LOCI_TAG="$TAGLINE" "$BPY" <<'PY'
import os
ART = os.environ["LOCI_ART"]; TAG = os.environ["LOCI_TAG"]
STOPS = [(122,162,247),(125,207,255),(187,154,247),(115,218,202),(158,206,106),(247,118,142)]
def g(p):
    x = ((p % 1) + 1) % 1; s = x * (len(STOPS) - 1)
    i = min(len(STOPS) - 2, int(s)); t = s - i
    a, b = STOPS[i], STOPS[i + 1]
    return tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))
for r, line in enumerate(ART.split("\n")):
    n = max(len(line), 1); out = []
    for i, ch in enumerate(line):
        if ch == " ": out.append(" ")
        else:
            c = g((i / n) * 0.9 + r * 0.07)
            out.append("\033[38;2;%d;%d;%dm%s" % (c[0], c[1], c[2], ch))
    out.append("\033[0m"); print("".join(out))
print("\033[38;2;86;95;137m" + TAG + "\033[0m")
PY
  else
    printf '%s\n%b%s%b\n' "$ART" "$DIM" "$TAGLINE" "$RST"
  fi
  printf '\n'
}

spinner() { # $1 = pid, $2 = label
  set -- "$1" "$2" ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏
  pid=$1; label=$2; shift 2
  n=$#; i=1
  while kill -0 "$pid" 2>/dev/null; do
    eval "frame=\${$i}"
    printf '\r  %b%s%b %s' "$DIM" "$frame" "$RST" "$label"
    i=$((i + 1)); [ "$i" -gt "$n" ] && i=1
    sleep 0.08
  done
  printf '\r\033[K'
}

LOG=$(mktemp 2>/dev/null || echo /tmp/loci-install.$$)
run_spun() { # $1 label, rest: command
  label=$1; shift
  if [ "$TTY" = 1 ]; then
    ( "$@" ) >"$LOG" 2>&1 &
    spinner $! "$label"
    wait $! ; return $?
  fi
  info "$label"
  "$@" >"$LOG" 2>&1
}

py_ge_311() { "$1" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,11) else 1)' 2>/dev/null; }

# --- run --------------------------------------------------------------------
banner
rule "checks"

if command -v zsh >/dev/null 2>&1; then
  ok "zsh found ($(zsh --version 2>/dev/null | awk '{print $2}'))"
else
  bad "zsh not found — loci's // hook needs zsh"
fi

PYTHON=
for c in python3.13 python3.12 python3.11 python3 python; do
  command -v "$c" >/dev/null 2>&1 || continue
  if py_ge_311 "$c"; then PYTHON=$(command -v "$c"); break; fi
done
if [ -n "$PYTHON" ]; then
  ok "Python ≥3.11 found ($("$PYTHON" -c 'import sys;print("%d.%d"%sys.version_info[:2])'))"
else
  bad "Python ≥3.11 not found — please install it and re-run"
  exit 1
fi

rule "install"
if run_spun "installing loci onto your PATH" "$PYTHON" -m pip install --user "$SCRIPT_DIR"; then
  ok "loci installed"
else
  bad "pip install failed"; cat "$LOG"; exit 1
fi

USER_BIN="$("$PYTHON" -m site --user-base 2>/dev/null)/bin"
case ":$PATH:" in
  *":$USER_BIN:"*) : ;;
  *) info "add to PATH:  export PATH=\"$USER_BIN:\$PATH\"" ;;
esac

CONFIG_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/loci
mkdir -p "$CONFIG_DIR"
cp "$SCRIPT_DIR/shell/loci.zsh" "$CONFIG_DIR/loci.zsh"
ZSHRC=${ZDOTDIR:-$HOME}/.zshrc
if grep -q 'loci >>>' "$ZSHRC" 2>/dev/null; then
  ok "// hook already present in $ZSHRC"
else
  {
    printf '\n# >>> loci >>>\n'
    printf '[ -f "%s/loci.zsh" ] && source "%s/loci.zsh"\n' "$CONFIG_DIR" "$CONFIG_DIR"
    printf '# <<< loci <<<\n'
  } >> "$ZSHRC"
  ok "added the // hook to $ZSHRC"
fi

rule "key"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  ok "ANTHROPIC_API_KEY is set"
else
  info "ANTHROPIC_API_KEY is not set (loci reads it from the environment; never stored)"
fi

# --- close ------------------------------------------------------------------
printf '\n%b┌─ ready %b\n' "$BLUE" "$RST"
printf '%b│%b  1. open a new terminal (or: %bsource %s%b)\n' "$BLUE" "$RST" "$CYAN" "$ZSHRC" "$RST"
printf '%b│%b  2. set your key:  %bexport ANTHROPIC_API_KEY="sk-ant-..."%b\n' "$BLUE" "$RST" "$CYAN" "$RST"
printf '%b│%b  3. run setup:     %bloci onboard%b\n' "$BLUE" "$RST" "$CYAN" "$RST"
printf '%b│%b  4. summon it:     %b// list this directory and suggest a .gitignore%b\n' "$BLUE" "$RST" "$CYAN" "$RST"
printf '%b└%b  %bthe genius of the place is yours.%b\n\n' "$BLUE" "$RST" "$DIM" "$RST"
