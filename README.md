# roman-os-packages

Repositorio oficial de paquetes precompilados de Arch Linux para **roman-os**.

## Cómo usar

Añade este repositorio a tu `/etc/pacman.conf`:

```ini
[roman-os-packages]
SigLevel = Optional TrustAll
Server = https://romanOSlinux.github.io/roman-os-packages/$arch
```

## Estructura

- Cada subcarpeta contiene un paquete con su correspondiente `PKGBUILD`.
- El flujo de GitHub Actions compila automáticamente todos los paquetes y publica la base de datos en la rama `gh-pages` al empujar cambios a `main`.
