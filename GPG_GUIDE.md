# Guía para Habilitar Firmas GPG en Roman OS Packages

Esta guía detalla el proceso paso a paso para habilitar firmas GPG en el repositorio `roman-os-packages` para máxima seguridad, abandonando el uso de `SigLevel = TrustAll`.

Dado que los paquetes de Roman OS se compilan automáticamente mediante GitHub Actions, la llave privada debe ser configurada de forma segura en GitHub.

## 1. Generar tu Llave GPG (Local)
Primero, necesitas una identidad digital para firmar. En tu terminal local (tu PC personal), ejecuta:
```bash
gpg --full-generate-key
```
* Elige `RSA (sign only)` o `RSA and RSA`.
* Tamaño de la llave: `4096` bits.
* Ponle un nombre descriptivo, ej. `Roman OS Packager <admin@romanos.org>`.
* Te pedirá una contraseña; **anótala bien y guárdala en un gestor de contraseñas**.

## 2. Exportar las llaves
Necesitas exportar tu llave pública (para los usuarios/ISO) y tu llave privada (para GitHub Actions).

**Exportar la privada (¡No la compartas!):**
```bash
gpg --export-secret-keys --armor <TU_EMAIL> > privada.key
```

**Exportar la pública (Distribuible):**
```bash
gpg --export --armor <TU_EMAIL> > roman-os.pub
```

## 3. Configurar GitHub Actions (Secretos)
1. Ve a tu repositorio `roman-os-packages` en GitHub.
2. Navega a **Settings > Secrets and variables > Actions > New repository secret**.
3. Crea un secreto llamado `GPG_PRIVATE_KEY` y pega el contenido completo del archivo `privada.key`.
4. Si le pusiste contraseña a tu llave, crea otro secreto llamado `GPG_PASSPHRASE`.

## 4. Modificar tu `build.yml`
Se deben agregar pasos en el workflow para importar la llave y firmar tanto los paquetes como la base de datos del repositorio.

```yaml
      - name: Import GPG Key
        run: |
          echo "${{ secrets.GPG_PRIVATE_KEY }}" | gpg --import
          # Si usas contraseña, configurar el passphrase aquí o pasarlo por stdin a los comandos gpg

      - name: Build Packages
        run: |
          # ... (código actual de compilación)
          
          # Al finalizar la compilación, firmar los paquetes
          for pkg in ../x86_64/*.pkg.tar.zst; do
            gpg --detach-sign --use-agent "$pkg"
          done

      - name: Generate Repository Database
        run: |
          # Añadir la bandera --sign al repo-add para que firme la base de datos (crea .db.tar.gz.sig)
          repo-add --sign roman-os-packages.db.tar.gz *.pkg.tar.zst
```

## 5. Integrar la Llave Pública en tu ISO (Pacman Keyring)
Para que los sistemas confíen en los paquetes firmados, debes añadir `roman-os.pub` al *keyring* de `pacman`.

**Opción A (Recomendada): Crear un paquete `roman-os-keyring`**
Crea un paquete que instale `roman-os.pub` en `/usr/share/pacman/keyrings/` y ejecute los comandos de `pacman-key` en su script `.install`. Incluye este paquete en tu ISO.

**Opción B: Archivos en la ISO (airootfs)**
Para el Live USB, puedes añadir la llave pública a la estructura de archivos en `archiso/airootfs/` e importarla mediante los scripts de configuración (`roman-os_before`, etc.) ejecutando:
```bash
pacman-key --add roman-os.pub
pacman-key --lsign-key <TU_EMAIL>
```

## 6. Cambiar el SigLevel a Seguro
Una vez que los paquetes se generan con firmas y el sistema cuenta con la llave pública instalada, modifica la configuración de Pacman.

En `/etc/pacman.conf` (y en `archiso/pacman.conf`):

**Cambiar de (Inseguro):**
```ini
[roman-os-packages]
SigLevel = Optional TrustAll
```
**A (Seguro):**
```ini
[roman-os-packages]
SigLevel = Required DatabaseOptional
# o preferiblemente:
# SigLevel = Required TrustedOnly
```
