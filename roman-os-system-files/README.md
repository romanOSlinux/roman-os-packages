<p align="center">
  <img src="kiro.jpg" alt="Kiro" width="220" />
</p>

# kiro-system-files

System-level files for the Kiro distro — kernel parameters, udev rules, systemd drop-ins, sudoers rules, modprobe blacklists, X11 keyboard maps, sysctl tunings, plus the **`kiro-*` toolchain** of diagnostic and maintenance commands. Owned by Kiro; collisions with personal install scripts (e.g. `arcolinux-nemesis`) are resolved in favour of this repo — see [HQ/ECOSYSTEM.md → cascade rules](../../Insync/Kiro/Kiro-HQ/ECOSYSTEM.md).

## What's in this repo

### `etc/` — system configuration drop-ins
- `sysctl.d/` — kernel tuning (network stack, VM, fs)
- `modprobe.d/` — module options + blacklists
- `udev/` — device rules
- `systemd/` — service drop-ins and timers
- `sudoers.d/` — sudo policy (timestamp_timeout, etc.)
- `security/` — limits.d entries
- `tmpfiles.d/` — runtime tmpfs / cleanup rules
- `samba/` — Samba config including `smb.conf.nemesis` (aligned byte-identical with the `arcolinux-nemesis` personal copy — see [HQ/ECOSYSTEM.md cascade rules](../../Insync/Kiro/Kiro-HQ/ECOSYSTEM.md))
- `pacman.d/`, `X11/` — pacman drop-ins, keyboard layout maps

### `usr/local/bin/` — the `kiro-*` toolchain

| Command                | Purpose                                                              |
|------------------------|----------------------------------------------------------------------|
| `kiro-audit`           | Audit a running install against expected Kiro defaults               |
| `kiro-calamares-log`   | Summarise the Calamares installer log (timeline, warnings, verdict)  |
| `kiro-diag`            | Diagnostic dump: ISO version, BIOS/UEFI, mounts, DM, kernels, NVIDIA |
| `kiro-enable-ssh`      | Enable + start `sshd.service`                                        |
| `kiro-fix-gpg-conf`    | Reset `/etc/pacman.d/gnupg/` to a clean state                        |
| `kiro-fix-mirrors`     | Repair `/etc/pacman.d/mirrorlist` from a known-good baseline         |
| `kiro-fix-pacman-conf` | Restore Kiro's `pacman.conf` defaults                                |
| `kiro-fix-pacman-keys` | Re-init + re-populate pacman keyring                                 |
| `kiro-get-mirrors`     | Refresh fast mirror list via reflector                               |
| `kiro-install-tools`   | Install Kiro's recommended additional packages                       |
| `kiro-iso-version`     | Print `/etc/dev-rel` and rolling-release marker                      |
| `kiro-lint`            | Lint Kiro-specific config files for known anti-patterns              |
| `kiro-probe`           | Inspect hardware / firmware / driver state                           |
| `kiro-report`          | Public-safe diagnostic bundle (drivers, packages, logs) for support  |
| `kiro-set-cores`       | Set makepkg.conf MAKEFLAGS to all CPU cores                          |
| `kiro-set-cores-min1`  | Set makepkg.conf MAKEFLAGS to all cores minus one (1 core free)      |
| `kiro-set-cores-min2`  | Set makepkg.conf MAKEFLAGS to all cores minus two (2 cores free)     |
| `kiro-verify`          | Post-install verification — does the install match the ISO manifest? |
| `kiro-which-vga`       | Detect installed VGA card vendor (Intel / AMD / NVIDIA)              |
| `kiro-get-nemesis`     | Helper to fetch the nemesis_repo bootstrap                           |
| `kiro-pci-latency`     | One-shot PCI latency tweak                                           |
| `kiro-skell`           | Fast `/etc/skel/` restore — backs up only the configs it overwrites  |
| `kiro-skell-all`       | Full `/etc/skel/` restore — backs up the whole `~/.config` first     |

### `usr/lib/systemd/`, `usr/share/backgrounds/`
Bundled system-wide systemd units and Kiro wallpapers.

## Installation

### From `nemesis_repo` (recommended)

```ini
[nemesis_repo]
Server = https://erikdubois.github.io/$repo/$arch
```

```bash
sudo pacman -Syu
sudo pacman -S kiro-system-files
```

This installs the configs into `/etc/` and the `kiro-*` toolchain into `/usr/local/bin/`.

> **Signed repo.** `nemesis_repo` packages are PGP-signed by the Kiro key. On Kiro
> the key is already trusted (shipped + locally signed by `kiro-keyring`) and the
> repo inherits the global `SigLevel = Required DatabaseOptional` — no per-repo line
> needed. Adding the repo by hand on a non-Kiro box? Install `kiro-keyring` first, or
> set `SigLevel = Optional` for the repo until it's in place, then verification kicks in.

### Manual

```bash
git clone https://github.com/kirodubes/kiro-system-files.git
cd kiro-system-files
sudo cp -r etc/.   /etc/
sudo cp -r usr/.   /usr/
```

## Related

- [kiro-dot-files](https://github.com/kirodubes/kiro-dot-files) — user-level dotfiles (companion to this system-level repo).
- [HQ/ECOSYSTEM.md → cascade rules](../../Insync/Kiro/Kiro-HQ/ECOSYSTEM.md) — explicit ownership of paths shared with `arcolinux-nemesis`.

## Websites

Information : https://erikdubois.be

## Social Media

Youtube : https://www.youtube.com/erikdubois

<!-- KIRO-FUNDING-FOOTER:START — managed by Kiro-HQ/cascade-readme-footer.sh -->
## Help fund Kiro

Everything I build here stays free and open — always. If Kiro or any of these
tools have ever saved you time or taught you something, a small monthly
contribution helps keep the work going. Donations target break-even, nothing
more — the core always stays free for everyone.

- GitHub Sponsors: https://github.com/sponsors/erikdubois
- Patreon: https://www.patreon.com/c/kiroproject
- YouTube memberships: https://www.youtube.com/@ErikDubois/join
- Ko-fi: https://ko-fi.com/erikdubois
- PayPal: https://www.paypal.me/erikdubois
<!-- KIRO-FUNDING-FOOTER:END -->

## License

See [LICENSE](./LICENSE).
