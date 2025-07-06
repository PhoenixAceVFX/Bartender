<div align="center">
  <img src="Bartender.png" alt="Bartender Logo" width="200"/>
  <h1>Bartender</h1>
  <p>A simple and user-friendly mod and fastflag manager for Roblox on Linux, designed to work with Sober.</p>
  
  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
</div>

## 📋 Overview

Bartender is a simple tool that helps you manage Roblox mods and fastflags on Linux systems using Sober. With its simple interface, you can easily install mods, and customize your Roblox experience.

## ✨ Features

### 🎮 Mod Management
- **Easy Installation**: Simply double-click to install mods
- **Mod Import**: Import mod archives (.zip) with drag-and-drop support
- **Clean Interface**: View all your installed mods in a simple, organized list
- **One-Click Cleanup**: Remove all installed mods with a single click

### ⚙️ Fastflag Management
- **Live Editing**: Double-click any flag to modify its value
- **Smart Search**: Quickly find specific flags with the search bar
- **Type Support**: Automatic type detection for boolean, integer, float, and string values
- **Import/Export**: Save and load flag configurations as JSON files
- **Native File Dialogs**: Uses your system's native file dialogs for a seamless experience

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- Sober (Vinegar) installed and configured
- Required system dependencies:
  ```bash
  # For Debian/Ubuntu
  sudo apt install python3-tk python3-pil.imagetk
  
  # For Arch Linux
  sudo pacman -S tk python-pillow
  ```

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Bartender.git
   cd Bartender
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run Bartender:
   ```bash
   python main.py
   ```

### Building from Source
To create a standalone executable:

```bash
# Install PyInstaller if you haven't already
pip install pyinstaller

# Build the executable
pyinstaller --windowed --onefile --icon=Bartender.png --name Bartender main.py

# The executable will be in the 'dist' directory
```

## 🖥️ Usage

### Managing Mods
1. **Import Mods**: Click the "Import Mod" button to add new mods
2. **Install**: Double-click any mod to install it
3. **Clean Up**: Use the "Cleanup Mods" button to remove all installed mods

### Working with Fastflags
1. **Edit Values**: Double-click any flag to edit its value
2. **Search**: Use the search bar to quickly find specific flags
3. **Save Changes**: Click "Save Changes" to apply your modifications
4. **Import/Export**: Use the respective buttons to save or load flag configurations

## 📁 File Locations
- **Mods Directory**: `~/.local/Bartender/Mods/`
- **Installed Mods**: `~/.var/app/org.vinegarhq.Sober/data/sober/asset_overlay/`
- **Sober Config**: `~/.var/app/org.vinegarhq.Sober/config/sober/config.json`
d
## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for any bugs or feature requests.

1. Fork the repository
2. Create a new branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

Distributed under the GPL-3.0 License. See `LICENSE` for more information.

## 💡 Acknowledgements

- [Sober (Vinegar)](https://github.com/vinegarhq/sober) - For making Roblox on Linux possible
- [Roblox](https://www.roblox.com) - For creating an amazing gaming platform

---

<div align="center">
  Made with ❤️ for the Linux gaming community
</div>
