# Registro de Migración: De Kiro a roman-os

Este documento registra de forma detallada la migración de los paquetes de infraestructura y personalización del proyecto original (**Kiro**) hacia el ecosistema independiente de **roman-os**.

## Estado General de la Migración

- **Total de Paquetes Identificados**: 27
- **Migrados**: 1
- **Pendientes**: 26

---

## Detalle de Paquetes y Estado de Migración

| # | Paquete Original (Kiro) | Paquete Destino (roman-os) | Tipo / Propósito | Estado | Notas / Progreso |
|---|-------------------------|----------------------------|------------------|--------|------------------|
| 1 | `kiro-mirrorlist` | `roman-os-mirrorlist` | Configuración / Lista de espejos del repositorio | **Completado** | Primer paquete creado e integrado en la ISO. |
| 2 | `kiro-keyring` | `roman-os-keyring` | Seguridad / Claves GPG para firmar paquetes | *Pendiente* | Necesario si decidimos firmar los paquetes con GPG. |
| 3 | `kiro-calamares-config`| `roman-os-calamares-config`| Instalador / Diapositivas, branding y configuración de Calamares | **Completado** | Repositorio clonado, limpiado de `.git`, y renombradas referencias de kiro a roman-os. Removido `kiro-calamares-tweak-tool` de la ISO por ser innecesario. |
| 4 | `kiro-grub-theme` | `roman-os-grub-theme` | Arranque / Tema del cargador de arranque GRUB | **Completado** | Creado tema minimalista desde cero (simple y funcional) prescindiendo del tema antiguo. |
| 5 | `kiro-system-files` | `roman-os-system-files` | Configuración / Archivos base de configuración del sistema | **Completado** | Clonado, renombrados los scripts internos (de kiro a roman-os) y limpiado dependencias. |
| 6 | `kiro-shells` | `roman-os-shells` | Configuración / `.bashrc` y configuraciones de terminales | **Completado** | Elimina la dependencia del `wget` externo que rompía la compilación. |
| 7 | `kiro-xfce` | `roman-os-xfce` | Entorno / Configuración por defecto del escritorio XFCE | **Completado** | Extraído del caché y portado. |
| 8 | `kiro-dot-files` | `roman-os-dot-files` | Personalización / Archivos de configuración de usuario (dotfiles) | *Pendiente* | Configura el look & feel por defecto del usuario. |
| 9 | `kiro-assistant` | `roman-os-assistant` | Herramientas / Asistente interactivo del sistema | *Pendiente* | Asistente de IA/sistema. |
| 10 | `kiro-iso-builder` | `roman-os-builder-gui` | Herramientas / Interfaz gráfica del compilador de la ISO | *Pendiente* | La GUI interactiva para compilar la ISO. |
| 11 | `plymouth-theme-kiro-logo`| `plymouth-theme-roman-os` | Visual / Pantalla de carga animada del sistema | *Pendiente* | Logo de carga de roman-os al apagar/encender. |
| 12-27 | Otros paquetes estéticos | `roman-os-*` | Temas de iconos, Kvantum, configuraciones de Rofi, Polybar | *Pendiente* | Paquetes menores que se irán migrando progresivamente. |

---

## Registro de Actividades

### [2026-06-28] - Inicialización de roman-os-packages
* **Creado el repositorio base**: Inicializado el repositorio monorepo de paquetes en `/home/roman/roman-os-packages`.
* **Automatización CI/CD**: Creado el flujo `.github/workflows/build.yml` con empaquetamiento en contenedor de Arch Linux y despliegue automático a GitHub Pages.
* **Paquete 1 (`roman-os-mirrorlist`)**: Migrado, compilado y desplegado exitosamente.
* **Resiliencia en ISO**: Modificado el script de la ISO (`build-the-iso.sh`) para soportar caídas de red y agregar el repositorio `roman-os-packages` automáticamente.
