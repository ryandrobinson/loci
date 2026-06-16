# loci.zsh — summon loci from your normal zsh prompt with //
#
#   // <request>   one ambient turn in the current directory
#   //  (+ Enter)  open a sustained back-and-forth; exit with Ctrl-D or //
#   anything else  runs as a normal shell command, untouched
#
# This installs an accept-line ZLE widget. A line beginning with // is captured
# RAW — the request text is quoted with ${(q)...} before the shell re-reads it,
# so no globbing or word-splitting ever touches what you typed. The widget is
# idempotent and safe to source from .zshrc more than once.

# Only meaningful in an interactive zsh with ZLE available.
[[ -o interactive ]] || return 0
whence zle >/dev/null 2>&1 || return 0

# Idempotency guard — re-sourcing is a no-op.
[[ -n ${LOCI_ZSH_SOURCED:-} ]] && return 0
typeset -g LOCI_ZSH_SOURCED=1

# A stable per-window session id so different terminals hold different threads.
# $$ is the interactive shell's pid: constant for the life of this window.
: ${LOCI_SESSION:=zsh-$$}
export LOCI_SESSION

# The accept-line widget. Falls through to the builtin for ordinary commands.
loci-accept-line() {
  emulate -L zsh
  if [[ $BUFFER == //* ]]; then
    local raw=${BUFFER#//}
    raw=${raw## }            # drop a single leading space: "// hi" -> "hi"
    if [[ -z $raw ]]; then
      # bare //  -> sustained chat
      BUFFER='loci chat'
    else
      # one ambient turn. ${(q)raw} quotes the request so the re-parse keeps it
      # as a single, literal argument — captured RAW as promised.
      BUFFER="loci turn -- ${(q)raw}"
    fi
  fi
  zle .accept-line
}

zle -N loci-accept-line
bindkey '^M' loci-accept-line   # Return
bindkey '^J' loci-accept-line   # Ctrl-J / newline
