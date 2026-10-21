# ts-kicad-plugins

KiCAD plugins Tecsmith.

These plugins target KiCad 10.0.x.
The plugins use the legacy `pcbnew` Python interface.
KiCad plans to remove this interface in KiCad 11, so these plugins require a separate migration for that version.
See the [KiCad Python interface documentation](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/).

| Plugin | Does ... |
|---|---|
| FabText | Annoyingly KiCAD footprints use various sizes in Fab text. This plugin makes them all the same size. |
| RoundFillZone | Create round fill zones, for when "Create Polygon from Selection..." makes far to many corners :) |
| RoundZoneRule | Create round zone rules, for when "Create Polygon from Selection..." makes far to many corners :) |
| Teardrops | Based on [NilujePerchut/kicad_scripts](https://github.com/NilujePerchut/kicad_scripts), but for KiCAD 10. Draws teardrops on vias with traces using polygons or fill zones - useful for making footprints, otherwise just use KiCAD's teardrop feature. |

*(This repository includes PCM packaging automation that publishes a release zip and updates `ts-kicad-repository`.)*

## Installation

Choose one of the three methods below.
The Plugin and Content Manager (PCM) is available from the KiCad Project Manager window.
The [KiCad PCM guide](https://docs.kicad.org/10.0/en/kicad/kicad.html#plugin-content-manager) describes package and repository management.

### Method 1: Install through the Tecsmith repository

The [consolidated Tecsmith repository](https://github.com/Tecsmith/ts-kicad-repository) contains the published libraries and plugins.

1. Open the KiCad Project Manager.
2. Open `Plugin and Content Manager`.
3. Click `Manage...` in the `Repository` tab.
4. Click `+` to add a repository.
5. Enter `Tecsmith repository` as the name.
6. Enter this repository URL:

   ```text
   https://raw.githubusercontent.com/Tecsmith/ts-kicad-repository/main/repository.json
   ```

7. Save the repository list.
8. Select the Tecsmith repository in the repository dropdown.
9. Click `Refresh` to load the available packages.
10. Select `ts-kicad-plugins` in the `Plugins` tab.
11. Click `Install`.
12. Click `Apply Pending Changes`.
13. Restart the PCB Editor.

### Method 2: Install a package ZIP through PCM

For a published version, download `ts-kicad-plugins-<version>.zip` from the [release assets](https://github.com/Tecsmith/ts-kicad-plugins/releases).
Continue at step 4 with that ZIP.
This route requires no Git or Python installation.

GitHub's `Code → Download ZIP` and `Source code (zip)` downloads contain the repository source.
They require packaging before installation because [PCM requires `metadata.json` and `plugins/` at the ZIP root](https://dev-docs.kicad.org/en/addons/#python-plugins).

To build a package from local source, use steps 1–3 first.
The build requires Python 3, available as `python3`.
Cloning the source also requires Git.
Use Terminal on macOS or Linux, or Git Bash on Windows:

1. Clone this repository:

   ```sh
   git clone https://github.com/Tecsmith/ts-kicad-plugins.git
   ```

   Alternatively, download the source with `Code → Download ZIP` on GitHub.
   Extract that ZIP before step 2.

2. Enter the source folder in your terminal.

   For a Git clone:

   ```sh
   cd ts-kicad-plugins
   ```

   For a source ZIP downloaded from `main`:

   ```sh
   cd ts-kicad-plugins-main
   ```

3. Build the package ZIP with a numeric version:

   ```sh
   sh pcm/create_pcm_archive.sh 2026.10.21
   ```

4. Open `Plugin and Content Manager` from the KiCad Project Manager.
5. Click `Install from file...`.
6. Select the downloaded release package or your locally built `pcm/ts-kicad-plugins-2026.10.21.zip`.
7. If PCM queues the installation, click `Apply Pending Changes`.
8. Restart the PCB Editor.

The script creates the package structure and metadata that PCM requires.
After local edits, repeat steps 3–8 to install the updated code.

### Method 3: Link a development clone into KiCad

This method keeps the Git clone in a development folder.
It requires Git.
A link named `tecsmith-plugins` exposes the clone's `plugins/` folder to KiCad.
After edits, restart the PCB Editor to load the updated code.

The examples use `$HOME/dev/ts-kicad-plugins` as the clone location.
If you already have a development clone, skip step 5 and use its path in the remaining commands.

The default folders for manually installed plugins in KiCad 10 are:

| Platform | Plugins folder |
|---|---|
| macOS | `~/Documents/KiCad/10.0/scripting/plugins` |
| Linux | `~/.local/share/kicad/10.0/scripting/plugins` |
| Windows | `%USERPROFILE%\Documents\KiCad\10.0\scripting\plugins` |

These paths follow [KiCad's script locations](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#_python_script_locations).
For custom paths, run the following commands in the PCB Editor's Python console:

```python
import pcbnew
print(pcbnew.PLUGIN_DIRECTORIES_SEARCH)
```

Use the matching scripting plugins folder in step 4.

1. If PCM already lists `ts-kicad-plugins` as installed, click `Uninstall`.
2. If you queued an uninstall, click `Apply Pending Changes`.
3. Open Terminal on macOS or Linux, or PowerShell on Windows.
4. Prepare the plugins folder with the commands for your operating system.

   macOS:

   ```sh
   kicad_plugins="$HOME/Documents/KiCad/10.0/scripting/plugins"
   mkdir -p "$kicad_plugins"
   ```

   Linux:

   ```sh
   kicad_plugins="$HOME/.local/share/kicad/10.0/scripting/plugins"
   mkdir -p "$kicad_plugins"
   ```

   Windows PowerShell:

   ```powershell
   $kicad_plugins = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'KiCad\10.0\scripting\plugins'
   New-Item -ItemType Directory -Force -Path $kicad_plugins | Out-Null
   ```

5. Clone this repository into a development folder.

   macOS or Linux:

   ```sh
   mkdir -p "$HOME/dev"
   git clone https://github.com/Tecsmith/ts-kicad-plugins.git "$HOME/dev/ts-kicad-plugins"
   ```

   Windows PowerShell:

   ```powershell
   New-Item -ItemType Directory -Force -Path "$HOME/dev" | Out-Null
   git clone https://github.com/Tecsmith/ts-kicad-plugins.git "$HOME/dev/ts-kicad-plugins"
   ```

6. Link the clone's `plugins/` folder with the command for your operating system.

   macOS or Linux:

   ```sh
   ln -s "$HOME/dev/ts-kicad-plugins/plugins" "$kicad_plugins/tecsmith-plugins"
   ```

   Windows PowerShell:

   ```powershell
   New-Item -ItemType Junction -Path "$kicad_plugins/tecsmith-plugins" -Target "$HOME/dev/ts-kicad-plugins/plugins"
   ```

7. Restart the PCB Editor.
8. Edit the files inside `$HOME/dev/ts-kicad-plugins` for development.

To download upstream changes, run this command in the same terminal:

```sh
git -C "$HOME/dev/ts-kicad-plugins" pull
```

## Using the plugins

The four plugins appear under `Tools → External Plugins` and provide toolbar buttons.
Round Zone Rule provides a layer selector because the Python interface does not expose the active editor layer.

Polygon teardrops use named groups so removal affects only generated shapes.
Keep these groups intact for automatic removal.
Polygons from older versions have no marker and require manual removal.
KiCad can report design rule violations because copper polygons have no assigned net.
