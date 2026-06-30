# CHANGELOG

## 2026.06.26

### System tuning — adopt two CachyOS improvements (live diff vs clean CachyOS)

- **What Changed:** compared `kiro-system-files` against a clean CachyOS rolling install
  (`cachyos-settings`) and adopted the two genuine deltas where CachyOS was ahead. (1) Added
  `etc/modules-load.d/ntsync.conf` to autoload the `ntsync` module — NT synchronization primitives
  that significantly speed up Wine/Proton; the module ships in our default `linux-cachyos` kernel
  (and `linux-zen`) but was never loaded. (2) Fixed `etc/tmpfiles.d/thp-tuning.conf`:
  `khugepaged/max_ptes_none` was set to `511`, which is the kernel default and therefore a no-op —
  changed to `409` (split any THP >80% zero-filled) so the THP shrinker actually reduces RSS
  over-provisioning under `THP=always`, matching CachyOS.
- **Technical Details:** both tweaks are kernel-agnostic per the repo rule — `systemd-modules-load`
  silently skips `ntsync` on kernels that lack it, and `max_ptes_none=409` is valid on every 6.12+
  kernel (older kernels harmlessly fail the tmpfiles write). The wider diff confirmed Kiro is
  otherwise a superset of CachyOS (sysctl, limits, journald, systemd-oomd, ananicy-cpp all already
  ahead). Two items were left for a separate decision at the time — both now resolved in the
  follow-up below: the zram cap and the swappiness comment.
- **Files Modified:**
  - `etc/modules-load.d/ntsync.conf` (new)
  - `etc/tmpfiles.d/thp-tuning.conf`

### ZRAM sizing + swappiness comment accuracy (follow-up to the CachyOS diff)

- **What Changed:** (1) Raised the ZRAM device size from `min(ram / 2, 4096)` to `min(ram, 8192)`
  in `etc/systemd/zram-generator.conf`. The old 4 GiB cap under-served 16 GB+ machines and clashed
  with our aggressive `vm.swappiness = 150` — we told the kernel to swap eagerly but handed it a
  small target. ZRAM size is a *cap*, not a reservation (real RAM is consumed only as pages are
  actually swapped, and compressed), so a generous size is cheap; low/mid-RAM boxes now get
  ZRAM == RAM. (2) Corrected the `vm.swappiness` comment in
  `etc/sysctl.d/99-kiro-optimizations.conf`: it claimed "150 is the modern Arch ZRAM standard
  (CachyOS…)", but a clean CachyOS install actually ships `vm.swappiness = 100`. Reworded to state
  that 150 is our deliberate aggressive choice (kernel cap is 200 since 5.8), not a copied convention.
- **Technical Details:** kept an 8 GiB ceiling rather than CachyOS's unbounded `zram-size = ram`
  so very-high-RAM machines don't allocate pointless device metadata; the value change is
  kernel-agnostic. No functional change to swappiness — comment-only fix for accuracy.
- **Files Modified:**
  - `etc/systemd/zram-generator.conf`
  - `etc/sysctl.d/99-kiro-optimizations.conf`

## 2026.06.24

### kiro-report — `--copy` flag (copy the report to the clipboard)

- **What Changed:** added `-c`/`--copy` to `kiro-report`. After writing the redacted log file it now also
  copies the report to the clipboard, wrapped in a Markdown ```` ``` ```` code fence so it pastes straight
  into a Kiro Discussions code block. The support flow becomes "run → paste" instead of "open file → select
  all → copy". Inspired by MX Linux's quick-system-info-gui "Copy for forum" button, but kept as a CLI flag
  on the existing tool (kiro-report already exceeds QSI on content + PII redaction; only the one-click
  clipboard convenience was missing).
- **Technical Details:** `kiro-report` re-execs as root via `ensure_root`, so a clipboard tool run in that
  context would target root's empty session. The new `copy_to_clipboard()` helper instead harvests the
  invoking user's live session variables (`WAYLAND_DISPLAY` / `DISPLAY` / `XAUTHORITY` / `XDG_RUNTIME_DIR`)
  straight from a graphical process's `/proc/<pid>/environ` — robust against random `/tmp` `XAUTHORITY`
  paths — then runs the tool as that user with `sudo -u`. Wayland (`wl-copy`) is tried first, then X11
  (`xclip`, then `xsel`). Degrades gracefully: when no clipboard tool or graphical session is found it logs
  a warning and the file path still stands. Man page synopsis/options updated.
- **Heads-up (not yet done):** the package declares no clipboard dependency and none of
  `wl-clipboard`/`xclip`/`xsel` ship in the kiro-iso package list, so `--copy` will warn-and-skip on a stock
  install. To make it actually copy, add `wl-clipboard`/`xclip` as `optdepends` (or to the ISO package list)
  — left for Erik to decide.
- **Files Modified:** `usr/local/bin/kiro-report`, `usr/share/man/man8/kiro-report.8`

## 2026.06.21

### Remove the systemd-logind.service drop-in (`10-kiro-session.conf`)
- **What:** deleted `etc/systemd/system/systemd-logind.service.d/10-kiro-session.conf` (and its now-empty
  `.service.d` dir), plus its expected-config entries in `kiro-audit` and `kiro-verify`.
- **Why:** the drop-in overrode the deliberately-tuned upstream `systemd-logind.service` —
  `Restart=always`→`on-failure`, `RestartSec=0`→`5s`, plus `KillMode=mixed` / `KillSignal=SIGTERM`. logind
  is the seat manager that hands DRM-master to each new session, so upstream runs it `Restart=always` /
  `RestartSec=0` on purpose; weakening that is risky and the file's own comments were factually wrong
  ("Restart on failure … ensures session management works" — the opposite is true). Reverting to upstream
  behaviour is strictly safer. (It was *not* the cause of the Plasma logout black screen — that was
  `archlinux-logout` running `pkill plasma`; this is an independent correctness fix.)
- Both `kiro-audit` (`check_systemd_dropins`) and `kiro-verify` config-presence lists updated so they no
  longer expect the removed file.

### kiro-audit — new "Kiro Plasma theme/config" check
- **What:** added a `check_kiro_plasma` section that runs **only when Plasma is installed**. It reports
  two things for the installed `kiro-plasma-*` set: (1) **delivery** — the config each package ships under
  `/etc/xdg` (system-default cascade) and `/etc/skel` (new-user seed) is present and seeded; (2) **visual
  inventory** — for each element the *active* Kiro look-and-feel declares (cursor, colour scheme, icons,
  widget style, window decoration) it lists the UID 1000 user's actual effective value as **SET** (matches
  intended), **DIFFERS**, or **NOT SET** (falling back to a cascade/system default).
- **Why:** surfaces theme drift — what the look-and-feel intends vs what the session actually shows. Most
  of these only apply when the user actively selects the Global Theme, so NOT SET is a normal state, not a
  failure; the check uses `warn`, never `fail`, to avoid alarmism on a fresh install.

### Technical Details
- Reads effective values with `sudo -H -u <user> kreadconfig6` (the audit runs as root). Scoped to the
  **active** look-and-feel (`kdeglobals [KDE] LookAndFeelPackage`) so several installed theme packages
  don't each report false mismatches; a non-Kiro active look-and-feel is reported plainly.
- **Cursor is resolved through its real lookup chain** — `~/.config/kcminputrc` → `~/.icons/default/index.theme`
  → `/usr/share/icons/default/index.theme` — and reports the cursor genuinely in effect plus its source
  package, instead of just reading the (often empty) `kcminputrc` key. On a stock image this correctly
  shows the `default-cursors` value rather than `<unset>`.
- The look-and-feel `defaults` parser stores its section-header regex in a variable
  (`hdr_re='^\[([^][]+)\]...'`); the equivalent inline `[[ =~ ]]` form silently fails to match in Bash.
- Report-only — no `--fix` action for theme state. Man page `kiro-audit.8` updated with the new check.



### kiro-common — recover the invoking user on the pkexec (graphical root) path
- **Bug:** `TARGET_USER="${SUDO_USER:-$USER}"` resolved to **root** whenever a script was elevated via
  `pkexec` (the graphical password dialog from `ensure_root`). `pkexec` scrubs the environment to a
  minimal safe set — it does not set `SUDO_USER` and sets `USER=root` — so the fallback picked root.
  Any script writing or chowning user files then targeted `/root` instead of the real user's home.
- **Symptom that surfaced it:** `kiro-report` wrote its report to `/root/kiro-report-*.log` and printed a
  `file:///root/...` link the desktop user's browser cannot open (root-only directory).
- **Fix:** prefer `PKEXEC_UID` (which `pkexec` *does* export — the invoking user's uid) to recover the
  real user, then fall back to `SUDO_USER`/`USER`. The `sudo` and direct-root paths are unchanged; only
  the previously-broken pkexec path now resolves to the human who launched the command — matching what
  `sudo` already did.

### Technical Details
- `getent passwd "${PKEXEC_UID}" | cut -d: -f1` maps the uid back to a name; empty `PKEXEC_UID` (sudo /
  real-root) falls through to the original `${SUDO_USER:-$USER}`.
- Affects only `kiro-system-files` (the sole package shipping `roman-os-common.sh`); the change is a strict
  correction — no consumer wants `TARGET_USER=root` under pkexec.

### kiro-common — restore /usr/local/bin on the pkexec PATH
- **Bug (same pkexec-scrub family):** `pkexec` rewrites PATH to a minimal `/usr/sbin:/usr/bin:/sbin:/bin`
  that omits `/usr/local/bin`. Scripts that call a sibling tool by bare name then fail under the graphical
  root path. `kiro-report` hit exactly this — `line 201: kiro-diag: command not found` — so every
  graphically-generated report was **missing its entire `kiro-diag` section** (hardware, GPU, kernel,
  desktop). The `sudo` path was fine because sudo's `secure_path` includes `/usr/local/bin`.
- **Fix:** `ensure_root` now passes an explicit `PATH` (with `/usr/local/sbin:/usr/local/bin` prepended)
  through the `pkexec env` re-exec, alongside the existing `TERM`. Fixes every Kiro script that shells out
  to a `/usr/local/bin` sibling, not just kiro-report.

### kiro-report — drop Qt noise + stop mis-redacting versions and C++ "::"
- The "Warnings / errors" grep surfaced Qt chatter on every install (`beginResetModel`,
  `QObject::setParent`, `QIODevice::read`, `QLayout`, ...) that never points at a real fault. Now the
  grep pipes through `grep -vF '(Qt):'` before `tail -n 40`, so the 40-line budget holds *meaningful*
  warnings (branding/partition/chwd/osprober/EFI/chcon/intel-ucode) instead of being consumed by noise.
- **Redaction false positives fixed.** The IPv4 rule matched 4-part package versions, printing
  `libva <ip>-1`, `vulkan-tools <ip>-1`, `imagemagick <ip>-1`, etc.; the IPv6 `::` rule ate every C++
  scope operator, mangling the Calamares log (`Calamares::JobThread::run` → `Calamares<ipv6>JobThr<ipv6>run`).
  - IPv4 now uses valid 0-255 octets and skips a quad followed by `-` (pkgrel) or `.<letter>` (git-version
    continuation, e.g. `sddm-git`'s `…-git` hash suffix), so versions survive while real addresses —
    including one at a sentence end (a trailing-period IP) — are still scrubbed.
  - IPv6 is anchored on non-alphanumeric boundaries, so `Word::Word` survives while real `fe80::…`,
    `::1`, and `2001:db8::…` addresses are scrubbed. PCI (`0000:03:00.0`) and timestamps (`11:32:56`)
    are untouched (no `::`). Verified across an 11-case test matrix.

### kiro-diag — reliable bootloader detection (systemd-boot / GRUB / Limine / rEFInd)
- **Bug:** detection parsed `efibootmgr` labels. A systemd-boot install reached via the removable
  fallback path (`\EFI\BOOT\BOOTX64.EFI`) is labelled only `UEFI OS` by firmware, matching none of the
  patterns → `Bootloader: unknown`. Package presence was no help either — Kiro ships `grub` + `refind`
  even when systemd-boot is what actually boots.
- **Fix:** resolve the ESP with `bootctl -p` (layout-agnostic: `/efi`, `/boot`, `/boot/efi`) and detect from
  authoritative on-disk evidence, in priority order:
  - **systemd-boot** — `bootctl is-installed` = yes, or `$ESP/EFI/systemd/systemd-bootx64.efi`, or `$ESP/loader/loader.conf`
  - **rEFInd** — `$ESP/EFI/refind/refind.conf` or `refind*.efi`
  - **Limine** — `$ESP/EFI/*/limine*.efi`, `$ESP/limine.conf`, or `/boot/limine.{conf,cfg}` (incl. BIOS)
  - **GRUB** — `$ESP/EFI/*/grub*.efi` or `/boot/grub/grub.cfg` (incl. legacy BIOS)
- Version still comes from `pacman -Q`. Verified against synthetic ESP layouts for all four loaders plus the
  no-match case; on the dev box (`UEFI OS` fallback) it now correctly reports `systemd-boot`.

### Files Modified
- `usr/local/lib/roman-os-common.sh` — `TARGET_USER` honours `PKEXEC_UID`; `ensure_root` passes a PATH with `/usr/local/bin` through pkexec
- `usr/local/bin/kiro-report` — Calamares warnings exclude `(Qt):`; IPv4/IPv6 redaction tightened
- `usr/local/bin/kiro-diag` — bootloader detection rewritten to use ESP evidence, not efibootmgr labels

## 2026.06.15

### Desktop entries — localize Comment + GenericName (14 languages)
- Added translated `Comment` and a new descriptive `GenericName` to all seven shipped desktop
  entries, in 14 languages (de, fr, nl, es, it, pt_BR, pt, ru, pl, uk, zh_CN, ja, tr, cs). Brand
  `Name`s and technical `Keywords` stay English.
- The four `kiro-link-*` entries keep their URL `Comment` untouched (a URL is not translatable) and
  receive only a translated `GenericName` ("Web Bookmark").
- GenericName per entry: kiro-audit → "System Integrity Checker"; kiro-sysinfo → "System Information
  Viewer"; kiro-probe-report → "Hardware Report"; the four links → "Web Bookmark".
- **Fixed the `kiro-link-*` menu categories.** The four links had `Categories=X-Kiro;` (no registered
  main category — catch-all off-Kiro). Now `Network;X-Kiro;`: a proper Internet home everywhere, with
  `X-Kiro` still placing them in the Kiro submenu (`kiro.menu` includes them by both category and filename).
- `desktop-file-validate` now clean on all seven (the earlier `Categories` hint is resolved).

### Files Modified
- `usr/share/applications/kiro-audit.desktop`
- `usr/share/applications/kiro-sysinfo.desktop`
- `usr/share/applications/kiro-probe-report.desktop`
- `usr/share/applications/kiro-link-website.desktop`
- `usr/share/applications/kiro-link-code.desktop`
- `usr/share/applications/kiro-link-discussions.desktop`
- `usr/share/applications/kiro-link-releases.desktop`

## 2026.06.13

### kiro-audit — verify package signing (key trust + effective SigLevel)
- `check_pacman_repos` now audits the package-signing rollout: it checks the **Kiro signing key** is trusted in the pacman keyring (`149ABD0C3A0563EE`), and for `nemesis_repo`/`kiro_repo` resolves the **effective SigLevel** — per-repo override if present, otherwise the global `[options]` value (Kiro ships the repos with no per-repo SigLevel, so they inherit the global `Required DatabaseOptional`).
- Verdicts: **FAIL** if a repo enforces (`Required`/`Optional`) while the key is absent (the real footgun — pacman rejects every package, syncs break); **PASS** if enforcing + key trusted; **WARN** if still `Never` (transitional). Verified on a fresh v26.06.13 VM: PASS + PASS, 135/0/0.

### Restore template — stop reverting nemesis to unsigned
- `usr/local/share/kiro/pacman.conf` (the restore template `kiro-fix-pacman-conf` / ATT's `att-fix-pacman-conf` copy back; moved here from kiro-dot-files) still carried `[nemesis_repo] SigLevel = Never`, so a "fix pacman.conf" run silently turned signing back off. Removed the per-repo `SigLevel` from **both** `nemesis_repo` and `chaotic-aur` so they inherit the global `Required DatabaseOptional`, matching the shipped config (no per-repo overrides anywhere).

### Files Modified
- `usr/local/bin/kiro-audit`
- `usr/local/share/kiro/pacman.conf` — dropped per-repo `SigLevel` from nemesis_repo + chaotic-aur

## 2026.06.12

### Kiro onboard themes — 5 branded on-screen-keyboard themes (accessibility)

**What Changed**
- Added **5 Kiro-branded onboard themes** to ship system-wide: **Kiro Aurora** (signature dark slate, blue→green brand keys), **Kiro Daylight** (light, dark-on-white for bright rooms / low-vision light preference), **Kiro Beacon** (amber-on-black accessibility flagship — flat fills, oversized keys, sharp edges, maximum contrast), **Kiro Emerald** (green brand identity), **Kiro Azure** (blue brand identity). Onboard ships on the ISO (added to `kiro-iso-next` 2026-06-12); its stock themes look dated, so these give the on-screen keyboard a cohesive, readable, on-brand look. Names are deliberately distinct from all 17 stock onboard themes. **Default = Kiro Azure**, set system-wide via a gsettings schema override — but this only changes the *default*: a user who picks another theme in onboard's settings keeps their choice. All five remain discoverable in onboard's theme picker and in ATT's Accessibility page.

**Technical Details**
- Each theme is an onboard `.theme` (XML: `key_style`, `roundrect_radius`, `key_size`, gradients, shadow) paired with a `.colors` color scheme (XML `format="2.1"`: layered backgrounds + per-`key_group` fill/stroke/label). All designed for label↔fill contrast: white labels on the dark themes, near-black labels on Daylight's white keys, black-on-amber with white-label overrides on Beacon's dark modifier groups. All 10 files XML-validated. Delivered via **kiro-system-files** (no new package): the PKGBUILD copies the `usr/` tree wholesale, so dropping the files under `usr/share/onboard/themes/` installs them to `/usr/share/onboard/themes/` automatically — no PKGBUILD or `packages.x86_64` change needed. The default is set with a glib **gsettings override** (`usr/share/glib-2.0/schemas/zz-kiro-onboard.gschema.override`, `[org.onboard] theme=…/Kiro Azure.theme`); the `glib2` pacman hook compiles it into `gschemas.compiled` at install — no manual `glib-compile-schemas` step. Validated with `glib-compile-schemas --strict --dry-run` against onboard's real schema.

**Files Modified**
- `usr/share/onboard/themes/Kiro Aurora.theme` + `.colors`
- `usr/share/onboard/themes/Kiro Daylight.theme` + `.colors`
- `usr/share/onboard/themes/Kiro Beacon.theme` + `.colors`
- `usr/share/onboard/themes/Kiro Emerald.theme` + `.colors`
- `usr/share/onboard/themes/Kiro Azure.theme` + `.colors`
- `usr/share/glib-2.0/schemas/zz-kiro-onboard.gschema.override` *(new — default theme)*

## 2026.06.11

### `kiro-audit`: edition-agnostic desktop check (Wayland-aware)

**What Changed**
- `check_desktop()` no longer hardcodes **XFCE + ohmychadwm**. It now passes if **any** valid login session exists, scanning both `/usr/share/xsessions` and `/usr/share/wayland-sessions`. Now that KIB can build any edition (the TWMs, Budgie, …), the old checks threw four false FAILs on every non-default install — e.g. a Budgie install reported `ohmychadwm not installed` / `xfwm4 not installed` / `ohmychadwm.desktop missing` / `xfce.desktop missing` despite being perfectly healthy. Surfaced by the 2026-06-11 Budgie-ISO install test ([kiro-iso/DISTRO_TESTING.md](../../KIRO-ISO-CALAMARES/kiro-iso/DISTRO_TESTING.md)).

**Technical Details**
- Collects session names from both session dirs into an array; `pass` lists them ("desktop session(s) installed: …"), `fail` only when **none** exist (a system with no desktop is the real fault). Added Wayland session coverage — the first Wayland edition (Budgie) would otherwise be invisible to the audit. Kept the `edu-chadwm` dropped-package check (edition-agnostic). Verified against the Budgie test install (sessions found: `qtile`, `budgie-desktop`, `labwc`, `qtile-wayland`) → PASS, replacing the 4 false FAILs.

**Files Modified**
- `usr/local/bin/kiro-audit`

### `kiro-audit`: live-ISO guard (`--force` to override)

**What Changed**
- Running `kiro-audit` in the **live ISO** produced a wall of irrelevant FAILs (read-only squashfs root, archiso packages/config present — most installed-system checks don't apply). It now detects the live ISO (`/run/archiso`) and exits early with a clear banner, **before** the root prompt. `--force` runs it anyway for dev inspection. Verified on the live Budgie ISO: bare run → banner + exit; `--force` → full run.

### `kiro-audit`: cachyos-enabled is a PASS, not a WARN

**What Changed**
- An enabled `[cachyos]` repo no longer WARNs — it's a legitimate state: chwd drivers during install, and going forward `cachyos niri` / `cachyos hyprland` packages (ship the ISO, users do the rest). The keyring + mirrorlist FAIL checks for an *enabled* block stay (without them pacman syncs break).

### `kiro-audit`: MAKEFLAGS accepts Kiro's deliberate `nproc-1`/`nproc-2`

**What Changed**
- `MAKEFLAGS=-jN` a couple below the CPU count no longer WARNs — the Kiro flow scripts deliberately leave 1–2 CPUs free for headroom. PASS when N is in `[nproc-2 .. nproc]` (e.g. `-j14` on a 16-CPU box); WARN only outside that band; FAIL if unset.

## 2026.06.08

### `kiro-audit`: verify GRUB boot-safety hooks in `check_bootloader()`

**What Changed**
- `check_bootloader()` now audits the new `kiro-bootloader-grub` boot-safety hooks: on systems where **GRUB is the live bootloader** it confirms `/usr/bin/kiro-grub-install` + the pacman hook are installed. It deliberately does **not** flag grub being installed on a systemd-boot system — ISO builders legitimately need the `grub` package (archiso optdepend), so grub presence there is normal, not a cleanup failure.

**Technical Details**
- Keys on the **live bootloader** (`/boot/efi/loader/loader.conf` for systemd-boot, `/boot/grub/grub.cfg` for GRUB), not on the `grub` package — `grub` is part of archiso so it is always installed and proves nothing.
- Pre-promotion safe: when GRUB is in use but the boot-safety package isn't shipped yet, the check stays silent (no FAIL/WARN), preserving the clean audit baseline. Name-agnostic for `kiro-bootloader-grub` and `kiro-bootloader-grub-nemesis`.
- Mirrors what was verified live on VirtualBox (BIOS + UEFI) and on bare metal (worf) for the `kiro-bootloader-grub-nemesis` rollout.

**Files Modified**
- `usr/local/bin/kiro-audit` — boot-safety block appended to `check_bootloader()`.

## 2026.06.06

### `99-kiro-optimizations.conf`: refresh stale lqx scheduler comments (kernel-agnostic, accurate)

**What Changed**
- The commented-out `kernel.sched_*` knobs and the RCU stall timeout in `etc/sysctl.d/99-kiro-optimizations.conf` still carried "Not supported on lqx 7.x kernel" / "Not supported on this kernel" notes. Kiro dropped lqx for `linux-cachyos` (default) + `linux-zen` (fallback) on 2026-05-28, so the comments were stale. Investigated each knob on the live `linux-cachyos 7.0.11` kernel and rewrote the comments to state the real, kernel-agnostic reason each stays disabled.
- **Net result: nothing was uncommented.** The TODO's hypothesis ("uncomment what cachyos supports") inverted on inspection — every knob either no longer exists as a sysctl on any modern kernel, or is already at its kernel default, so enabling it would be wrong or a no-op.

**Technical Details**
- `sched_latency_ns` / `sched_min_granularity_ns` / `sched_wakeup_granularity_ns`: removed kernel-wide in 6.6 when EEVDF replaced CFS — absent in both sysctl and debugfs on cachyos/zen/lts/hardened/mainline. EEVDF's nearest equivalent (`base_slice_ns`) is debugfs-only. Comment now documents this; kept commented.
- `sched_migration_cost_ns` (Optional section): not a sysctl since 5.13 — moved to `/sys/kernel/debug/sched/migration_cost_ns`. Documented as debugfs-only.
- `sched_autogroup_enabled`: confirmed **present** on cachyos (`CONFIG_SCHED_AUTOGROUP=y`, value 1). Left commented at the kernel default (enabled) on purpose — disabling only helps dedicated audio/RT boxes; per community-first defaults we keep the better general default and let audio users opt in.
- `sched_rt_runtime_us` / `sched_rt_period_us`: confirmed **present** and already at the exact wanted values (950000 / 1000000 = kernel defaults); `CONFIG_RT_GROUP_SCHED` is off on cachyos. Setting them is a no-op; kept commented.
- `rcu_cpu_stall_timeout`: it is the `rcupdate` module parameter (set via cmdline / `/sys/module/rcupdate/parameters/`), never a sysctl. Comment corrected.
- Also generalised one unrelated stale lqx mention: the active `kernel.unprivileged_userns_clone` comment now cites `linux-hardened` instead of lqx as the kernel that defaults it to 0.
- Verified empirically with `/proc/sys/kernel/`, `/proc/config.gz`, and `sudo ls /sys/kernel/debug/sched/`. No active settings changed — comments only.

**Files Modified**
- `etc/sysctl.d/99-kiro-optimizations.conf`

## 2026.06.04

### `kiro-audit`: verify `kiro-calamares-tweak-tool` removal (Calamares cleanup)

**What Changed**
- Added a check to the "Calamares cleanup" section confirming `kiro-calamares-tweak-tool` is removed post-install. It is an install-time-only tool; if not stripped during Calamares it leaks onto the user's installed system. The removal itself was fixed separately (added to the Calamares removal list, 2026-06-04); this is the verification hook so a regression can't pass silently — per the "testcase what we create" rule.

**Technical Details**
- One line next to the existing `calamares` / `mkinitcpio-archiso` / `memtest86+` checks: `pkg_missing kiro-calamares-tweak-tool` → `fail` on presence (a real leak, not a warn).

**Files Modified**
- `usr/local/bin/kiro-audit`

### `kiro-audit`: fix stale `ohmychadwm-git` package name (false FAIL)

**What Changed**
- `kiro-audit` checked for the package `ohmychadwm-git`, but Phase 2 of the Kiro package-naming work dropped the `-git` suffix — the installed package is now `ohmychadwm`. Every installed system (verified on metal boxes picard + riker against ISO `v26.06.04`) reported a spurious `FAIL ohmychadwm-git not installed` even though the WM, binary, and session file are all present. Renamed the check to `ohmychadwm` so the audit reports 0 FAIL on a correct install — important ahead of the betatester ISO, since the audit ships in the image.

**Technical Details**
- Three references updated: the desktop check (`check_desktop`), the `pacman -Qk` integrity exclude (`ohmychadwm` legitimately reports expected missing files as a local `/usr/local/bin` install), and the man page synopsis.
- Swept the script and repo for other stale `-git` package names — this was the only one.
- Also corrected a stale man-page line that claimed the audit checks for `multilib` in pacman.conf — multilib has been off by default since 2026-05-28 and that check was already removed from the script. Man page now reflects the real repo checks (nemesis_repo + chaotic-aur present, cachyos commented out).

**Files Modified**
- `usr/local/bin/kiro-audit`
- `usr/share/man/man8/kiro-audit.8`

### `kiro-audit`: btrfs snapshot verification hook

**What Changed**
- Added a `check_btrfs_snapshots` section to `usr/local/bin/kiro-audit` — the verification hook for the opt-in btrfs snapshot stack that ATT's Btrfs page installs. It confirms the Kiro layout and policy actually landed on a btrfs box, per the "testcase what we create" rule.
- Behaviour is opt-in-aware so it never produces false failures: a non-btrfs root (incl. the live ISO) passes-and-returns ("not applicable"); a btrfs root with no snapshot stack passes-and-returns ("opt-in via ATT, expected default"). Only once the user has opted in does it verify the full configuration.
- When set up, it checks: the four-package Garuda stack (`snapper`, `snap-pac`, `btrfs-assistant`, `btrfsmaintenance`); the snapper `root` config; `TIMELINE_CREATE=no` (Kiro policy — no hourly timeline); `snapper-cleanup.timer` enabled; `snapper-timeline.timer` NOT enabled; and `btrfsmaintenance-refresh.path` (warn-only). It also checks the ISO-side `@snapshots → /.snapshots` subvolume that Calamares pre-stages.

**Technical Details**
- Mirrors the policy in `~/btrfs.md` and the exact setup sequence ATT runs (`launch_btrfs_setup_in_terminal`), so the audit and the installer agree.
- `--fix` remediations added for the three safe, idempotent policy items: set `TIMELINE_CREATE=no`, enable `snapper-cleanup.timer`, disable `snapper-timeline.timer`. Package install and `create-config` are deliberately left to ATT's interactive flow (not auto-fixed).
- Root fstype and the `TIMELINE_CREATE` parse are guarded with `|| echo ""` / `|| true` so a missing line can't trip the `set -euo pipefail` ERR trap. `findmnt` is used for fstype + the `/.snapshots` mount check (util-linux, always present); all checks are kernel-agnostic. `bash -n` passes; full run needs a btrfs root + root (Erik to verify post-build).

**Files Modified**
- `usr/local/bin/kiro-audit`

### `kiro-audit`: disk format & LUKS encryption verification hook

**What Changed**
- Added a `check_disk_format` section to `usr/local/bin/kiro-audit` — the verification hook for the partitioning/filesystem choice now offered in Calamares (ext4 or btrfs root, optional full-disk LUKS, optional encrypted swap). Reports the chosen layout as INFO and, when LUKS is in use, asserts the encryption is sound. Closes the gap where nothing in the toolchain confirmed an encrypted install was correctly set up.
- Conditional/no-false-failure by design: an unencrypted install (the default, and the live ISO) prints one INFO line + a single pass ("no LUKS containers — expected default") and returns. Only when `crypto_LUKS` devices are actually present does it run the encryption asserts.
- When encrypted, it checks: each LUKS container is **LUKS2** (warn on legacy LUKS1/PBKDF2); the initramfs carries a `sd-encrypt`/`encrypt` unlock hook (else a future `mkinitcpio` rebuild would lock the box out); `/crypto_keyfile.bin` is `600 root:root` (fail + `--fix chmod 600` if loose); and at least one active dm-crypt mapping exists. INFO lines report root fstype/source, container list, and per-container cipher.

**Technical Details**
- Detection is `lsblk -rpno NAME,FSTYPE | awk '$2=="crypto_LUKS"'`; LUKS version/cipher via `cryptsetup luksDump`. dm-crypt liveness counts the tab-bearing `dmsetup ls --target crypt` lines (skips the "No devices found" string). Kernel-agnostic and util-linux/cryptsetup only.
- Verified live against all three production-ISO VMs (2026-06-04): unencrypted ext4 → +1 pass; LUKS-ext4 → +5 pass; LUKS-btrfs (2 containers incl. encrypted swap) → +7 pass; all 0 WARN / 0 FAIL. `bash -n` passes. `/kiro-syscheck` already invokes `kiro-audit`, so its summary now carries the encryption asserts with no separate change needed.

**Files Modified**
- `usr/local/bin/kiro-audit`

### `kiro-report`: disk encryption hint

**What Changed**
- Added a `section_encryption` block to `usr/local/bin/kiro-report` so a help report states the partitioning/encryption choice up front — the first thing a maintainer needs on any boot/unlock/install issue. Mirrors the new `kiro-audit` `check_disk_format` (the two tools now agree on how encryption is reported).
- Three fields: root filesystem (ext4/btrfs), encryption (`none` or `LUKS2 full-disk (N container(s))`), and encrypted swap (yes/no). Unencrypted installs print `none` and nothing else.

**Technical Details**
- kiro-report already runs as root, so the LUKS version comes straight from `cryptsetup luksDump`; no device UUIDs are printed and the output flows through the existing `redact()` (the `luks-<uuid>` mapper names would be scrubbed regardless — verified 0 raw UUIDs in the generated reports).
- Encrypted-swap detection uses `lsblk -rno FSTYPE,TYPE` matching a `swap`+`crypt` row, **not** `swapon` — the active encrypted swap surfaces as `/dev/dm-N`, which hides the crypt layer. Verified live on all three production-ISO VMs: unencrypted → `none`; LUKS-ext4 → LUKS2, swap no; LUKS-btrfs → LUKS2 (2 containers), swap yes.

**Files Modified**
- `usr/local/bin/kiro-report`

## 2026.06.01

### New tool: `kiro-report` — one public-safe diagnostic file for Kiro Discussions

**What Changed**
- Added `usr/local/bin/kiro-report`, which produces a single log file a user can paste into the Kiro Discussions board when asking for help. It bundles the full `kiro-diag` snapshot **plus** the dynamic failure evidence a maintainer actually needs to debug — then redacts every system-identifying value so it is safe to post on a public board. `kiro-diag` itself is left untouched (it stays the live, colored, on-screen tool referenced in ATT).
- Report contents: the complete `kiro-diag` snapshot; **graphics driver packages** with versions (Xorg `xf86-video-*`/`xf86-input-*`, Mesa, Vulkan, VA-API/VDPAU, NVIDIA); the **full list of explicitly-installed packages** (`pacman -Qe`); **failed systemd units**; **this-boot journal errors** (priority err+); **kernel ring-buffer errors** (`dmesg`); **recent pacman transactions**; and the **Calamares install log** (`/var/log/Calamares.log`) when present.
- Redaction replaces IPv4/IPv6 addresses, MAC addresses, UUIDs, the systemd machine-id, the hostname, and the username (incl. `/home/<user>`) with placeholders. The file footer reminds the user to skim it once before posting.
- Flags: `--help` / `--version` / `--output PATH`. Default output `~/kiro-report-YYYYMMDD-HHMMSS.log` (timestamped, never overwrites), chowned back to the invoking user. Ships a man page `usr/share/man/man8/kiro-report.8`; added a `kiro-report(8)` cross-reference to `kiro-diag.8`.

**Technical Details**
- Reuses `kiro-diag` by invoking it inside a colors-blanked subshell and piping through a single `redact()` `sed -E` filter, so the section logic stays in one place (DRY) rather than duplicated. The subshell blanks the color vars and `redact()` also strips any residual ANSI, so the file is always plain text even though the parent's stdout is a TTY.
- Redaction order matters: MAC and dashed-UUID rules run before the broader machine-id (`\b[0-9a-f]{32}\b`) and IPv6 (`::`-anchored) rules. The IPv6 rule only fires on the `::` double-colon, so **PCI addresses** (`0000:03:00.0`) survive intact — verified on the dev box that IP/IPv6/machine-id (both the `initrd=` path and `systemd.machine_id=`)/root-UUID/hostname/username are all stripped while PCI IDs, timestamps and Calamares warnings are preserved. Per the agreed privacy line, the partition UUID is redacted but the timezone is kept (coarse, useful for mirror/time-sync issues).
- All log pulls are guarded with `|| true` so `set -Euo pipefail` + the kiro-common ERR trap don't fire on empty `grep`/`journalctl` results. No PKGBUILD change — the package `cp -a`'s `usr/` wholesale, so the new script + man page are picked up automatically. `bash -n` and `--help` verified; full run needs root (Erik to verify post-build with `sudo kiro-report`).
- Related: complements the existing `kiro-calamares-log` (Calamares-only summary); `kiro-report` is the all-in-one bundle.

### New tools: `kiro-set-cores-min1` / `kiro-set-cores-min2` — leave 1–2 cores free for makepkg

**What Changed**
- Added `usr/local/bin/kiro-set-cores-min1` and `kiro-set-cores-min2`, companions to `kiro-set-cores`. Where `kiro-set-cores` sets `MAKEFLAGS=-jN` to *all* cores, these set it to `N-1` and `N-2` respectively (8 cores → `-j7` / `-j6`), leaving 1 or 2 cores free so the desktop stays responsive during long AUR builds. Both also flip `PKGEXT` to `.pkg.tar.zst` like the original.
- Each ships the standard `--help` / `--version` / `--dry-run` flags and a man page (`kiro-set-cores-min1.8`, `kiro-set-cores-min2.8`). Added to the README command table. These back the ATT full-package menu entries and run standalone from the terminal.

**Technical Details**
- Cores read via `nproc`; target = `nproc - RESERVE` (RESERVE=1/2), floored to `-j1` with a warn on low-core boxes.
- The sed is broadened from the original's narrow `#MAKEFLAGS="-j2"` match to `s/^#?MAKEFLAGS=.*/MAKEFLAGS="-jN"/` (with `-E`), so it works whether the line is the commented default or already set by a prior `kiro-set-cores` run, and is idempotent. Verified the `#-- Make Flags:` documentation comment is left untouched (only the `#MAKEFLAGS=` line carries `MAKEFLAGS=`).
- Both scripts source `roman-os-common.sh` like the rest of the suite; verified `bash -n`, `--help`, and `--dry-run` on the dev box (16 cores → `-j15` / `-j14`). No PKGBUILD change — the package `cp -a`'s `usr/` wholesale.

### New tool: `kiro-calamares-log` — summarise the Calamares installer log

**What Changed**
- Added `usr/local/bin/kiro-calamares-log`, a companion to `kiro-audit`. It reads `/var/log/Calamares.log` and prints a short readable summary instead of the ~1600-line raw dump: header (version, branding, target disk, user, host), the install job **timeline with per-job duration** (Kiro modules marked `*`), real **WARNINGs** (benign Qt/chcon/EFI-probe/branding noise filtered), **ERRORs/tracebacks**, and a one-line **CLEAN / FAILED verdict**.
- Switches: `--full` (append raw log), `--scrub` (redact host/user/IP), `--save [FILE]` (write colour-free plain text), `--upload` (post the scrubbed summary to a paste host and print the URL — implies `--scrub`). Plus the standard `--help` / `--version`.
- Ships a man page `usr/share/man/man8/kiro-calamares-log.8` and is listed in the README command table.

**Technical Details**
- Parses only the **last** `=== START CALAMARES` session (the log accumulates across launches). Completion is detected by Calamares reaching its final job ("Saving files for later"), so the normal 42/43 job count is correctly read as CLEAN (job 43 is Calamares' internal finalize), not "incomplete".
- Per-job duration = gap to the next job's timestamp; the last job is bounded by the final log timestamp.
- Warning filter keeps only `[2]` lines carrying an actual `WARNING` token (drops the bare C++ function-signature context lines), then removes a known-benign set. `--scrub` anchors the IP regex with word boundaries so it doesn't clip the dotted Calamares version string.
- Log is world-readable, so no root needed. Verified end-to-end on a real VM install (VERDICT: INSTALL CLEAN, 0 errors). No PKGBUILD change — the package `cp -a`'s `usr/` wholesale.

### kiro-calamares-log: `--upload` paste host switched from 0x0.st to paste.c-net.org

**What Changed**
- The `--upload` target moved from `https://0x0.st` to `https://paste.c-net.org`. 0x0.st is blanket-blocked as a malware/abuse-hosting domain by mainstream threat-intel blocklists — confirmed in the field that ISP filters (Telenet Safesurf/Safespot, powered by SAM Seamless Network), Proximus's filter, and Bitdefender all block it independently — so `--upload` failed for most users regardless of their network, not because of a script bug.
- `--upload` failures now print curl's actual error (e.g. connection reset, block page) instead of a blank "failed", so a future host-level block is diagnosable.

**Technical Details**
- paste.c-net.org takes a **raw POST body** and returns the paste URL directly, so the call changed from multipart `curl -F'file=@-;filename=...'` to `curl --data-binary @- "${PASTE_SERVICE}/"`.
- Replaced the `2>/dev/null` on the upload curl with a temp file capturing stderr, surfaced in the failure message. Verified the new host round-trips (upload → fetch back byte-for-byte) and is not DNS-hijacked. `--save` remains the always-reliable fallback since *any* anonymous paste host can eventually be category-flagged.

### kiro-audit: microcode check is now VM-aware

**What Changed**
- `check_microcode` no longer reports `FAIL  No microcode image found in /boot` on a virtual machine. A VM has no real CPU to update, so there is legitimately no `intel-ucode.img` / `amd-ucode.img` in `/boot` — flagging it as a failure produced a false negative on every VirtualBox/QEMU audit. On a VM it now reports `PASS  No microcode image in /boot — expected, this is a virtual machine (not real metal)`. On bare metal a missing image is still a real `FAIL`.

**Technical Details**
- Added a `systemd-detect-virt --vm --quiet` branch between the AMD `elif` and the final `fail`. The function detects the VM itself (the `is_vm` flag in `main()` is a local, not visible inside `check_microcode`).
- Verified `bash -n` clean; the dev box (bare metal) correctly keeps the FAIL path.

**Files Modified**
- `usr/local/bin/kiro-audit`

## 2026.05.31

### Split `kiro-skell` into a fast default + `kiro-skell-all` full-backup variant

**What Changed**
- The old `kiro-skell` (which backed up the **whole** `~/.config` before copying `/etc/skel`) was renamed to **`kiro-skell-all`** — behavior unchanged.
- A new, faster **`kiro-skell`** is now the default: it backs up **only** the `~/.config` entries that `/etc/skel/.config` will overwrite, then copies all of `/etc/skel` as before. Full `~/.config` backups had become slow as caches grew (multi-GB); the only data at risk is what gets overwritten, so that is all the new default backs up.
- The `/etc/skel` copy step is identical in both (overwrite all).

**Technical Details**
- New `kiro-skell` scans `/etc/skel/.config/*` at runtime and backs up each matching `~/.config/<name>` into `~/.config-backup-<stamp>/.config/`. Dynamic scan (not a hardcoded list) so it auto-adapts per ISO and never drifts stale.
- Both scripts stay self-contained (inline helpers, no `roman-os-common.sh`) so ATT's `skell` keeps fetching `kiro-skell` verbatim — `skell` now tracks the fast variant on the next `fetch-configs.sh` run.
- Man pages: new `kiro-skell-all.8`; `kiro-skell.8` rewritten for the scoped behavior; both cross-reference via `SEE ALSO`. Fixed the stale `FILES` line that listed `roman-os-common.sh` as a dependency.
- No PKGBUILD change needed — the package `cp -a`'s `usr/` wholesale, so the renamed + new files ship automatically.
- Verified: `bash -n` clean on both; `--dry-run` on each prints the expected backup scope.

**Files Modified**
- `usr/local/bin/kiro-skell` (new, fast) and `usr/local/bin/kiro-skell-all` (renamed from `kiro-skell`)
- `usr/share/man/man8/kiro-skell.8` (rewritten), `usr/share/man/man8/kiro-skell-all.8` (new)
- `README.md`, `CLAUDE.md`

### `kiro-skell` made self-contained — single source of truth for ATT's `skell`

**What Changed**
- `kiro-skell` no longer sources `/usr/local/lib/roman-os-common.sh`; it inlines the helpers it uses (colors, `log_info`, `log_success`, `show_help`, `show_version`, `execute_or_dryrun`, ERR trap). It now runs unchanged on any distro. This makes it the **single source of truth** for ATT's `skell` (cross-distro, where `roman-os-common.sh` does not exist) — ATT fetches this file verbatim and ships it as `usr/bin/skell`. The copy direction is one-way: ATT pulls from here; this repo stays unaware of ATT.
- The intro block is now colored (`log_section` + body) instead of a plain `echo` banner, and the whole script names itself via `"$(basename "$0")"`, so the same bytes print `kiro-skell` here and `skell` when ATT ships it — no rewriting on copy.

**Technical Details**
- Documented exception added to `CLAUDE.md` (Shared library section): `kiro-skell` is the one script that does not source `roman-os-common.sh`; keep the inline helpers in step with the library by hand if its log format changes.
- Verified: `bash -n` clean; `--help`, `--version`, `--dry-run` all work standalone (no library present); run under the name `skell` it prints `skell`.

**Files Modified**
- `usr/local/bin/kiro-skell`
- `CLAUDE.md`

### Renamed `kiro-skel` → `kiro-skell` (single-L → double-L) for naming consistency

**What Changed**
- The skel-restore command is now consistently spelled with two L's. The shipped binary was already `usr/local/bin/kiro-skell`, but its man page and README still called it `kiro-skel`; that mismatch is now closed. The double-L `kiro-skell` (Kiro) / `skell` (ATT) spelling is the canonical convention, recorded in `Kiro-HQ/ASSISTANT.md`.

**Technical Details**
- `/etc/skel` (the Linux skeleton path) is untouched — only the *command name* changed. The rename never touches filesystem paths.
- Man page `usr/share/man/man8/kiro-skel.8` renamed to `kiro-skell.8` (via `git mv`); `.TH KIRO-SKEL` → `.TH KIRO-SKELL`, date bumped to 2026-05-31, all in-body `kiro-skel` references updated.
- `README.md` tool table: `kiro-skel` → `kiro-skell`.
- `usr/local/bin/kiro-skell` help/intro text referred to the command as bare `skel` ("run skel in a terminal") — updated to `kiro-skell` so it names a command that actually exists.

**Files Modified**
- `usr/share/man/man8/kiro-skell.8` (renamed from `kiro-skel.8` + content)
- `README.md`
- `usr/local/bin/kiro-skell`

### `kiro-probe` offline save + `kiro-probe-report` HTML insight page

**What Changed**
- `kiro-probe` gains `-s`/`--save [DIR]`: instead of uploading to linux-hardware.org, it saves the probe locally (`hw.info` directory + `hw.info.txz`) and generates a readable HTML insight report from it. This is the offline path — useful when the upload server is down (as happened) or when you just want the data as one local file. Default upload behaviour is unchanged when `--save` is absent.
- New `kiro-probe-report` command turns any saved probe (an `hw.info.txz` archive or `hw.info` directory) into a single self-contained, colour-coded HTML page: system summary cards, a device-status overview (works / detected / failed), a grouped device table, and collapsible raw-log sections (inxi, lscpu, dmidecode, lsblk, smartctl, sensors, glxinfo, lspci, lsusb, nmcli, systemd-analyze, dmesg). Runs without root and contacts no server.

**Technical Details**
- New `usr/local/lib/kiro-probe-report.py` — the HTML generator (the repo's first Python file). Parses the probe's `host` (key:value) and `devices` (`;`-delimited, with a per-device status field) plus selected `logs/`, and emits one dependency-free HTML file with inline CSS. Status colour-codes green/blue/red. Kept as a silent helper invoked by a bash wrapper, so the user-facing layer still sources `roman-os-common.sh` per repo convention. `ruff` clean.
- New `usr/local/bin/kiro-probe-report` — bash wrapper (sources `roman-os-common.sh`, `--help`/`--version`/`--dry-run`). Resolves a `.txz` (extracted to a temp dir cleaned by an EXIT trap) or a directory to the dir holding `host`, then calls the generator. `chown`s the output back to `$SUDO_USER` when run under sudo.
- Two bugs found and fixed in the wrapper during testing: (1) `resolve_info_dir` originally returned its path via command substitution, so the `WORKDIR` it set lived only in the subshell — the temp dir leaked and parent `WORKDIR` stayed empty. Rewritten to set a global `INFO_DIR` (no subshell). (2) The `cleanup` EXIT-trap function ended on a short-circuited `[[ ... ]] && rm`, returning non-zero when there was nothing to clean; under `set -Euo pipefail` that tripped `roman-os-common.sh`'s ERR trap and printed a spurious "ERROR DETECTED" banner (with a misleading stale `BASH_COMMAND`). Added an explicit `return 0`.
- The HTML carries a prominent local-only privacy banner: the raw-log sections embed hardware serial numbers (dmidecode/smartctl/lsblk), so the file is marked do-not-publish.
- New man page `kiro-probe-report.8`; `kiro-probe.8` updated for `--save`. Both lint clean (`groff -man -z`). Verified end-to-end against a real saved probe: both `.txz` and directory inputs render identically (132 KB), bad input exits 1, no temp-dir leak, no spurious ERR banner.

**Files Modified**
- `usr/local/bin/kiro-probe` (added `--save`)
- `usr/local/bin/kiro-probe-report` (new)
- `usr/local/lib/kiro-probe-report.py` (new)
- `usr/share/man/man8/kiro-probe-report.8` (new)
- `usr/share/man/man8/kiro-probe.8` (updated)

### `kiro-audit` — detect virtual machine and close with an anti-panic note

**What Changed**
- `kiro-audit` now detects when it runs inside a virtual machine and ends its output with a clear sentence explaining that the audit is intended for real (bare-metal) hardware, so the expected live-ISO/VM failures (memtest86+ missing files, live-only cleanup checks, etc. — ~22 FAILs on the live ISO) don't read as a broken install. All checks still run; nothing is skipped.
- The run header also gains a `Virt :` line naming the hypervisor (e.g. `oracle` for VirtualBox) when one is detected.

**Technical Details**
- Detection via `systemd-detect-virt --vm --quiet` in `main()` (local `is_vm`/`vm_type`); `|| true` guards the type lookup against the ERR trap. No new dependency — `systemd-detect-virt` ships with systemd.
- The closing banner is emitted as the last output, after the PASS/WARN/FAIL summary and the normal completion banner, so it stays visible even when `exit 1` fires on failures. The summary tail was refactored to compute a local `rc` and `exit "${rc}"` once at the end instead of an inline `exit 1`. `bash -n` clean.
- The closing message is hand-wrapped into short lines (longest ~62 cols) so it fits inside the 76-col banner and the alacritty terminal without wrapping mid-word.
- Verified live on the VirtualBox live-ISO VM (`liveuser`): `systemd-detect-virt` → `oracle`, banner prints after the 22-failure summary.

### Settings Manager entries — Kiro System Audit + System Information (inxi)

**What Changed**
- Two new XFCE Settings Manager launchers so Kiro's system tools are reachable from the graphical Settings dialog, not just the terminal:
  - **Kiro System Audit** → runs `kiro-audit` (Kiro K icon).
  - **System Information** → runs a complete `inxi -Fxxxz` report (familiar from ArcoLinux).
- Both open in **alacritty** (the terminal common to every Kiro environment, not only XFCE) and stay open with a `Press Enter to close...` prompt so the output is readable.

**Technical Details**
- New files `usr/share/applications/kiro-audit.desktop` and `usr/share/applications/kiro-sysinfo.desktop`. Category line `System;Settings;X-XFCE-SettingsDialog;X-XFCE-SystemSettings;` — `X-XFCE-SettingsDialog` is what surfaces them in the Settings Manager, `X-XFCE-SystemSettings` groups them under **System** (without it they land in *Other*).
- Exec uses `alacritty -e bash -c "<cmd>; echo; read -rp 'Press Enter to close...'"` instead of relying on the XFCE terminal helper (`exo-open`): on the live ISO that helper is set to an undefined `custom-TerminalEmulator`, so `Terminal=true` launchers silently fail. Explicit alacritty sidesteps it and works across DEs.
- `inxi -Fxxxz`: `-F` full report, `-xxx` maximum extra data, `-z` filters MAC/IP/identifying data. `inxi` already ships in `archiso/packages.x86_64`.
- Both add `TryExec=` (`kiro-audit` / `inxi`) so the entry auto-hides if the tool is removed.
- Both files pass `desktop-file-validate`; verified live in the Settings Manager under System.

### Settings Manager — surface 5 stock system tools in the System overview

**What Changed**
- Five standard tools that previously lived only in the app menu now also appear in the System group of the Settings Manager, so users get a single "what can I change / what's installed" overview (a deliberate feel-of-control selling point carried over from ArcoLinux). They remain in the app menu exactly as before — these entries are additive, not replacements:
  - **Firewall** (`firewall-config`) — Kiro ships firewalld default-on, so a firewall GUI in System Settings is the most natural fit.
  - **Timeshift** (`timeshift-launcher`) — backups / system restore.
  - **Disks** (`gnome-disks`) — drive / partition / SMART management.
  - **Advanced Network Configuration** (`nm-connection-editor`).
  - **Disk Usage Analyzer** (`baobab`).
- GParted was intentionally left menu-only (destructive root tool — avoid accidental clicks). hardinfo2 left out too (the inxi entry covers system info).

**Technical Details**
- Implemented as same-desktop-ID override copies shipped to `usr/local/share/applications/` (higher XDG_DATA_DIRS precedence than `/usr/share/applications`), so the menu entry stays identical — no duplicate icon — and gains the settings categories. Full upstream files copied verbatim to preserve translations.
- **Two categories are required**, not one: `xfce4-settings-manager` only shows an entry that has **both** the freedesktop `Settings` main category **and** `X-XFCE-SettingsDialog`. `X-XFCE-SettingsDialog` alone is insufficient — this is why Timeshift (`System;` only) and Disks (`...Utility...`) initially did not appear until `Settings;` was added. `X-XFCE-SystemSettings` places them in the **System** group.
- Every override carries `TryExec=<binary>` so that if the user removes the underlying app, the Settings Manager auto-hides the now-dead entry (the shipped `.desktop` is owned by edu-system-files, not the app's package, so it would otherwise persist as a broken icon).
- All five pass `desktop-file-validate`; verified deployed live on the VM.

**Files Modified**
- `usr/local/bin/kiro-audit`
- `usr/share/applications/kiro-audit.desktop` (new)
- `usr/share/applications/kiro-sysinfo.desktop` (new)
- `usr/local/share/applications/firewall-config.desktop` (new)
- `usr/local/share/applications/timeshift-gtk.desktop` (new)
- `usr/local/share/applications/org.gnome.DiskUtility.desktop` (new)
- `usr/local/share/applications/nm-connection-editor.desktop` (new)
- `usr/local/share/applications/org.gnome.baobab.desktop` (new)

## 2026.05.29

### `kiro-audit` — verify cachyos keyring/mirrorlist when `[cachyos]` is active

**What Changed**
- `check_pacman_repos` now goes further when it finds `[cachyos]` uncommented in `pacman.conf`: it confirms `cachyos-keyring` is installed and `/etc/pacman.d/cachyos-mirrorlist` exists. An active cachyos repo without those breaks every pacman sync (signature rejection / missing `Include=` target). This is the verification hook for the new ATT Pacman-page CachyOS toggle, which bootstraps both (bundled packages + `setup-cachyos`, mirroring Chaotic-AUR) before enabling the repo.

**Technical Details**
- Two new checks inside the existing `if grep -q '^\[cachyos\]'` branch: `pkg_installed cachyos-keyring` → PASS/FAIL, and `[[ -f /etc/pacman.d/cachyos-mirrorlist ]]` → PASS/FAIL. The commented-out and absent branches are unchanged (still PASS/WARN — Kiro ships it commented, opt-in). No new `main()` entry; folded into `check_pacman_repos`. `bash -n` clean.

### `kiro-audit` — new `check_chwd` surfaces the Calamares chwd-skip marker

**What Changed**
- New audit section warns when `/var/log/kiro-chwd-skipped.log` exists on the installed system. That marker is written by the Calamares chwd module when `chwd --autoconfigure` could not install the detected driver profile (e.g. a profile package missing from the configured repos), in which case the install now completes on the open driver instead of aborting. Without this check the fallback would be silent — the user would have a working but driver-less system and no signal as to why. Paired with the non-fatal chwd change in [kiro-calamares-config](/home/erik/KIRO/kiro-calamares-config/CHANGELOG.md): that change keeps the install alive, this check makes the skip visible.

**Technical Details**
- WARN (not FAIL): a skipped profile means the system is usable on nouveau/mesa, not broken. The marker body (reason + retry hint) is echoed indented under the WARN line. When no marker exists → PASS (covers both "autoconfigure succeeded" and `driver=free`).
- Section title `chwd driver install`. Called between `check_nvidia` and `check_bootloader` in `main()`. Kernel-agnostic (no kernel-specific paths).
- `bash -n` clean.

**Files Modified**
- `usr/local/bin/kiro-audit`

### `kiro-audit` — `check_pacman_repos` now checks the cachyos opt-in state

**What Changed**
- `check_pacman_repos` gained a cachyos row. Kiro now ships `[cachyos]` commented out in the installed `/etc/pacman.conf` (kiro_final disables it after install — see [kiro-calamares-config](/home/erik/KIRO/kiro-calamares-config/CHANGELOG.md)). The audit reports: PASS when `[cachyos]` is commented (opt-in, as shipped); a soft WARN if it is active (legitimate only if the user re-enabled it on purpose) or absent entirely.

**Technical Details**
- Soft WARN rather than FAIL on an active repo: re-enabling cachyos is a valid user choice, so it must not read as a defect. Matches the existing "intended-state, advisory" tone of the repo checks.
- chaotic-aur remains a FAIL-if-missing check: it is the update source that backs `linux-cachyos` once cachyos is off, so its absence is a real defect.

**Files Modified**
- `usr/local/bin/kiro-audit`

---

## 2026.05.28

### `kiro-audit` — new `check_tuned_profile` for the tuned-ppd pin

**What Changed**
- New audit section asserts `/etc/tuned/ppd_base_profile == performance` and `tuned-adm active == throughput-performance`. Catches the regression where the upstream `tuned` package's pacman install writes `ppd_base_profile=balanced` into the install target, short-circuiting `ppd.conf`'s `default=performance` fallback. Two bare-metal installs (Picard + Riker, both v26.05.28) landed on `balanced` instead of `throughput-performance` — kiro-audit gave 128/0/0 because it had no tuned-side check. This closes the gap so the kiro_final pin (kiro-calamares-config side) is verifiable instead of silent.
- Paired with the kiro_final write in [kiro-calamares-config](/home/erik/KIRO/kiro-calamares-config/CHANGELOG.md) — the write fixes the install, the audit check guarantees we notice if the pin is ever lost again.

**Technical Details**
- Helper handles the "tuned not installed" case (warn, skip), the missing-`tuned-adm`-binary case (warn, skip), and unknown active-profile string (fail with the actual value). Section title `tuned-ppd power profile`. Kernel-agnostic (tuned/tuned-ppd are not kernel-tied).
- Called between `check_resolved_config` and `check_tumbler` in `main()`.
- `bash -n` clean.

**Files Modified**
- `usr/local/bin/kiro-audit`

---

### `show_version` — query pacman at runtime instead of hardcoding

**What Changed**
- `show_version()` in `roman-os-common.sh` was printing a hardcoded `version 1.0.0` + frozen `Created: 2026-04-20` line for 17 of the 18 `usr/local/bin/` scripts — directly violating the repo's own "Never hardcode a version string. Query the owning package." rule in CLAUDE.md. Only `kiro-audit` did it correctly (inline). The helper now resolves the caller's path and queries `pacman -Qqo` → `pacman -Q`, so `--version` matches what pacman knows; falls back to `<script> (not installed via pacman)` when run from a source tree. One central fix lifts all 17 scripts at once.

**Technical Details**
- Second parameter to `show_version` is now the script path (defaults to `$0`), so call sites that pass `"$0"` or `"$(basename "$0")"` continue to work; passing `${BASH_SOURCE[0]}` from a caller gives the most accurate resolution under symlinks.
- Uses `realpath` to follow symlinks before the pacman lookup (matches `kiro-audit`'s working pattern).
- `kiro-audit`'s inline `-v|--version` block migrated to call `show_version "$(basename "$0")" "${BASH_SOURCE[0]}"` instead of duplicating the pacman-query pattern. Single source of truth across all 18 scripts now.

**Files Modified**
- `usr/local/lib/roman-os-common.sh`
- `usr/local/bin/kiro-audit`

---

### `kiro-audit` is now **kernel-agnostic**

**What Changed**
- `kiro-audit` is now **kernel-agnostic**. It used to hardcode `linux-lqx` in `check_kernel` and `check_mkinitcpio`, so any non-lqx Kiro install (linux-zen / linux-hardened / linux-cachyos / multi-kernel) reported 6 spurious FAILs — proven on a CachyOS install 2026-05-27 (`7.0.10-1-cachyos` installed cleanly, audit FAILed on "expected linux-lqx" + missing lqx vmlinuz/initramfs/packages/preset). Detection now happens at runtime; whatever kernel ships, the audit validates it. Last hardcoded component of the kernel-agnostic set — build-side selector (`kiro-iso-next`) and installer (`kiro_kernel` in `kiro-calamares-config-next`) were already done.

**Technical Details**
- New `detect_kernels()` helper: scans `/usr/lib/modules/*/pkgbase` (every Arch kernel package drops one), emits a sorted/deduped list. Shared by `check_kernel` + `check_mkinitcpio` so both reason from the same source.
- `check_kernel` rewritten: detects installed kernel(s), reports them, then per-kernel loops over `/boot/vmlinuz-${k}`, `/boot/initramfs-${k}.img`, `${k}` package, `${k}-headers`. The running-kernel match is now anchored on `/usr/lib/modules/$(uname -r)/pkgbase` rather than a substring match on `uname -r` — catches the mid-upgrade-before-reboot case as a WARN (not a hard FAIL).
- `check_mkinitcpio` preset block rewritten: per-kernel `${k}.preset` check via the same `detect_kernels`. The stock-`linux.preset`-leftover check is preserved but gated on `! pkg_installed linux` — when `linux` is the chosen kernel, the per-kernel loop covers it and the leftover check is skipped (no double-counting, no false FAIL).
- Man page (`kiro-audit.8`) — kernel section + mkinitcpio bullet rewritten to describe runtime detection; date bumped to 2026-05-28.
- `bash -n` clean. No script structure / template changes — only `check_kernel`, the preset block in `check_mkinitcpio`, and the new helper.

**Files Modified**
- `usr/local/bin/kiro-audit`
- `usr/share/man/man8/kiro-audit.8`

---

### `kiro-enable-ssh`: pacman -Sy + liveuser password on the live ISO

**What Changed**
- `kiro-enable-ssh` now refreshes the pacman database (`pacman -Sy`) before installing openssh — the live ISO's seeded `/var/lib/pacman/sync/` can be empty or stale, so without this the install would fail (or warn loudly).
- On the **live ISO only** (detected via `/run/archiso/bootmnt`), the script now sets `liveuser`'s password to `erik`. Without a password, sshd's password auth refuses the login even after the daemon is up — so the previously-correct opt-in was silently unusable for `liveuser`. The earlier "live sshd is root-only" assumption was wrong: the airootfs `sshd_config.d/10-archiso.conf` permits `PasswordAuthentication yes` + `PermitRootLogin yes` with no `AllowUsers`/`DenyUsers` restriction — the real blocker was just the missing password.

**Technical Details**
- New step ordering in `main()`: refresh pacman db → install openssh → enable sshd → open firewall → set liveuser password (live-ISO-gated).
- `/run/archiso/bootmnt` is the canonical live-ISO marker (archiso always mounts the boot medium there). On an installed system the directory doesn't exist → the password step is a no-op, preserving install-side behaviour.
- The password step uses `bash -c "echo 'liveuser:erik' | chpasswd"` wrapped in `execute_or_dryrun` so `--dry-run` reports the action without making the change.
- Purpose / Why header updated to document both additions.
- `bash -n` clean.

**Files Modified**
- `usr/local/bin/kiro-enable-ssh`

---

### Garuda imports — 5 small tuning adoptions (kernel-agnostic)

**What Changed**
- After comparing edu-system-files against Garuda Mokka's tuning footprint (live ISO over SSH, 2026-05-28), 5 small additions adopted. Everything Garuda ships system-tweaks-wise comes from one tiny package (`garuda-common-settings`); most was already in our set or weaker than ours, but five items were clean wins. Full analysis written to `kiro-iso/docs/garuda-comparison-2026-05-28.md`.
- **New project rule:** every Kiro system tuning addition MUST be kernel-agnostic — works on linux-cachyos (default), linux-zen (fallback), or anything the user pacman-installs later. All 5 adoptions verified against this rule.

**Technical Details**
1. **systemd-oomd** enabled + tuned. Three drop-ins (oomd global + system slice + user slice) plus a `services-systemd.conf` enable line in **both** kiro-calamares-config and kiro-calamares-config-next so the daemon actually runs on installed systems. Policy: `ManagedOOMMemoryPressure=kill` at `80%` pressure for `20s`. Kicks in BEFORE the kernel OOM killer (which only fires when memory is already exhausted), so the desktop stays responsive on 4-8 GiB systems. Not mandatory in services-systemd — kernel OOM is the fallback.
2. **Intel ME blacklist** (`mei`, `mei_me`). Closes a userspace attack surface that has hosted multiple RCE CVEs (e.g. SA-00086). Does not disable ME itself (only BIOS or `me_cleaner` can), only removes the kernel-side hook. AMD machines load nothing here anyway.
3. **`options btusb reset=1`**. Fixes the common "BT works on cold boot, dead after suspend/resume" issue on Intel AX2xx and Realtek RTL8822 combo cards.
4. **Disable kernel zswap** via tmpfile. With zram-generator providing swap, leaving zswap on means double-compression (zswap on cache, then zstd again as it hits zram). Wasted CPU.
5. **NetworkManager `unmanaged-lo`**. Silences the boot-time warning where NM complains about the loopback interface it shouldn't be managing.
- New `check_garuda_imports()` function in `kiro-audit` verifying each file's presence/content + that `systemd-oomd` is enabled, active, mei modules aren't loaded, and zswap reads `0` at runtime. Wired into `main()` between `check_modprobe_thp` and `check_permissions`.
- `--fix` mode added on the systemd-oomd-not-enabled FAIL.
- All file headers cross-reference the analysis doc in kiro-iso so the rationale chain is one click away.
- Companion edit in `CLAUDE.md` records the kernel-agnostic rule under script conventions.
- `bash -n` clean.

**Plus:** removed the `multilib missing from pacman.conf` WARN from `check_pacman_repos`. Multilib is intentionally not shipped (32-bit Wine/Steam libs — not Kiro's target audience); users who want it enable it in one click via ATT. The audit row was noise — silence is the correct signal for a deliberate design choice. Replaced with an inline comment explaining the omission. `syscheck.md` updated to retire the "expected WARN" carve-out.

**Files Modified**
- `etc/systemd/oomd.conf.d/10-kiro-oomd.conf` (new)
- `etc/systemd/system/system.slice.d/10-kiro-oomd-per-slice.conf` (new)
- `etc/systemd/user/slice.d/10-kiro-oomd-per-slice.conf` (new)
- `etc/modprobe.d/blacklist-intel-me.conf` (new)
- `etc/modprobe.d/bluetooth-usb.conf` (new)
- `etc/tmpfiles.d/disable-zswap.conf` (new)
- `etc/NetworkManager/conf.d/unmanaged-lo.conf` (new)
- `usr/local/bin/kiro-audit` (added `check_garuda_imports`)
- `CLAUDE.md` (new "Kernel-agnostic rule" subsection)

Companion changes outside this repo:
- `kiro-calamares-config/etc/calamares/modules/services-systemd.conf` (enable systemd-oomd, non-mandatory)
- `kiro-calamares-config-next/etc/calamares/modules/services-systemd.conf` (same)
- `kiro-iso/docs/garuda-comparison-2026-05-28.md` (new — full analysis)

## 2026.05.26

**What Changed**
- `kiro-audit` now checks that `logrotate.timer` is enabled. Kiro enables it on the installed system via the Calamares `services-systemd` module so file-based logs (`pacman.log`, Xorg/app logs) rotate; journald rotates its own store separately. The audit `WARN`s (not `FAIL`s) when the timer is disabled and offers a `--fix` that runs `systemctl enable logrotate.timer`. `man-db.timer` was reviewed at the same time and intentionally left unchecked — it is not enabled on Kiro (marginal benefit vs periodic wakeup churn).

**Technical Details**
- New block in `check_services()` beside the firewalld check, using the established `pass`/`warn` + `apply_fix` pattern. `is-enabled` is authoritative: a fresh install can read active-but-disabled, which won't persist across reboot. Mirrors the matching checks added the same day to `/syscheck` (item 15) and the ATT Dev page's "System integrity (kiro-audit mirror)" group.

**Files Modified**
- `usr/local/bin/kiro-audit`

## 2026.05.25

**What Changed**
- `kiro-audit` bootloader detection made robust. The UEFI branch now identifies systemd-boot via `bootctl is-installed` (authoritative ESP state) instead of grepping `efibootmgr` for the literal label `Linux Boot Manager`, and the GRUB checks (UEFI and BIOS) now also accept the `grub` package being installed, not just a `/boot/grub` directory. Previously a systemd-boot machine could report `WARN UEFI system but bootloader type unclear` when efibootmgr was unavailable or the firmware entry was relabeled — surfaced on a systemd-boot install during a system audit.

- Removed the dead HDD `fifo_batch` tuning rule from `60-ioschedulers-tuning.rules`. It set `ATTR{queue/iosched/fifo_batch}="32"` on rotating `sd*` disks, but `60-io-scheduler.rules` puts those same disks on BFQ, and BFQ exposes no `fifo_batch` (it is an mq-deadline tunable) — so the write always silently no-oped. This was the `[FAIL]` newly surfaced by the 2026.05.24 kiro-lint block-device ATTR-target fix. Confirmed on the Kiro VB VM: `sda` is `rotational=1` on `[bfq]`, and its `queue/iosched/` dir contains `slice_idle`/`low_latency`/… but no `fifo_batch`.

- Corrected the SSD comment in the same file. It claimed "queue/iosched/ does not exist under mq-deadline so slice_idle_us is unavailable" — both wrong: mq-deadline *does* expose `queue/iosched/` (with `fifo_batch`, `read_expire`, etc.), and `slice_idle_us` is a BFQ tunable, not mq-deadline's. The conclusion (no SSD tuning) was always fine; the reasoning was false. Rewritten to state SSDs run mq-deadline, whose defaults already suit them.

- `kiro-enable-ssh` now opens SSH in the firewall as well as enabling the service. After enabling `sshd` it allows the `ssh` service in firewalld (`firewall-cmd --permanent --add-service=ssh`, then `--reload` if the daemon is running). Previously the script only installed/enabled sshd and silently relied on firewalld's default `public` zone keeping `ssh` open — so on any hardened or non-default zone the "one-command opt-in" would report success yet leave the user unreachable. Discovered while connecting to picard, whose firewalld is active: SSH worked (default zone permits it) but ICMP and mDNS were dropped, so `picard.local` would not resolve and only the LAN IP worked.

**Technical Details**
- The HDD rule's own comment was self-contradictory ("sets HDDs to BFQ, so fifo_batch is available" — BFQ is precisely why it is *not* available). Replaced the rule + comment with a comment documenting why no iosched tuning happens here (HDDs run BFQ, whose defaults already suit mechanical disks). The NVMe `io_poll_delay` rule in the same file is unaffected and still verifies PASS.
- *(kiro-enable-ssh)* The firewall step is guarded by `command -v firewall-cmd` so it is skipped silently when firewalld is not installed, and the `--reload` only runs when `systemctl is-active --quiet firewalld` succeeds (so `--permanent` still writes the config offline if firewalld is stopped). The `--add-service` is idempotent — firewalld returns `ALREADY_ENABLED` (exit 0) when the rule is already present, so it is safe under the script's `set -Euo pipefail` + ERR trap. Header `Purpose`/`Why`, the `--help` description, and the man page (NAME, DESCRIPTION, a new step 3, and a `firewall-cmd(1)` SEE ALSO) were updated to match.

**Files Modified**
- `etc/udev/rules.d/60-ioschedulers-tuning.rules`
- `usr/local/bin/kiro-enable-ssh`
- `usr/share/man/man8/kiro-enable-ssh.8`

## 2026.05.24

**What Changed**
- Stopped `62-network-optimization.rules` from emitting two boot-time `ethtool` errors on machines with a consumer Intel NIC (I217/I218/I219, e1000e driver). The rule applied server-NIC tuning knobs to all e1000e devices, which they reject.
- Fixed a false-positive `[FAIL]` in `kiro-verify`: its config-presence list still expected `10-kiro-session.conf` at the old `multi-user.target.wants/systemd-logind.service.d/` path. The drop-in was moved to the canonical `systemd-logind.service.d/` path on 2026.05.22, but the verifier's expected-path list was never updated to match.
- Added graphical privilege escalation: a new `ensure_root()` helper in `roman-os-common.sh`, wired into the 5 root-requiring scripts (`kiro-diag`, `kiro-audit`, `kiro-verify`, `kiro-enable-ssh`, `kiro-pci-latency`). Forgetting `sudo` now pops up a polkit password dialog in a graphical session (or falls back to a terminal `sudo` prompt over SSH/tty) instead of erroring out.
- Fixed `kiro-diag` hanging indefinitely at the Bluetooth section when the bluetooth service is inactive.
- Expanded `kiro-audit` to match current config drift: the udev check now validates all 10 shipped rule files (was 2), plus new checks for systemd drop-ins, Intel/Realtek ethernet modprobe configs, and the THP tmpfiles drop-in; help/header text updated for auto-elevation.
- Fixed the ripple from the `pci-latency`→`kiro-pci-latency`, `skel`→`kiro-skel`, `get-nemesis`→`kiro-get-nemesis` script renames: renamed the systemd unit to `kiro-pci-latency.service` (ExecStart, enable symlink, and `kiro-verify`/man-page references all updated), renamed the 3 orphaned man pages, and corrected the README tool table.
- In-depth review of `kiro-verify`: fixed an IO-scheduler false-`FAIL` (it expected `mmcblk` → `bfq`, but `60-io-scheduler.rules` sets non-rotational `mmcblk` → `mq-deadline`), and added the missing `khugepaged/scan_sleep_millisecs=10` THP check. Its 38-entry config-presence list was verified complete and accurate against the shipped tree (no changes).
- In-depth review of `kiro-lint`, two fixes to the udev ATTR-target check: (1) block-device ATTR writes (IO schedulers, read-ahead, fifo_batch — the most common kind) were **never verified**, always `[SKIP]`, because the device-type classifier glob-matched the `KERNEL==` value against case patterns but the value literally contains glob metacharacters (`sd[a-z]*`) and never matched its own pattern — replaced with substring family detection; (2) rules that match by `SUBSYSTEM==` rather than `KERNEL==` (the `power/control` writes in 61-audio-power and 64-gpu) were also skipped — added a subsystem resolver that searches `/sys/bus/<sub>/devices` and `/sys/class/<sub>`. Together these took the verified-write count on a SATA box from 5 → 19 (remaining SKIPs are genuine: no nvme/vd/wifi/backlight present, unloaded modules).
- Reviewed `kiro-probe` (a thin `hw-probe` upload wrapper — correctly uses per-command `sudo`, no changes beyond the below) and from it caught a systemic bug: `log_error` is the `roman-os-common.sh` ERR-trap handler (`log_error <lineno> <cmd>`), but 13 scripts called it with a plain message string, rendering a misleading "⚠️ ERROR DETECTED / Line: <message> / Waiting 10 seconds…" banner (no actual wait) on their error paths. Converted all 15 sites — 12 identical `Unknown option: $arg` arg-parse errors plus 3 bespoke messages (rate-mirrors missing, no-internet, setpci-not-found) — to the `echo "${RED}…${RESET}" >&2` convention already used by kiro-diag/kiro-lint. `kiro-audit` is excluded: it's standalone and its own `log_error` is a message function, so its call is correct.
- Eliminated the *remaining* boot-time `ethtool` error on the `62-network-optimization.rules` e1000e path. Even after the knob-split above (correct single `rx-usecs 0`), the command still failed exit 1 every boot on picard — a separate cause: a udev net-rename race, not an unsupported knob. Fixed by matching the rename `move` event and guarding the call so it can no longer log a failure. Found during a syscheck on picard (booted on the prior package; the split fix removed the EINVAL knobs but not this race).

**Technical Details**
- *(ethtool)* The rule lumped `e1000e` together with the server NICs (`igb|ixgbe|i40e`) and assumed shared capabilities. On the I219-V two RUN commands failed every boot: `ethtool -C $name rx-usecs 0 rx-frames 0 tx-usecs 0 tx-frames 0` (exit 1 — consumer e1000e only supports `rx-usecs`, the per-frame/tx knobs return EINVAL) and `ethtool -K $name gso on` (exit 92 — GSO is already on by default and fixed, so setting it returns EOPNOTSUPP).
- *(ethtool)* Split `e1000e` onto its own coalescing line using only the supported `rx-usecs 0`; left the full four-knob line for `igb|ixgbe|i40e`. Dropped `e1000e` from the GSO line entirely. Networking was never affected — this was cosmetic boot-log noise.
- *(kiro-verify)* The expected path was a leftover from the pre-2026.05.22 layout and even contained an impossible drop-in location (`*.target.wants/` holds symlinks, not service override dirs). The file ships and applies correctly on picard (`systemctl show systemd-logind` confirms `TimeoutStopUSec=10s`, `Restart=on-failure`), so this was purely a stale check, not a missing config. Corrected the list entry to `/etc/systemd/system/systemd-logind.service.d/10-kiro-session.conf`.
- Both found via `dmesg`/`journalctl` and `kiro-verify` on picard (bare-metal Kiro v26.05.24), traced to the package with `pacman -Qo`. Shared package, so the fixes improve both the production and `-next` ISOs.
- *(ensure_root)* Re-execs via `exec pkexec env TERM="$TERM" "$self" "$@"` when a display is present and `pkexec` exists, else `exec sudo`. `TERM` is passed through `env` because `pkexec` scrubs the environment, which would otherwise strip colored output. Uses `${BASH_SOURCE[-1]}` so the original script path resolves whether invoked by full path, bare name via `PATH`, or from inside a function. `kiro-audit` is self-contained (does not source `roman-os-common.sh`), so it carries its own copy of the helper — must be kept in sync. `--help`/`--version` are handled before `ensure_root`, so they never trigger a password prompt.
- *(kiro-diag)* `bluetoothctl show` blocks on D-Bus when `bluetoothd` is down; it is now skipped entirely when the service is inactive and wrapped in `timeout 3` when active.
- *(kiro-pci-latency.service)* Renamed the unit from `pci-latency.service` to `kiro-pci-latency.service` and repointed `ExecStart` to `/usr/local/bin/kiro-pci-latency` (the old path was deleted by the script rename and would fail `203/EXEC` at boot). Recreated the `multi-user.target.wants/` enable symlink with the corrected `../kiro-pci-latency.service` target, and updated the unit-name references in `kiro-verify` (config list + oneshot result check) and the man pages.
- *(man pages)* Renamed with `git mv` (history preserved); content rewritten with `perl` using a guard that preserves the unchanged `/etc/skel` system path. Service-unit path references were updated to `kiro-pci-latency.service` to match the rename.
- *(kiro-verify)* `check_io_schedulers` expected `mmcblk*` → `bfq`, contradicting `60-io-scheduler.rules`, which groups `mmcblk[0-9]*` with non-rotational `sd*` and sets `mq-deadline`; since eMMC/SD are always non-rotational this was a guaranteed false `FAIL` on any machine with an mmcblk device. Also added a `khugepaged/scan_sleep_millisecs == 10` check (warn-level, mirrors `max_ptes_none`) — the 4th value `thp-tuning.conf` writes but the verifier wasn't checking.
- *(kiro-lint)* `_sysfs_attr_exists` chose its sysfs search base with `case "$kernel_pat" in sd[a-z]*) …`, but `$kernel_pat` holds the literal rule string `sd[a-z]*`, which the glob `sd[a-z]*` cannot match (the `[a-z]` class wants a letter, the string has `[`). So `sd*`/`vd*`/`|`-combined KERNELs fell through to `return 2` (SKIP); only `nvme*n*` matched by accident. Replaced the case with `[[ "$kernel_pat" == *sd* … ]]` substring tests, and dropped a dead `pfx_filter` local. Separately, `check_udev_attr_targets` now also extracts `SUBSYSTEM==` and falls back to a new `_sysfs_subsystem_attr_exists` resolver (searches `/sys/bus/<sub>/devices` then `/sys/class/<sub>`) when a rule has no `KERNEL==`, so the `power/control` / `autosuspend_delay_ms` writes in 61-audio-power and 64-gpu are verified instead of skipped. `KERNEL==` still takes precedence when both are present.
- *(ethtool rename race)* The rule fired on `ACTION=="add"` while the NIC still carried its transient kernel name `eth0`; systemd then renamed it to `enp0s31f6` (a `move` uevent) before udev's queued `ethtool -C eth0 …` exec'd, so the command hit a now-nonexistent `eth0` and exited 1. Confirmed harmless on picard: `ethtool -C enp0s31f6 rx-usecs 0` returns exit 0 and `rx-usecs` is already 0 — pure boot-log noise, networking never affected. Fix: match `ACTION=="add|move"` so the knob is (re)applied against the final renamed name, and wrap each `RUN` in `/bin/sh -c '… || true'` so the racing add-time attempt against the stale name never trips udev's "Process failed" warning. Applied to all three Intel branches (`igb|ixgbe|i40e` coalesce, `e1000e` rx-usecs, `ixgbe|i40e` GSO). The non-Intel branches (r8169 / Broadcom / Mellanox / WiFi) share the same race but no fleet hardware currently exercises them, so they were left unchanged. `udevadm verify` passes on the edited file.

**Files Modified**
- [etc/udev/rules.d/62-network-optimization.rules](etc/udev/rules.d/62-network-optimization.rules)
- [usr/local/bin/kiro-verify](usr/local/bin/kiro-verify)
- [usr/local/lib/roman-os-common.sh](usr/local/lib/roman-os-common.sh)
- [usr/local/bin/kiro-diag](usr/local/bin/kiro-diag), [usr/local/bin/kiro-audit](usr/local/bin/kiro-audit), [usr/local/bin/kiro-enable-ssh](usr/local/bin/kiro-enable-ssh), [usr/local/bin/kiro-pci-latency](usr/local/bin/kiro-pci-latency), [usr/local/bin/kiro-lint](usr/local/bin/kiro-lint)
- `log_error` sweep: [kiro-probe](usr/local/bin/kiro-probe), [kiro-get-mirrors](usr/local/bin/kiro-get-mirrors), [kiro-fix-mirrors](usr/local/bin/kiro-fix-mirrors), [kiro-which-vga](usr/local/bin/kiro-which-vga), [kiro-fix-pacman-keys](usr/local/bin/kiro-fix-pacman-keys), [kiro-fix-gpg-conf](usr/local/bin/kiro-fix-gpg-conf), [kiro-skel](usr/local/bin/kiro-skel), [kiro-install-tools](usr/local/bin/kiro-install-tools), [kiro-fix-pacman-conf](usr/local/bin/kiro-fix-pacman-conf), [kiro-iso-version](usr/local/bin/kiro-iso-version), [kiro-get-nemesis](usr/local/bin/kiro-get-nemesis), [kiro-set-cores](usr/local/bin/kiro-set-cores) (kiro-enable-ssh, kiro-pci-latency already listed above)
- [etc/systemd/system/kiro-pci-latency.service](etc/systemd/system/kiro-pci-latency.service) (renamed from `pci-latency.service`; `multi-user.target.wants/` enable symlink recreated)
- `usr/share/man/man8/{kiro-pci-latency,kiro-skel,kiro-get-nemesis}.8` (renamed from `pci-latency.8`, `skel.8`, `get-nemesis.8`)
- [README.md](README.md)

## 2026.05.22

**What Changed**
Moved the `systemd-logind.service.d/10-kiro-session.conf` drop-in out of `multi-user.target.wants/` to the canonical `systemd-logind.service.d/` path so its settings are actually applied on Kiro installs.

**Technical Details**
- Drop-in was nested at `etc/systemd/system/multi-user.target.wants/systemd-logind.service.d/10-kiro-session.conf`. systemd parses `*.target.wants/` as a list of symlinks-to-units, not a place for service override directories, so it logged at every boot and every `daemon-reload`: `multi-user.target: Wants dependency dropin .../systemd-logind.service.d is not a symlink, ignoring`. The drop-in (`TimeoutStopSec=10s`, `Restart=on-failure`, `RestartSec=5s`, `KillMode=mixed`, `KillSignal=SIGTERM`) was being silently discarded on every install that shipped this package.
- Fix is a pure `git mv` to `etc/systemd/system/systemd-logind.service.d/10-kiro-session.conf` — no content change. Sibling `pci-latency.service` symlink in `multi-user.target.wants/` was already correct and was left in place.
- Found by `journalctl -p err -b` on picard (bare-metal Kiro v26.05.19), then traced to the package via `pacman -Qo`.

**Files Modified**
- `etc/systemd/system/systemd-logind.service.d/10-kiro-session.conf` (moved from `multi-user.target.wants/`)

## 2026.05.21

**What Changed**
Aligned `etc/samba/smb.conf.nemesis` with the personal `arcolinux-nemesis` template. Casing for the Samba share path normalised on the lowercase `Shared` form (was `SHARED`).

**Technical Details**
- `[SAMBASHARE] path = /home/erik/SHARED` → `/home/erik/Shared`; comment header updated to match.
- Decision came out of the HQ cross-stack audit between `arcolinux-nemesis` (personal install scripts) and `edu-system-files` (Kiro block). The two repos shipped functionally identical templates that differed only on casing; `Shared` wins as the canonical form because `arcolinux-nemesis` actively writes `/etc/samba/smb.conf` from its own template on Erik's machines, so aligning here prevents churn.
- The other two collisions found in the audit (zram-generator.conf, 90-memory-accounting.conf) were resolved on the nemesis side by deleting the offending nemesis scripts — `edu-system-files` keeps ownership of those system files unchanged.

**Files Modified**
- [etc/samba/smb.conf.nemesis](etc/samba/smb.conf.nemesis)

## 2026.05.20

**What Changed**
Added the mandatory `Purpose:` / `Why:` header block to 18 scripts in `usr/local/bin/` to bring them in line with the canonical bash template in `~/.claude/CLAUDE.md`.

**Technical Details**
- Inserted a `# Purpose:` prose block (what the script does) followed by a `# Why:` line (motivation) into each script's existing `#####` banner header, between the `DO NOT JUST RUN THIS` warning and the closing banner line.
- No functional code changes — headers only. Existing `set -Euo pipefail`, `SCRIPT_DIR`, sourcing of `roman-os-common.sh`, and arg parsing all left untouched.
- `kiro-audit` header refreshed: dropped the old short "verify the install is correct" line and replaced with the full Purpose/Why pair that lists what the audit actually checks (kernel, microcode, mkinitcpio, audio, Calamares cleanup, kiro_final, repos, DEs, SDDM, groups, services, permissions, bootloader, packages).
- Brings these scripts into compliance so anyone opening the file can tell what it does without reading the body — matches the standard set by Kiro-HQ's `up.sh` / `setup.sh` / `cleanup.sh`.

**Files Modified**
- `usr/local/bin/get-nemesis`
- `usr/local/bin/kiro-audit`
- `usr/local/bin/kiro-diag`
- `usr/local/bin/kiro-enable-ssh`
- `usr/local/bin/kiro-fix-gpg-conf`
- `usr/local/bin/kiro-fix-mirrors`
- `usr/local/bin/kiro-fix-pacman-conf`
- `usr/local/bin/kiro-fix-pacman-keys`
- `usr/local/bin/kiro-get-mirrors`
- `usr/local/bin/kiro-install-tools`
- `usr/local/bin/kiro-iso-version`
- `usr/local/bin/kiro-lint`
- `usr/local/bin/kiro-probe`
- `usr/local/bin/kiro-set-cores`
- `usr/local/bin/kiro-verify`
- `usr/local/bin/kiro-which-vga`
- `usr/local/bin/pci-latency`
- `usr/local/bin/skel`

---

## 2026.05.19 (session 5)

**What Changed**
Major expansion of `kiro-diag` with new sections; fixes to `kiro-lint` and `kiro-verify`; stale CUPS check removed from `kiro-audit`.

**Technical Details**
- `kiro-diag` fully rewritten: replaced raw `tput` calls with library color vars, added `_field()` helper, structured into named section functions. New sections: Hardware (CPU, RAM, lsblk), GPU (Intel + AMD + NVIDIA with drivers), Storage (df -h, swap), Network (ip -br), Audio (PipeWire/WirePlumber/PulseAudio via pgrep), Bluetooth (bluez state + adapter), Desktop (DM, WM via pgrep, sessions), Kernel (governor, cmdline), Bootloader (efibootmgr-based detection for systemd-boot/GRUB/rEFInd/Limine), Packages (count, paru/yay status), Temperatures (sensors). System section gained uptime, virtualization, timezone, locale, Kiro package version.
- `kiro-diag` fixes: `log_error` → `echo+RED` for unknown option; NVIDIA driver check now parses `lspci -nnk` directly; nvidia-drm.modeset checks `/proc/cmdline` first then systemd-boot then grub; package version queries installed path not `$BASH_SOURCE`; ISO fields split into release/codename/build; `ohmychadwm` added to WM detection list; Intel GPU detection added.
- `kiro-lint`: fixed `log_error` misuse (ERR trap handler called with plain string); added `w*` to `_sysfs_attr_exists` network branch so `KERNEL=="w*"` udev rules are verified instead of silently skipped.
- `kiro-verify`: corrected IO scheduler expectation for `sd*` SSDs (mq-deadline, not bfq — matches the udev rule); added 3 missing deployed config files to presence check (`dmesg-nopasswd`, `10-kiro-mdns.conf`, `10-kiro-session.conf`).
- `kiro-audit`: removed stale `cups-permissions.conf` tmpfiles.d presence check; simplified CUPS fix branches to always use `chmod 600` directly.

**Files Modified**
- `usr/local/bin/kiro-diag`
- `usr/local/bin/kiro-lint`
- `usr/local/bin/kiro-verify`
- `usr/local/bin/kiro-audit`

---

## 2026.05.19 (session 4)

**What Changed**
Removed the stale `cups-permissions.conf` tmpfiles.d check from `kiro-audit` — the file is no longer deployed on the system.

**Technical Details**
- Dropped the `[[ -f /etc/tmpfiles.d/cups-permissions.conf ]]` presence check that would FAIL if the file was absent.
- Simplified `classes.conf` and `printers.conf` fix branches: removed the conditional that called `systemd-tmpfiles --create`; both now always use `chmod 600` directly.

**Files Modified**
- `usr/local/bin/kiro-audit`

---

## 2026.05.19 (session 3)

**What Changed**
Added `--fix` mode to `kiro-audit` that auto-remediates known fixable failures. Fixed `--version` to read the version from the owning pacman package at runtime instead of a hardcoded string.

**Technical Details**
- `apply_fix "description" cmd [args...]` helper: in `--fix` mode prints the description and runs the command, incrementing `FIXED` on success; in read-only mode prints a `FIX?` hint showing what would run. No `eval` — command and args passed directly via `"$@"`.
- 8 fixable checks wired: 6 archiso leftover file/dir deletions (`10-archiso.conf`, `.automated_script.sh`, `.zlogin`, `getty@tty1` drop-in, `g_wheel`, `49-nopasswd_global.rules`), `systemctl mask pacman-init`, and `systemd-tmpfiles --create` for CUPS permissions (falls back to `chmod 600` if the `tmpfiles.d` conf is absent).
- Summary shows `FIXED: N` when `--fix` is used; final message says "re-run to confirm" rather than hard-failing when fixes were applied — FAIL counter still reflects issues found pre-fix.
- `--version` now runs `pacman -Qqo "$(realpath "${BASH_SOURCE[0]}")"` to get the owning package name, then `pacman -Q "$pkg"` to print `<pkg> <version>`. Falls back gracefully when not installed via pacman.

**Files Modified**
- `usr/local/bin/kiro-audit`

---

## 2026.05.19 (session 2)

**What Changed**
Added `kiro-enable-ssh` — a one-step script that installs `openssh` and immediately enables/starts `sshd`. Fixed incorrect use of `log_error` for a user-facing root-check message.

**Technical Details**
- Script follows the Phase 2 pattern: sources `roman-os-common.sh`, supports `--help`/`--version`/`--dry-run`, requires root via `[[ $EUID -ne 0 ]]` guard
- `log_error` in `roman-os-common.sh` is the ERR trap handler — it takes `lineno`/`cmd` params, not a message string. Calling it with a plain string produces the full `⚠️ ERROR DETECTED` banner with the message treated as a line number. Root-check failures (and any user-facing error before the trap can fire) must use `echo "${RED}...${RESET}" >&2` instead
- Man pages belong in `usr/share/man/man8/` (maps to `/usr/share/man/man8/` on deploy) — the path is correct. `mandb` runs on a daily systemd timer (`man-db.timer`) with up to 12h random delay, not at boot. Run `sudo mandb` manually after deploying new pages to get immediate tab completion

**Files Modified**
- `usr/local/bin/kiro-enable-ssh` (new)
- `usr/share/man/man8/kiro-enable-ssh.8` (new)

---

## 2026.05.19

**What Changed**
Added `kiro-lint` — a static config analyser that checks the `etc/` tree before deployment.

**Technical Details**
Four checks implemented:
- **Sysctl duplicate keys**: parses each `sysctl.d/*.conf`, joins backslash-continuation lines, flags any key that appears more than once in the same file (last write wins, earlier value is silently lost)
- **Modprobe params vs sysfs**: for each `options <driver> param=val` in `modprobe.d/`, verifies the param is exposed under `/sys/module/<driver>/parameters/`; skips gracefully when the module isn't loaded; detected `snd_hda_intel.stateful_codec` as absent from lqx 7.0.9 kernel
- **Cross-file conflicts**: builds a map of all modprobe param values, detects same driver/param set to different values across files, then checks udev `ATTR{}` write targets for param names that match — flags anything where udev would silently override the modprobe value at runtime
- **Udev ATTR write targets**: extracts `ATTR{path}="value"` write assignments (distinguished from `==` match conditions via PCRE negative lookbehind), resolves the KERNEL= pattern to a sysfs search base, and verifies the attribute path exists on a live device; SKIPs cleanly when no matching hardware is present
- Script accepts `--source <path>` to analyse a repo tree before deployment (default: `/` for installed files); no root required

**Files Modified**
- `usr/local/bin/kiro-lint` (new)
- `TODO.md`
- `CHANGELOG.md`

---

## 2026.05.18 (session 3)

**What Changed**
Complete audit and fix of all `etc/` configuration files — sysctl, udev rules, systemd drop-ins, modprobe options. 23 issues resolved across Critical / High / Medium / Low / Documentation categories. Every config file the package ships is now safe to deploy on a general desktop or laptop without hardware-specific breakage.

**Technical Details**
- **Critical**: `probe_mask=1` removed from `audio-hda.conf` (was blocking HDMI audio by limiting HDA bus scan to first codec); `jackpoll_ms=0` → `500` (0 disabled headphone jack detection); `61-audio-power.rules` was a verbatim copy of `60-io-scheduler.rules` — replaced with correct USB/PCIe audio power management; `DPRINTK=1` removed from `intel-ethernet.conf` (was flooding journal on any Intel e1000e NIC)
- **High**: `kernel.sysrq=0` → `244` (REISUB bitmask: R+E+I+S+U+B); `ptrace_scope=2` → `1` (2 breaks gdb/strace/IDE debuggers); `DefaultTimeoutStartSec=10s` → `30s` (10s killed databases and Samba on first start); watchdog block commented out (iTCO_wdt and sp5100_tco are blacklisted so `/dev/watchdog` never exists); journal `Storage=volatile` → `persistent` (volatile lost all logs on reboot); journald file had three concatenated blocks with conflicting duplicate keys — rate limiting ended up clobbered to 0/0 (disabled entirely); NVIDIA `power/control=auto` udev rule removed (causes GPU hangs on GTX 900/1000 series)
- **Medium**: `vm.dirty_ratio`/`vm.dirty_background_ratio` removed (silently ignored when `dirty_bytes` is set); duplicate sysctl keys deduplicated (kptr_restrict×2, netdev_max_backlog×2, tcp_fastopen×2, entire BBR/fq block×2); NVMe `set-feature -f 2` rule removed (feature ID 2 is Write Atomicity Normal, not APST); `hdparm -M 128` removed (was mislabelled as TRIM — actually Acoustic Management, mostly ignored by modern drives); `68-sound-power.rules` had `power_save=10` conflicting with `modprobe.d` `power_save=0`; `realtek-ethernet.conf` invalid r8169 parameters stripped and `use_dac=1` reverted to safe default; `amdgpu.conf` instability warning added for early Vega/Navi
- **Low**: `kernel.unprivileged_userns_clone` removed (hardened-kernel-only sysctl, causes errors on vanilla Arch); `66-input-optimization.rules` rewritten — all four previous rules were no-ops (non-existent procfs path, fake libinput env vars, wrong usbhid jitter direction); `DefaultTasksMax=infinity` → `65536`; user subsequently refined the USB HID autosuspend rules to correctly match on `usb_interface` and write to the parent device node via `dirname %p`
- **Documentation**: `overcommit_ratio=50` comment updated to note it is ignored when `overcommit_memory=1`; `sched_autogroup_enabled=0` trade-off documented (correct for single-user audio desktop, reduces fairness on multi-user systems); `nvidia.conf` `NVreg_InitializeSystemMemoryAllocations=0` single-user caveat added

**Files Modified**
- `etc/modprobe.d/audio-hda.conf`
- `etc/modprobe.d/amdgpu.conf`
- `etc/modprobe.d/intel-ethernet.conf`
- `etc/modprobe.d/nvidia.conf`
- `etc/modprobe.d/realtek-ethernet.conf`
- `etc/sysctl.d/99-kiro-optimizations.conf`
- `etc/systemd/journald.conf.d/10-kiro-journal.conf`
- `etc/systemd/system.conf.d/10-kiro-system.conf`
- `etc/udev/rules.d/61-audio-power.rules`
- `etc/udev/rules.d/64-gpu-optimization.rules`
- `etc/udev/rules.d/65-storage-optimization.rules`
- `etc/udev/rules.d/66-input-optimization.rules`
- `etc/udev/rules.d/68-sound-power.rules`

---

## 2026.05.18 (session 2)

**What Changed**
All 33 scripts in `usr/local/bin/` that were not sourcing the shared library have been updated. Every script in the project now sources `/usr/local/lib/roman-os-common.sh` for uniform logging, colors, and error handling.

**Technical Details**
Scripts were processed in four tiers:
- **Tier 1** (16 scripts): Standard transform — `#set -e` replaced with `set -Euo pipefail`, source block added, echo banners replaced with `log_section`/`log_info`/`log_success`/`log_warn`/`log_error`
- **Tier 2** (9 scripts): Same as Tier 1 plus removal of inline tput color variable blocks and inline `tput setaf`/`tput sgr0` calls, replaced by library log functions
- **Tier 3** (7 scripts): Careful handling — duplicate local `check_connectivity()` in `var` removed in favour of the library's version; ANSI display code in `sysinfo`, `sysinfo-retro`, `fetch`, `hfetch`, `sfetch` preserved untouched (display formatting, not logging); custom domain functions in `fix-sddm-conf` and `get-chadwm`/`get-sddm-simplicity` kept and cleaned of tput calls
- **Tier 4** (1 script): `pci-latency` — shebang changed from `#!/usr/bin/env sh` to `#!/bin/bash`; `set +e` preserved intentionally (script must continue on setpci failures); `set -Euo pipefail` deliberately omitted
- `get-arcolinux-nemesis` turned out to be a symlink to `get-nemesis` — one edit covered both
- Deprecated `$[count+1]` arithmetic replaced with `$((count+1))` in `get-chadwm` and `get-sddm-simplicity`
- `remove-socials` rm calls changed to `rm -f` to be safe under `set -Euo pipefail`
- All 44 scripts syntax-checked with `bash -n` — zero errors

**Files Modified**
- `usr/local/bin/iso`
- `usr/local/bin/edu-get-mirrors`
- `usr/local/bin/edu-probe`
- `usr/local/bin/edu-set-cores`
- `usr/local/bin/edu-which-vga`
- `usr/local/bin/edu-fix-archlinux-servers`
- `usr/local/bin/edu-fix-pacman-gpg-conf`
- `usr/local/bin/get-linux-mainline-x64v3-from-chaotic-repo`
- `usr/local/bin/get-linux-nitrous-from-chaotic-repo`
- `usr/local/bin/get-linux-xanmod-edge-x64v3-from-chaotic-repo`
- `usr/local/bin/get-linux-xanmod-lts-from-chaotic-repo`
- `usr/local/bin/remove-chaotic-repo-from-pacman.conf`
- `usr/local/bin/remove-nemesis-repo-from-pacman.conf`
- `usr/local/bin/toggle-chaotic-repo`
- `usr/local/bin/skel`
- `usr/local/bin/velo`
- `usr/local/bin/get-nemesis` (also covers `get-arcolinux-nemesis` symlink)
- `usr/local/bin/get-flexi`
- `usr/local/bin/use`
- `usr/local/bin/remove-debug`
- `usr/local/bin/remove-socials`
- `usr/local/bin/add-virtualbox-guest-utils`
- `usr/local/bin/get-chadwm`
- `usr/local/bin/get-sddm-simplicity`
- `usr/local/bin/var`
- `usr/local/bin/fix-sddm-conf`
- `usr/local/bin/sysinfo`
- `usr/local/bin/sysinfo-retro`
- `usr/local/bin/fetch`
- `usr/local/bin/hfetch`
- `usr/local/bin/sfetch`
- `usr/local/bin/pci-latency`
- `CHANGELOG.md`
- `TODO.md` (new stub)
- `IDEAS.md` (new stub)

---

## 2026.05.18

**What Changed**
Added `kiro-verify` — a post-install verification script that checks all configuration settings shipped by this package are actually applied at runtime and scans logs for errors.

**Technical Details**
The script parses `/etc/sysctl.d/99-kiro-optimizations.conf` dynamically (no hardcoded key list) to compare expected vs live values via `sysctl -n`. Additional checks cover: all 34 config files are installed, ZRAM is active with zstd compression, IO schedulers match device type (NVMe→none, SSD→bfq, HDD→mq-deadline), THP settings in `/sys/kernel/mm/`, blacklisted modules not loaded, no failed systemd units, and a journal/udev/dmesg error scan. Outputs PASS/FAIL/WARN/SKIP per check with a final summary, exits 1 on any FAIL. sysctl params missing from the running kernel produce WARN rather than FAIL.

**Files Modified**
- `usr/local/bin/kiro-verify` (new)
- `CHANGELOG.md`

---

## 2026.05.01

**What Changed**
Added CLAUDE.md with architecture overview for Claude Code sessions.

**Technical Details**
Documents the shared library pattern, script conventions, config file map, and current improvement phase status so future sessions don't need to rediscover structure.

**Files Modified**
- `CLAUDE.md` (new)

---

## 2026.04.20

**What Changed**
Phase 1 code quality overhaul: created unified shared library, enabled strict error handling, fixed variable quoting across critical scripts, and standardized logging.

**Technical Details**
- Created `usr/local/lib/roman-os-common.sh` (1000+ lines, 80+ functions) consolidating `arcolinux-nemesis/common/common.sh` and EDU-specific utilities into 14 sections
- Removed empty `edu-common.sh` wrapper; all scripts now source `roman-os-common.sh` directly
- Enabled `set -Euo pipefail` in all main scripts (previously commented out or absent)
- Fixed 20+ unquoted variable expansions in critical scripts (`edu-fix-pacman-conf`, `get-linux-kiro`, `setup-edu.sh`, `edu-fix-pacman-databases-and-keys`)
- Replaced bare `echo` calls with `log_*` functions throughout
- Added `confirm_destructive_operation()` guards to destructive pacman/key operations
- Added trap-based tmpfile cleanup in repo management scripts
- Replaced hardcoded connectivity checks with `check_connectivity()` library call

**Files Modified**
- `usr/local/lib/roman-os-common.sh` (new)
- `usr/local/bin/edu-fix-pacman-conf`
- `usr/local/bin/edu-fix-pacman-databases-and-keys`
- `usr/local/bin/get-linux-kiro`
- `usr/local/bin/add-kiro`
- `usr/local/bin/add-chaotic_repo-to-pacman.conf`
- `usr/local/bin/add-nemesis_repo-to-pacman.conf`
- `usr/local/bin/pac`
- `usr/local/bin/get-me-started`
- `setup-edu.sh`
- `up.sh`

---

## 2026.04.19

**What Changed**
Initial repository setup with system configuration files and utility scripts for Kiro/ArcoLinux desktops.

**Technical Details**
Established the `usr/local/bin/` + `usr/local/lib/` + `etc/` directory tree mirroring the live system layout. Populated with kernel parameter tuning (`sysctl.d`), udev hardware rules, systemd drop-ins, modprobe options, and 40+ utility scripts for pacman, kernel variants, DE fetching, and system info.

**Files Modified**
- Initial commit of all files
