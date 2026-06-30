# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

System configuration and utility scripts for Kiro / ArcoLinux-based desktops. It ships:
- **`usr/local/bin/`** — 40+ standalone utility scripts (pacman helpers, kernel variant installers, system info, DE fetchers)
- **`usr/local/lib/roman-os-common.sh`** — unified shared library sourced by all scripts (80+ functions, 1000+ lines)
- **`etc/`** — drop-in config files for sysctl, udev, systemd, modprobe, X11, pacman hooks

## Deployment

**Always build and install the package — never `sudo cp` files directly.**

After committing changes, build and install the package (e.g. `makepkg -si`). Direct copying bypasses pacman, creates untracked files, and breaks future upgrades.

`setup-edu.sh` configures git remotes; `up.sh` commits and pushes.

## Shared library (`roman-os-common.sh`)

Every script must source this library before doing anything else:

```bash
# shellcheck source=/usr/local/lib/roman-os-common.sh
source /usr/local/lib/roman-os-common.sh
```

**Documented exception — `usr/local/bin/kiro-skell` and `usr/local/bin/kiro-skell-all`.** This pair of scripts does **not** source the library; each **inlines** the handful of helpers it needs (colors, `log_info`, `log_success`, `show_help`, `show_version`, `execute_or_dryrun`, the ERR trap). `kiro-skell` is the **fast** default (backs up only the `~/.config` entries `/etc/skel` overwrites, scanned dynamically); `kiro-skell-all` is the **full** variant (backs up the whole `~/.config`). Reason for self-containment: `kiro-skell` is the single source of truth for ATT's `skell`, which is fetched and shipped to **non-Kiro** systems (stock Arch, Endeavour, CachyOS, Manjaro) where `/usr/local/lib/roman-os-common.sh` does not exist. Sourcing it would hard-fail off-Kiro. Keep both self-contained; do not "fix" them to source the library. All their user-facing text uses `"$(basename "$0")"` so a verbatim copy under another name (e.g. `skell`) prints that name unchanged. If `roman-os-common.sh`'s log format changes, update the inline copies here by hand.

Key sections and their functions:
- **Colors** — `$RED`, `$GREEN`, `$YELLOW`, `$BLUE`, `$CYAN`, `$BOLD`, `$RESET` (tput-based, disabled when not a terminal)
- **Logging** — `log_section`, `log_subsection`, `log_info`, `log_success`, `log_warn`, `log_error`
- **Error handling** — automatic `on_error` trap; scripts use `set -Euo pipefail`
- **Generic helpers** — `require_root_tools`, `replace_text_in_file`, `comment_out_patterns_in_file`, `show_help`, `execute_or_dryrun`
- **Package helpers** — `pkg_installed`, `install_packages`, `remove_packages`, `install_local_packages_from_dir`
- **Repo/pacman helpers** — add/remove/toggle repository entries in `pacman.conf`
- **Kernel/performance helpers** — sysctl, scheduler, CPU core utilities

## Script conventions

- First line after shebang: `set -Euo pipefail`
- Source `roman-os-common.sh` before any logic
- Use library logging functions — never raw `echo` for user-facing output
- Root checks via `require_root_tools` or `[[ $EUID -ne 0 ]]` guard
- Avoid hard-coding paths that `roman-os-common.sh` already provides

## Kernel-agnostic rule

**Every system tweak shipped by this package — sysctl, udev, modprobe, systemd drop-in, tmpfile, NetworkManager conf, audit check — must work on any kernel a Kiro user might run.** Kiro ships `linux-cachyos` as default + `linux-zen` as fallback (2026-05-28), but users freely swap to `linux-hardened`, `linux-lts`, custom kernels, etc.

This means:
- No tweak may depend on a kernel-specific sysfs path, parameter, or scheduler that only one kernel exposes.
- No modprobe option that exists in only one kernel's driver build.
- No service that requires a CachyOS-only or Zen-only feature.
- When reviewing a new tweak, ask: "does this break on linux-lts?" If yes, redesign or skip.
- `kiro-audit` itself is kernel-agnostic (see `detect_kernels()` and `check_kernel`).

Past examples of this rule applied: `kiro-audit` rewrite 2026-05-28; the 5 Garuda imports same day (systemd-oomd, mei blacklist, btusb reset, zswap disable, NM-lo) were all verified kernel-agnostic before adoption.

## Configuration file locations

| Path                                      | Purpose                                                 |
|-------------------------------------------|---------------------------------------------------------|
| `etc/sysctl.d/99-kiro-optimizations.conf` | Kernel tuning (memory, network, I/O, security)          |
| `etc/udev/rules.d/60–68-*.rules`          | Hardware tuning rules (I/O schedulers, GPU, USB, audio) |
| `etc/systemd/system.conf.d/`              | Global systemd service/timeout/resource settings        |
| `etc/modprobe.d/`                         | Driver options for AMD/Nvidia GPU, audio, ethernet      |
| `etc/security/limits.d/`                  | ulimit overrides for audio and system processes         |

## Configuration files — audit status (2026.05.18)

All `etc/` config files were audited and fixed. The set is now safe to deploy on general desktop and laptop hardware without hardware-specific breakage. Key outcomes:
- `etc/sysctl.d/99-kiro-optimizations.conf` — duplicate keys removed, security settings calibrated for usability (sysrq=244, ptrace_scope=1), comments corrected
- `etc/udev/rules.d/` — broken rules replaced or removed; NVIDIA GPU power rule removed (hangs); input rules rewritten with working sysfs paths
- `etc/systemd/` — journal storage changed to persistent; rate limiting fixed; timeouts increased to safe values
- `etc/modprobe.d/` — invalid r8169 parameters stripped; probe_mask removed; DPRINTK=1 removed; warnings added for amdgpu and nvidia single-user caveat

## Script improvement status

- Phase 1 (complete): unified library, error handling, variable quoting — all 33 scripts source `roman-os-common.sh`
- Phase 2 (in progress): `--help`/`--version`/`--dry-run` flags and man pages — pattern established on `kiro-fix-pacman-keys`, `kiro-enable-ssh`, and `kiro-audit`
- Phases 3–4 (planned): config files, full shellcheck/shfmt pass

## `--fix` mode pattern (kiro-audit)

For audit/diagnostic scripts that can auto-remediate: add `FIX_MODE=false`, parse `--fix` in the arg loop, and use this helper:

```bash
apply_fix() {
    local msg="$1"; shift
    if [[ "${FIX_MODE}" == true ]]; then
        echo "  ${CYAN}FIX${RESET}   ${msg}"
        if "$@"; then FIXED=$((FIXED + 1)); else echo "  ${RED}ERR${RESET}   fix failed: $*"; fi
    else
        echo "  ${CYAN}FIX?${RESET}  --fix: ${msg}"
    fi
}
```

Call it immediately after `fail()` on fixable checks. Read-only mode shows `FIX?` hints; `--fix` mode prints and runs. Summary reports `FIXED: N`.

## `--version` — read from pacman at runtime

Never hardcode a version string. Query the owning package:

```bash
pkg=$(pacman -Qqo "$(realpath "${BASH_SOURCE[0]}")" 2>/dev/null) \
    && pacman -Q "${pkg}" \
    || echo "$(basename "$0") (not installed via pacman)"
```

## `log_error` is a trap handler, not a message function

`log_error` in `roman-os-common.sh` takes `lineno` and `cmd` params — it is wired to the ERR trap. Calling it with a plain string produces the full banner with the string treated as a line number. For user-facing messages (e.g. root checks), use:

```bash
echo "${RED}This script must be run as root.${RESET}" >&2
```

## Files excluded from the package

- `etc/cups/cups-permissions.conf` — **do not add to the package**; it conflicts during ISO build and must be applied by post-install scripting or the user manually.

## Man pages

Man pages live in `usr/share/man/man8/` (section 8, system-admin commands). After deploying new pages, run `sudo mandb` manually — the `man-db.timer` only fires once daily with up to 12h random delay.
