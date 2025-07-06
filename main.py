#!/usr/bin/env python3
import sys
import os
import json
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
from tkinter.font import Font
from typing import Dict, Any, Optional, List, Tuple, Union, Callable
import subprocess
import sys
import platform

# Constants
MODS_DIR = Path.home() / ".local" / "Bartender" / "Mods"
SOBER_MODS_DIR = Path.home() / ".var" / "app" / "org.vinegarhq.Sober" / "data" / "sober" / "asset_overlay"
CONFIG_PATH = Path.home() / ".var" / "app" / "org.vinegarhq.Sober" / "config" / "sober" / "config.json"
ICON_PATH = Path(__file__).parent / "Bartender.png"

# Ensure directories exist
MODS_DIR.mkdir(parents=True, exist_ok=True)
SOBER_MODS_DIR.mkdir(parents=True, exist_ok=True)

# Type aliases
ConfigType = Dict[str, Any]
PathLike = Union[str, os.PathLike]


def open_file_dialog(
    title: str = "Select File",
    initialdir: Optional[PathLike] = None,
    filetypes: Optional[List[Tuple[str, str]]] = None,
    parent: Optional[tk.Tk] = None,
    multiple: bool = False,
    save: bool = False,
    defaultextension: str = "",
    initialfile: str = ""
) -> Union[str, List[str], None]:
    """
    Open a file dialog using the system's default file browser if available,
    falling back to Tkinter's file dialog.
    
    Args:
        title: Dialog title
        initialdir: Initial directory
        filetypes: List of (description, pattern) tuples
        parent: Parent window
        multiple: Allow multiple file selection (open dialog only)
        save: If True, show save dialog instead of open dialog
        defaultextension: Default extension for save dialog
        initialfile: Initial file name for save dialog
        
    Returns:
        Selected file path(s) or None if canceled
    """
    def use_tkinter() -> Union[str, List[str], None]:
        """Fallback to Tkinter's file dialog."""
        if save:
            return filedialog.asksaveasfilename(
                title=title,
                defaultextension=defaultextension,
                filetypes=filetypes,
                initialdir=initialdir,
                initialfile=initialfile,
                parent=parent
            )
        elif multiple:
            return filedialog.askopenfilenames(
                title=title,
                initialdir=initialdir,
                filetypes=filetypes,
                parent=parent
            )
        else:
            return filedialog.askopenfilename(
                title=title,
                initialdir=initialdir,
                filetypes=filetypes,
                parent=parent
            )
    
    # Try to use system's default file browser
    system = platform.system().lower()
    
    try:
        if save:
            # For save dialogs, we'll use Tkinter as it's more consistent
            return use_tkinter()
            
        if system == 'linux':
            # Try zenity (GNOME, XFCE, etc.)
            try:
                cmd = ['zenity', '--file-selection', '--title', title]
                if multiple:
                    cmd.append('--multiple')
                if initialdir:
                    cmd.extend(['--filename', str(initialdir)])
                
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
                files = result.stdout.strip().split('|')
                return files if multiple and len(files) > 1 else files[0] if files else None
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
                
            # Try kdialog (KDE)
            try:
                cmd = ['kdialog', '--getopenfilename', f'--title={title}']
                if initialdir:
                    cmd.append(str(initialdir))
                if filetypes:
                    # Convert filetypes to KDialog format
                    types = []
                    for desc, ext in filetypes:
                        types.append(f'{desc} ({ext})')
                    cmd.append(' '.join(types))
                
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
                files = result.stdout.strip()
                return files if files else None
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        
        elif system == 'darwin':  # macOS
            try:
                cmd = ['osascript', '-e', f'''
                    choose file''' + 
                    (' with multiple selections allowed' if multiple else '') + 
                    (f''' with prompt "{title}"''' if title else '') +
                    (f''' default location "{initialdir}"''' if initialdir else '')
                ]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
                files = [f.strip() for f in result.stdout.strip().split(', ')]
                return files if multiple and len(files) > 1 else files[0] if files else None
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        
        elif system == 'windows':
            # Windows has a different approach, use Tkinter for now
            pass
            
    except Exception as e:
        print(f"Error using native file dialog: {e}", file=sys.stderr)
    
    # Fall back to Tkinter
    return use_tkinter()

class ModManager:
    @staticmethod
    def get_available_mods() -> List[Path]:
        """Return a list of available mod archives."""
        return [f for f in MODS_DIR.glob("*.zip") if f.is_file()]

    @staticmethod
    def _scan_directory_to_json(directory: Path) -> dict:
        """Recursively scan a directory and return its structure as a dictionary."""
        result = {}
        try:
            for item in directory.iterdir():
                if item.is_dir():
                    result[item.name] = ModManager._scan_directory_to_json(item)
                else:
                    result[item.name] = None
        except (PermissionError, OSError) as e:
            print(f"Warning: Could not scan {directory}: {e}")
        return result

    @staticmethod
    def _save_structure_to_file(structure: dict, file_path: Path) -> bool:
        """Save directory structure to a JSON file."""
        try:
            with open(file_path, 'w') as f:
                json.dump(structure, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving structure to {file_path}: {e}")
            return False

    @staticmethod
    def _load_structure_from_file(file_path: Path) -> Optional[dict]:
        """Load directory structure from a JSON file."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading structure from {file_path}: {e}")
            return None

    @staticmethod
    def _fix_case_issues(base_dir: Path, correct_structure: dict, log_callback=None) -> List[str]:
        """Fix case issues in directory structure to match correct structure."""
        changes = []
        
        def log(message, level='info'):
            if log_callback:
                log_callback(message, level)
            else:
                print(f"[{level.upper()}] {message}")
        
        def process_directory(current_path: Path, structure: dict, depth=0):
            nonlocal changes
            
            # Get all items in the current directory
            try:
                items = {item.name.lower(): item for item in current_path.iterdir()}
            except OSError as e:
                log(f"Could not list directory {current_path.relative_to(base_dir)}: {e}", 'error')
                return
            
            indent = '  ' * depth
            log(f"{indent}Checking: {current_path.relative_to(base_dir)}", 'debug')
            
            # Check each item in the correct structure
            for correct_name, substructure in structure.items():
                # Find matching item (case-insensitive)
                matched_item = items.get(correct_name.lower())
                
                if matched_item is None:
                    continue
                    
                # If names don't match (different case), rename
                if matched_item.name != correct_name:
                    new_path = matched_item.parent / correct_name
                    try:
                        log(f"{indent}  Renaming: {matched_item.name} -> {correct_name}", 'warning')
                        matched_item.rename(new_path)
                        change_msg = f"Renamed: {matched_item.relative_to(base_dir)} -> {new_path.relative_to(base_dir)}"
                        changes.append(change_msg)
                        log(f"{indent}  ✓ {change_msg}", 'success')
                        current_item = new_path
                    except OSError as e:
                        error_msg = f"Failed to rename {matched_item.name}: {e}"
                        changes.append(error_msg)
                        log(f"{indent}  ✗ {error_msg}", 'error')
                        current_item = matched_item
                else:
                    current_item = matched_item
                    log(f"{indent}  ✓ {current_item.name} (correct case)", 'debug')
                
                # Recurse into subdirectories
                if substructure is not None and current_item.is_dir():
                    process_directory(current_item, substructure, depth + 1)
        
        log(f"Starting verification of: {base_dir}", 'info')
        process_directory(base_dir, correct_structure)
        
        if not changes:
            log("No case issues found.", 'success')
        else:
            log(f"Found and fixed {len(changes)} case issues.", 'success')
            
        return changes

    # Class-level path constants
    BASE_CONTENT = Path.home() / ".var/app/org.vinegarhq.Sober/data/sober/assets/content"
    BASE_EXTRACONTENT = Path.home() / ".var/app/org.vinegarhq.Sober/data/sober/assets/ExtraContent"
    MOD_CONTENT = Path.home() / ".var/app/org.vinegarhq.Sober/data/sober/asset_overlay/content"
    MOD_EXTRACONTENT = Path.home() / ".var/app/org.vinegarhq.Sober/data/sober/asset_overlay/ExtraContent"
    
    @classmethod
    def verify_and_fix_mod_structures(cls) -> Tuple[bool, List[str]]:
        """Verify and fix mod directory structures to match base game casing."""
        # Use class-level paths
        BASE_CONTENT = cls.BASE_CONTENT
        BASE_EXTRACONTENT = cls.BASE_EXTRACONTENT
        MOD_CONTENT = cls.MOD_CONTENT
        MOD_EXTRACONTENT = cls.MOD_EXTRACONTENT
        
        # Check if base content exists
        if not (BASE_CONTENT.exists() or BASE_EXTRACONTENT.exists()):
            return False, ["Could not find base game files. Make sure Sober is installed and has downloaded the game files."]
        
        changes = []
        
        # Process content directory
        if BASE_CONTENT.exists() and MOD_CONTENT.exists():
            correct_structure = ModManager._scan_directory_to_json(BASE_CONTENT)
            changes.extend(ModManager._fix_case_issues(MOD_CONTENT, correct_structure))
        
        # Process ExtraContent directory
        if BASE_EXTRACONTENT.exists() and MOD_EXTRACONTENT.exists():
            correct_structure = ModManager._scan_directory_to_json(BASE_EXTRACONTENT)
            changes.extend(ModManager._fix_case_issues(MOD_EXTRACONTENT, correct_structure))
        
        if not changes:
            return True, ["No issues found. All mod files have correct casing."]
        return True, changes

    @staticmethod
    def _find_mod_content_dir(base_dir: Path) -> Optional[Path]:
        """Find the directory containing content/ExtraContent folders."""
        # Check root directory first
        if any((base_dir / name).exists() for name in ['content', 'ExtraContent']):
            return base_dir
            
        # Check first-level directories
        for item in base_dir.iterdir():
            if item.is_dir() and any((item / name).exists() for name in ['content', 'ExtraContent']):
                return item
                
        return None

    @staticmethod
    def install_mod(mod_path: Path) -> Tuple[bool, str]:
        """Install a mod by extracting it to the Sober mods directory.
        
        Args:
            mod_path: Path to the mod zip file
            
        Returns:
            Tuple of (success, message)
        """
        import tempfile
        import shutil
        
        temp_dir = Path(tempfile.mkdtemp(prefix='bartender_mod_'))
        
        try:
            # Extract to temp directory
            with zipfile.ZipFile(mod_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find the directory containing content/ExtraContent
            mod_content_dir = ModManager._find_mod_content_dir(temp_dir)
            if mod_content_dir is None:
                return False, (
                    f"Invalid mod structure in {mod_path.name}.\n\n"
                    "Mod archive must contain either 'content' or 'ExtraContent' directory.\n"
                    "Please install this mod manually if you believe this is an error."
                )
            
            # Ensure Sober mods directory exists
            SOBER_MODS_DIR.mkdir(parents=True, exist_ok=True)
            
            # Copy only content/ExtraContent folders directly to Sober mods directory
            copied_something = False
            for item in ['content', 'ExtraContent']:
                src = mod_content_dir / item
                dest = SOBER_MODS_DIR / item
                
                if src.exists():
                    # Remove existing content if it exists
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(src, dest)
                    copied_something = True
            
            if not copied_something:
                return False, "No valid content found to install"
            
            return True, f"Successfully installed {mod_path.name}"
            
        except Exception as e:
            return False, f"Failed to install {mod_path.name}: {str(e)}"
            
        finally:
            # Clean up temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

class FastFlagManager:
    @staticmethod
    def load_config() -> Optional[ConfigType]:
        """Load the Sober config file."""
        try:
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default config if file doesn't exist
            return {"fflags": {}}
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            return None

    @staticmethod
    def save_config(config: ConfigType) -> Tuple[bool, str]:
        """Save the Sober config file."""
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=4)
            return True, "Config saved successfully"
        except Exception as e:
            return False, f"Failed to save config: {str(e)}"

class ModsTab(ttk.Frame):
    def __init__(self, parent, status_var):
        super().__init__(parent, style='TFrame')
        self.status_var = status_var
        self.mod_manager = ModManager()
        
        # Define dark theme colors
        self.bg_color = '#2d2d2d'
        self.fg_color = '#e0e0e0'
        self.accent_color = '#4a90e2'
        self.highlight_bg = '#3a3a3a'
        
        self.setup_ui()
        self.refresh_mods_list()

    def setup_ui(self):
        # Configure grid weights
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)  # Let the treeview expand

        # Buttons frame with custom styling
        button_frame = ttk.Frame(self, style='TFrame')
        button_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        button_frame.columnconfigure(1, weight=1)  # Spacer

        # Import button
        self.import_btn = ttk.Button(
            button_frame,
            text="Import Mod",
            command=self.import_mod,
            style='Accent.TButton',
            width=15
        )
        self.import_btn.grid(row=0, column=0, padx=(0, 5), sticky="w")

        # Cleanup button
        self.cleanup_btn = ttk.Button(
            button_frame,
            text="Cleanup Mods",
            command=self.cleanup_mods,
            style='Danger.TButton',
            width=15
        )
        self.cleanup_btn.grid(row=0, column=2, padx=5, sticky="w")

        # Verify Structure button
        self.verify_btn = ttk.Button(
            button_frame,
            text="Verify Mod Structure",
            command=self.verify_mod_structures,
            style='Info.TButton',
            width=15
        )
        self.verify_btn.grid(row=0, column=3, padx=5, sticky="w")

        # Mods list with custom styling
        style = ttk.Style()
        style.configure("Treeview",
            background=self.highlight_bg,
            fieldbackground=self.highlight_bg,
            foreground=self.fg_color,
            borderwidth=0,
            rowheight=25
        )
        style.map('Treeview',
            background=[('selected', self.accent_color)],
            foreground=[('selected', 'white')]
        )
        
        # Configure the treeview heading style
        style.configure("Treeview.Heading",
            background=self.highlight_bg,
            foreground=self.fg_color,
            font=('Segoe UI', 9, 'bold'),
            relief='flat'
        )
            
        # Create treeview for mods with dark theme
        style = ttk.Style()
        style.configure('Mods.Treeview', 
                      rowheight=25, 
                      background=self.bg_color, 
                      fieldbackground=self.bg_color, 
                      foreground=self.fg_color)
        style.configure('Mods.Treeview.Heading', 
                      background=self.highlight_bg, 
                      foreground=self.fg_color,
                      font=('Segoe UI', 9, 'bold'))
        
        # Create a frame for the treeview and scrollbar
        tree_frame = ttk.Frame(self, style='TFrame')
        tree_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(5, 0))
        self.grid_rowconfigure(1, weight=1)  # Make the treeview expand vertically
        self.grid_columnconfigure(0, weight=1)  # Make the treeview expand horizontally
        
        # Create the treeview
        self.mods_tree = ttk.Treeview(
            tree_frame,
            columns=('Mod Name',),
            show='headings',
            selectmode='browse',
            style='Mods.Treeview'
        )
        
        # Configure the single column
        self.mods_tree.heading('Mod Name', text='Mod Name', anchor='w')
        self.mods_tree.column('Mod Name', anchor='w', stretch=tk.YES)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient=tk.VERTICAL,
            command=self.mods_tree.yview
        )
        self.mods_tree.configure(yscroll=scrollbar.set)
        
        # Grid the treeview and scrollbar
        self.mods_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double click to install/uninstall
        self.mods_tree.bind("<Double-1>", self.on_mod_double_click)
        
        # Configure tag for installed mods
        self.mods_tree.tag_configure('installed', foreground='#4caf50')  # Green for installed

    def refresh_mods_list(self):
        self.mods_tree.delete(*self.mods_tree.get_children())
        for mod_path in sorted(MODS_DIR.glob('*.zip')):
            mod_name = mod_path.stem
            self.mods_tree.insert('', 'end', values=(mod_name,))
    
    def on_mod_double_click(self, event):
        """Handle double-click on a mod in the list."""
        item = self.mods_tree.selection()[0]
        mod_name = self.mods_tree.item(item, 'values')[0]
        mod_path = MODS_DIR / f"{mod_name}.zip"
        
        if mod_path.exists():
            success, message = ModManager.install_mod(mod_path)
            if success:
                self.status_var.set(f"Installed mod: {mod_name}")
                messagebox.showinfo("Success", message)
                self.refresh_mods_list()
            else:
                self.status_var.set(f"Failed to install mod: {mod_name}")
                messagebox.showerror("Error", message)
        else:
            self.status_var.set(f"Mod file not found: {mod_path}")
            messagebox.showerror("Error", f"Mod file not found: {mod_path}")

    def import_mod(self):
        """Import a mod archive."""
        file_path = open_file_dialog(
            title="Select Mod Archive",
            filetypes=[("ZIP Archives", "*.zip"), ("All Files", "*")],
            parent=self.winfo_toplevel()
        )
        if file_path:
            try:
                dest_path = MODS_DIR / Path(file_path).name
                shutil.copy2(file_path, dest_path)
                self.refresh_mods_list()
                self.status_var.set(f"Imported mod: {dest_path.name}")
                messagebox.showinfo("Success", f"Successfully imported {dest_path.name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import mod: {str(e)}")
                self.status_var.set("Failed to import mod")

    def cleanup_mods(self):
        if not SOBER_MODS_DIR.exists():
            messagebox.showinfo("No Mods", "No mods directory found to clean up.")
            return
            
        confirm = messagebox.askyesno(
            "Confirm Cleanup",
            "This will remove all installed mods. Are you sure?",
            icon='warning'
        )
        
        if confirm:
            try:
                # Remove all directories in the mods directory
                for item in SOBER_MODS_DIR.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                
                self.status_var.set("All mods have been removed")
                self.refresh_mods_list()
                messagebox.showinfo("Success", "All mods have been removed successfully")
                
            except Exception as e:
                self.status_var.set(f"Error removing mods: {str(e)}")
                messagebox.showerror("Error", f"Failed to remove mods: {str(e)}")

    def verify_mod_structures(self):
        """Verify and fix mod directory structures to match base game casing."""
        import threading
        from tkinter import ttk as ttk
        
        # Create a popup window
        popup = tk.Toplevel(self)
        popup.title("Verifying Mod Structures")
        popup.geometry("800x600")
        popup.resizable(True, True)
        
        # Make popup modal
        popup.transient(self.master)
        popup.grab_set()
        
        # Add a text widget for output with monospace font
        text_frame = ttk.Frame(popup)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add clear button and status label
        control_frame = ttk.Frame(popup)
        control_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        
        status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(control_frame, textvariable=status_var)
        status_label.pack(side=tk.LEFT)
        
        def clear_log():
            output_text.delete(1.0, tk.END)
            
        clear_btn = ttk.Button(control_frame, text="Clear Log", command=clear_log)
        clear_btn.pack(side=tk.RIGHT)
        
        # Text widget with better styling
        output_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('DejaVu Sans Mono', 9),
            bg='#1e1e1e',
            fg='#e0e0e0',
            insertbackground='#e0e0e0',
            selectbackground='#264f78',
            padx=10,
            pady=10,
            undo=True,
            maxundo=-1
        )
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=output_text.yview)
        output_text.configure(yscrollcommand=scrollbar.set)
        
        # Grid layout for better resizing
        output_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # Add a frame for buttons at the bottom
        btn_frame = ttk.Frame(popup)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Add copy to clipboard button
        def copy_to_clipboard():
            text = output_text.get(1.0, tk.END).strip()
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
                status_var.set("Log copied to clipboard!")
                self.after(2000, lambda: status_var.set("Ready"))
                
        copy_btn = ttk.Button(btn_frame, text="Copy to Clipboard", command=copy_to_clipboard)
        copy_btn.pack(side=tk.LEFT, padx=5)
        
        # Add close button
        close_btn = ttk.Button(btn_frame, text="Close", command=popup.destroy, style="Accent.TButton")
        close_btn.pack(side=tk.RIGHT, padx=5)
        
        # Configure tags for different message types
        output_text.tag_configure('info', foreground='#4fc3f7')  # Light blue for info
        output_text.tag_configure('success', foreground='#69f0ae')  # Green for success
        output_text.tag_configure('warning', foreground='#ffd54f')  # Yellow for warnings
        output_text.tag_configure('error', foreground='#ff8a80')  # Red for errors
        output_text.tag_configure('debug', foreground='#b39ddb')  # Purple for debug
        output_text.tag_configure('highlight', background='#2a2a2a')  # For highlighting
        
        def log(message, level='info', highlight=False):
            """Add a log message with the specified level."""
            timestamp = datetime.now().strftime("%H:%M:%S")
            tag = level.lower()
            
            # Add timestamp
            output_text.insert(tk.END, f"[{timestamp}] ", 'debug')
            
            # Add message with appropriate tag
            output_text.insert(tk.END, message, tag)
            
            # Add newline and scroll to end
            output_text.insert(tk.END, "\n")
            output_text.see(tk.END)
            output_text.update_idletasks()
            
            # Auto-scroll to the end
            output_text.see(tk.END)
        
        def run_verification():
            try:
                log("Starting mod structure verification...", 'info')
                log(f"Base paths: {self.mod_manager.BASE_CONTENT} | {self.mod_manager.BASE_EXTRACONTENT}", 'debug')
                log(f"Mod paths: {self.mod_manager.MOD_CONTENT} | {self.mod_manager.MOD_EXTRACONTENT}", 'debug')
                
                # Check if base content exists
                if not (self.mod_manager.BASE_CONTENT.exists() or self.mod_manager.BASE_EXTRACONTENT.exists()):
                    log("Error: Could not find base game files.", 'error')
                    log("Please ensure Sober is installed and has downloaded the game files.", 'error')
                    return
                
                # Process content directory
                if self.mod_manager.BASE_CONTENT.exists() and self.mod_manager.MOD_CONTENT.exists():
                    log(f"\nProcessing content directory...", 'info')
                    log(f"Scanning base content: {self.mod_manager.BASE_CONTENT}", 'debug')
                    correct_structure = self.mod_manager._scan_directory_to_json(self.mod_manager.BASE_CONTENT)
                    changes = self.mod_manager._fix_case_issues(self.mod_manager.MOD_CONTENT, correct_structure, log_callback=log)
                    
                    if changes:
                        log(f"\nMade {len(changes)} corrections in content directory:", 'info')
                        for change in changes:
                            log(f"• {change}", 'success')
                    else:
                        log("No issues found in content directory.", 'success')
                
                # Process ExtraContent directory
                if self.mod_manager.BASE_EXTRACONTENT.exists() and self.mod_manager.MOD_EXTRACONTENT.exists():
                    log(f"\nProcessing ExtraContent directory...", 'info')
                    log(f"Scanning base ExtraContent: {self.mod_manager.BASE_EXTRACONTENT}", 'debug')
                    correct_structure = self.mod_manager._scan_directory_to_json(self.mod_manager.BASE_EXTRACONTENT)
                    changes = self.mod_manager._fix_case_issues(self.mod_manager.MOD_EXTRACONTENT, correct_structure, log_callback=log)
                    
                    if changes:
                        log(f"\nMade {len(changes)} corrections in ExtraContent directory:", 'info')
                        for change in changes:
                            log(f"• {change}", 'success')
                    else:
                        log("No issues found in ExtraContent directory.", 'success')
                
                log("\n✓ Verification completed successfully!", 'success')
                
            except Exception as e:
                log(f"\nError during verification: {str(e)}", 'error')
                import traceback
                log(traceback.format_exc(), 'error')
            finally:
                log("\nVerification process finished.", 'info')
        
        # Start verification in a separate thread
        threading.Thread(target=run_verification, daemon=True).start()
        
        # Center the popup
        popup.update_idletasks()
        width = min(1000, popup.winfo_screenwidth() - 100)
        height = min(700, popup.winfo_screenheight() - 100)
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f'{width}x{height}+{x}+{y}')
        
        # Set focus to the text widget
        output_text.focus_set()

class FastFlagsTab(ttk.Frame):
    def __init__(self, parent, status_var):
        super().__init__(parent, style='TFrame')
        self.status_var = status_var
        
        # Define dark theme colors
        self.bg_color = '#2d2d2d'
        self.fg_color = '#e0e0e0'
        self.accent_color = '#4a90e2'
        self.highlight_bg = '#3a3a3a'
        
        # Store flag values
        self.flag_values = {}
        
        self.setup_ui()
        self.load_flags()

    def setup_ui(self):
        # Configure grid weights
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)  # Let the treeview expand

        # Search frame
        search_frame = ttk.Frame(self, style='TFrame')
        search_frame.pack(fill='x', padx=10, pady=5)
        
        # Search label and entry with proper styling
        ttk.Label(
            search_frame,
            text="Search:",
            style='TLabel'
        ).pack(side='left', padx=(0, 5))
        
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            style='TEntry',
            width=40
        )
        search_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        # Bind search variable to refresh function
        def on_search_callback(*args):
            self.refresh_flags()
        self.search_var.trace("w", lambda *args: on_search_callback())
        
        # Buttons frame with custom styling
        button_frame = ttk.Frame(self, style='TFrame')
        button_frame.pack(fill='x', padx=10, pady=(0, 5))
        
        # Button container
        btn_container = ttk.Frame(button_frame, style='TFrame')
        btn_container.pack(side='right')
        
        # Button container for flag management
        btn_frame = ttk.Frame(btn_container)
        btn_frame.pack(side='left', padx=(0, 10))
        
        # Add/Remove flag buttons
        ttk.Button(
            btn_frame,
            text="+ Add Flag",
            command=self.add_flag,
            style='Accent.TButton',
            width=12
        ).pack(side='left', padx=(0, 5))
        
        ttk.Button(
            btn_frame,
            text="- Remove Flag",
            command=self.remove_flag,
            style='Danger.TButton',
            width=12
        ).pack(side='left', padx=(0, 10))
        
        # Separator
        ttk.Separator(btn_container, orient='vertical').pack(side='left', fill='y', padx=5)
        
        # Import/Export buttons
        ttk.Button(
            btn_container,
            text="Import Flags",
            command=self.import_flags,
            style='Info.TButton',
            width=12
        ).pack(side='left', padx=5)
        
        ttk.Button(
            btn_container,
            text="Export Flags",
            command=self.export_flags,
            style='Info.TButton',
            width=12
        ).pack(side='left', padx=(0, 5))
        
        # Save button with accent color
        ttk.Button(
            btn_container,
            text="Save Changes",
            command=self.save_flags,
            style='Success.TButton',
            width=15
        ).pack(side='left')
        
        # Create treeview with dark theme and left alignment
        style = ttk.Style()
        style.configure('Treeview', rowheight=25, background=self.bg_color, fieldbackground=self.bg_color, foreground=self.fg_color)
        style.configure('Treeview.Heading', background=self.highlight_bg, foreground=self.fg_color)
        
        self.tree = ttk.Treeview(self, selectmode='browse', show='tree headings', style='Treeview')
        self.tree['columns'] = ('Flag Name', 'Value')
        
        # Configure columns with left alignment
        self.tree.column('#0', width=0, stretch=tk.NO)  # Hide first empty column
        self.tree.column('Flag Name', anchor='w', width=400, minwidth=200)
        self.tree.column('Value', anchor='w', width=200, minwidth=100)
        
        # Configure headings with left alignment
        self.tree.heading('Flag Name', text='Flag Name', anchor='w')
        self.tree.heading('Value', text='Value', anchor='w')
        self.tree.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Add a frame for buttons at the bottom
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        # Add copy to clipboard button
        def copy_to_clipboard():
            text = self.tree.item(self.tree.selection()[0], 'values')[1]
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Log copied to clipboard!")
                self.after(2000, lambda: self.status_var.set("Ready"))
                
        copy_btn = ttk.Button(btn_frame, text="Copy to Clipboard", command=copy_to_clipboard)
        copy_btn.pack(side=tk.LEFT, padx=5)
        
        # No close button to avoid confusion
        
        # Configure tags for different message types
        self.tree.tag_configure('true', foreground='#69f0ae')  # Green for true
        self.tree.tag_configure('false', foreground='#ff8a80')  # Red for false
        
        # Bind double-click event to edit flag
        self.tree.bind('<Double-1>', self.on_flag_edit)
        
        self.load_flags()
        
    def load_flags(self):
        """Load flags from the config file into the UI."""
        try:
            # Load config using FastFlagManager
            self.config = FastFlagManager.load_config()
            
            if not self.config or not isinstance(self.config, dict):
                self.status_var.set("No valid config found")
                self.config = {"fflags": {}}
            
            # Initialize flags if they don't exist
            if "fflags" not in self.config:
                self.config["fflags"] = {}
            
            self.flag_values = self.config["fflags"].copy()
            self.refresh_flags()
            
        except Exception as e:
            self.status_var.set(f"Error loading flags: {str(e)}")
            messagebox.showerror("Error", f"Failed to load flags: {str(e)}")
            self.config = {"fflags": {}}  # Initialize empty config on error
    
    def refresh_flags(self):
        """Refresh the flags list based on search filter."""
        if not hasattr(self, 'tree'):
            return
            
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get search term
        search_term = self.search_var.get().lower() if hasattr(self, 'search_var') else ''
        
        # Add filtered flags to treeview
        for flag_name, flag_value in sorted(self.flag_values.items()):
            if search_term and search_term not in flag_name.lower():
                continue
                
            # Format the value for display
            if isinstance(flag_value, bool):
                value_str = str(flag_value).lower()
                tag = 'true' if flag_value else 'false'
            else:
                value_str = str(flag_value)
                tag = ''
            
            # Add to treeview with appropriate tags
            self.tree.insert('', 'end', 
                          values=(flag_name, value_str),
                          tags=(tag,))
        
    def on_search(self, *args):
        """Handle search box text changes."""
        self.refresh_flags()
        
    def save_flags(self):
        """Save the current flag values to the config file."""
        if not hasattr(self, 'config') or not self.config:
            self.status_var.set("No config loaded to save")
            return False
            
        try:
            # Update config with current values
            self.config["fflags"] = self.flag_values
            
            # Save using FastFlagManager
            success, message = FastFlagManager.save_config(self.config)
            if success:
                self.status_var.set("Flags saved successfully")
            else:
                self.status_var.set(f"Error: {message}")
            return success
            
        except Exception as e:
            error_msg = f"Error saving flags: {str(e)}"
            self.status_var.set(error_msg)
            messagebox.showerror("Error", error_msg)
            return False
            
    def add_flag(self):
        """Add a new flag with a dialog."""
        flag_name = simpledialog.askstring("Add Flag", "Enter flag name:")
        if flag_name:
            flag_value = simpledialog.askstring("Add Flag", f"Enter value for {flag_name}:")
            if flag_value is not None:
                # Try to convert to appropriate type
                try:
                    if flag_value.lower() == 'true':
                        flag_value = True
                    elif flag_value.lower() == 'false':
                        flag_value = False
                    elif flag_value.isdigit():
                        flag_value = int(flag_value)
                    elif flag_value.replace('.', '', 1).isdigit() and flag_value.count('.') < 2:
                        flag_value = float(flag_value)
                    
                    self.flag_values[flag_name] = flag_value
                    self.refresh_flags()
                    self.status_var.set(f"Added flag: {flag_name}")
                except Exception as e:
                    messagebox.showerror("Error", f"Invalid value: {str(e)}")
    
    def remove_flag(self):
        """Remove the selected flag."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a flag to remove")
            return
            
        item = selected[0]
        flag_name = self.tree.item(item, 'values')[0]
        
        if messagebox.askyesno("Confirm", f"Remove flag '{flag_name}'?"):
            if flag_name in self.flag_values:
                del self.flag_values[flag_name]
                self.refresh_flags()
                self.status_var.set(f"Removed flag: {flag_name}")
    
    def on_flag_edit(self, event):
        """Handle double-click to edit a flag value."""
        try:
            # Get selected item
            selected = self.tree.selection()
            if not selected:
                return
                
            item = selected[0]
            flag_name = self.tree.item(item, 'values')[0]
            current_value = self.flag_values.get(flag_name, "")
            
            # Create a simple dialog to edit the value
            new_value = simpledialog.askstring(
                "Edit Flag Value",
                f"Enter new value for {flag_name}:",
                initialvalue=str(current_value)
            )
            
            if new_value is not None and new_value != str(current_value):
                # Convert string to appropriate type
                try:
                    if new_value.lower() == 'true':
                        new_value = True
                    elif new_value.lower() == 'false':
                        new_value = False
                    elif new_value.isdigit():
                        new_value = int(new_value)
                    elif new_value.replace('.', '', 1).isdigit() and new_value.count('.') < 2:
                        new_value = float(new_value)
                    
                    # Update the value
                    self.flag_values[flag_name] = new_value
                    self.refresh_flags()
                    self.status_var.set(f"Updated {flag_name}")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Invalid value: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit flag: {str(e)}")
    def import_flags(self):
        """Import flags from a JSON file."""
        file_path = open_file_dialog(
            title="Import Flags",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*")],
            parent=self.winfo_toplevel()
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    imported_flags = json.load(f)
                
                if not isinstance(imported_flags, dict):
                    raise ValueError("Invalid format: Expected a JSON object")
                
                # Update config with imported flags
                if "fflags" not in self.config:
                    self.config["fflags"] = {}
                
                self.config["fflags"].update(imported_flags)
                
                # Refresh the UI
                self.load_flags()
                messagebox.showinfo("Success", "Successfully imported FFlags")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import FFlags: {str(e)}")
    
    def export_flags(self):
        if not self.config or "fflags" not in self.config:
            messagebox.showwarning("No FFlags", "No FFlags to export")
            return
        
        # Use the system save dialog
        file_path = open_file_dialog(
            title="Export Flags",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*")],
            save=True,
            defaultextension=".json",
            initialfile="fflags_export.json"
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.config["fflags"], f, indent=4)
                messagebox.showinfo("Success", f"FFlags exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export FFlags: {str(e)}")

# ... (rest of the code remains the same)
        self.geometry("1000x700")
        self.minsize(900, 600)
        
        # Set application icon if available
        try:
            self.iconphoto(False, tk.PhotoImage(file=ICON_PATH))
        except:
            pass  # Icon not critical, continue without it
        
        # Configure styles
        self.style = ttk.Style()
        self.style.theme_use("clam")  # Modern theme as base
        
        # Custom color scheme
        self.bg_color = '#2d2d2d'
        self.fg_color = '#e0e0e0'
        self.accent_color = '#4a90e2'
        self.success_color = '#4caf50'
        self.warning_color = '#ff9800'
        self.danger_color = '#f44336'
        self.highlight_bg = '#3a3a3a'
        
        # Configure button styles
        self.style.configure('TButton', padding=6, relief='flat', background=self.bg_color)
        self.style.map('TButton',
            background=[('active', self.highlight_bg)],
            foreground=[('active', self.fg_color)]
        )
        
        # Accent button style
        self.style.configure('Accent.TButton',
            background=self.accent_color,
            foreground='white',
            font=('Segoe UI', 9, 'bold')
        )
        self.style.map('Accent.TButton',
            background=[('active', '#3a7bc8')],
            foreground=[('active', 'white')]
        )
        
        # Success button style
        self.style.configure('Success.TButton',
            background=self.success_color,
            foreground='white',
            font=('Segoe UI', 9, 'bold')
        )
        self.style.map('Success.TButton',
            background=[('active', '#43a047')],
            foreground=[('active', 'white')]
        )
        
        # Danger button style
        self.style.configure('Danger.TButton',
            background=self.danger_color,
            foreground='white',
            font=('Segoe UI', 9, 'bold')
        )
        self.style.map('Danger.TButton',
            background=[('active', '#e53935')],
            foreground=[('active', 'white')]
        )
        
        # Info button style
        self.style.configure('Info.TButton',
            background=self.highlight_bg,
            foreground=self.fg_color,
            font=('Segoe UI', 9)
        )
        self.style.map('Info.TButton',
            background=[('active', '#4a4a4a')],
            foreground=[('active', self.fg_color)]
        )
        
        # Configure main window appearance
        self.configure(bg=self.bg_color)
        
        # Configure ttk styles
        self._configure_styles()
        
        # Create main container
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create notebook (tabs) with custom style
        self.notebook = ttk.Notebook(self.container)
        self.notebook.pack(expand=True, fill='both')
        
        # Create status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(
            self.container, 
            textvariable=self.status_var,
            style='Status.TLabel',
            padding=(10, 5)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        self.status_var.set("Ready")
        
        # Create tabs
        self.mods_tab = ModsTab(self.notebook, self.status_var)
        self.fastflags_tab = FastFlagsTab(self.notebook, self.status_var)
        
        # Add tabs to notebook with custom styling
        self.notebook.add(self.mods_tab, text="  Mods  ")
        self.notebook.add(self.fastflags_tab, text="  FastFlags  ")
        
        # Add some padding around the notebook
        self.notebook.pack_configure(padx=5, pady=5)
        
        # Add version info
        version_label = ttk.Label(
            self.container,
            text=f"Bartender v1.0.0",
            style='Version.TLabel'
        )
        version_label.pack(side=tk.RIGHT, padx=5, pady=2)
        
        # Check if Sober is installed
        self.check_sober_installation()
        
        # Center window on screen
        self._center_window()
    
    def _center_window(self):
        """Center the window on the screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def _configure_styles(self):
        """Configure custom ttk styles."""
        # Frame styles
        self.style.configure('TFrame', background=self.bg_color)
        
        # Label styles
        self.style.configure('TLabel', 
                           background=self.bg_color, 
                           foreground=self.fg_color,
                           font=('Segoe UI', 9))
        
        # Status bar style
        self.style.configure('Status.TLabel',
                           background=self.highlight_bg,
                           foreground='#a0a0a0',
                           font=('Segoe UI', 8),
                           anchor='w')
        
        # Version label style
        self.style.configure('Version.TLabel',
                           background=self.bg_color,
                           foreground='#707070',
                           font=('Segoe UI', 8))
        
        # Notebook style
        self.style.configure('TNotebook', background=self.bg_color, borderwidth=0)
        self.style.configure('TNotebook.Tab',
                           padding=[15, 5],
                           background=self.highlight_bg,
                           foreground=self.fg_color,
                           font=('Segoe UI', 9, 'bold'),
                           borderwidth=0)
        self.style.map('TNotebook.Tab',
                     background=[('selected', self.accent_color)],
                     foreground=[('selected', 'white')])
        
        # Button styles
        button_font = ('Segoe UI', 9, 'bold')
        
        # Default button
        self.style.configure('TButton',
                           padding=6,
                           font=button_font,
                           borderwidth=1,
                           relief='flat')
        self.style.map('TButton',
                     background=[('active', self.highlight_bg)],
                     foreground=[('active', 'white')])
        
        # Primary button (blue accent)
        self.style.configure('Accent.TButton',
                           foreground='white',
                           background=self.accent_color,
                           font=button_font)
        self.style.map('Accent.TButton',
                     background=[('active', '#3a7bc8')],
                     foreground=[('active', 'white')])
        
        # Success button (green)
        self.style.configure('Success.TButton',
                           foreground='white',
                           background=self.success_color,
                           font=button_font)
        self.style.map('Success.TButton',
                     background=[('active', '#43a047')],
                     foreground=[('active', 'white')])
        
        # Danger button (red)
        self.style.configure('Danger.TButton',
                           foreground='white',
                           background=self.danger_color,
                           font=button_font)
        self.style.map('Danger.TButton',
                     background=[('active', '#d32f2f')],
                     foreground=[('active', 'white')])
        
        # Entry and Combobox styles
        self.style.configure('TEntry',
                           fieldbackground='#3a3a3a',
                           foreground=self.fg_color,
                           insertcolor=self.fg_color,
                           borderwidth=1,
                           relief='solid')
        
        self.style.map('TEntry',
                     fieldbackground=[('readonly', '#3a3a3a')],
                     foreground=[('readonly', self.fg_color)])
        
        # Scrollbar style
        self.style.configure('TScrollbar',
                           background=self.highlight_bg,
                           troughcolor=self.bg_color,
                           borderwidth=0,
                           arrowsize=12)
        
        # Treeview style
        self.style.configure('Treeview',
                           background='#3a3a3a',
                           fieldbackground='#3a3a3a',
                           foreground=self.fg_color,
                           borderwidth=0,
                           rowheight=25)
        
        self.style.map('Treeview',
                     background=[('selected', self.accent_color)],
                     foreground=[('selected', 'white')])
        
        # Treeview heading
        self.style.configure('Treeview.Heading',
                           background=self.highlight_bg,
                           foreground=self.fg_color,
                           font=('Segoe UI', 9, 'bold'),
                           relief='flat')
        
        # Notebook tab padding
        self.style.layout('TNotebook.Tab',
                        [('Notebook.tab',
                         {'sticky': 'nswe',
                          'children':
                              [('Notebook.padding',
                               {'side': 'top',
                                'sticky': 'nswe',
                                'children':
                                    [('Notebook.label',
                                     {'side': 'top',
                                      'sticky': ''})],
                                }),],
                          })])

    def check_sober_installation(self):
        """Check if Sober is installed and update status."""
        sober_config = Path.home() / ".var/app/org.vinegarhq.Sober/config/sober/config.json"
        if sober_config.exists():
            self.status_var.set("Ready - Sober installation found")
        else:
            self.status_var.set("Warning: Sober installation not found")
            messagebox.showwarning(
                "Sober Not Found",
                "Sober installation not found. Some features may not work correctly.\n\n"
                "Please install Sober from https://github.com/vinegarhq/vinegar"
            )
        self.status_var.set("Ready")

        # Check for Sober installation
        self.check_sober_installation()

    def check_sober_installation(self):
        if not os.path.exists(os.path.expanduser("~/.var/app/org.vinegarhq.Sober")):
            messagebox.showwarning(
                "Sober Not Found",
                "Sober installation not found. Please install Sober first.\n\n"
                "Bartender will still work, but some features may not function correctly."
            )
            self.status_var.set("Warning: Sober not found. Some features may not work.")
        else:
            self.status_var.set("Ready")


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Configure main window
        self.title("Bartender - Linux Roblox Mod Manager")
        self.geometry("1000x700")
        self.minsize(900, 600)
        
        # Set application icon if available
        try:
            # Try to set the application icon (works on Windows and some Linux)
            if os.name == 'nt':  # Windows
                import ctypes
                myappid = 'runaxr.Bartender.1.0'  # arbitrary string
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass  # Icon setting is optional
        
        # Configure styles
        self.style = ttk.Style()
        self.style.theme_use("clam")  # Modern theme as base
        
        # Custom color scheme
        self.bg_color = '#2d2d2d'
        self.fg_color = '#e0e0e0'
        self.accent_color = '#4a90e2'
        self.success_color = '#4caf50'
        self.warning_color = '#ff9800'
        self.danger_color = '#f44336'
        self.highlight_bg = '#3a3a3a'
        
        # Configure main window appearance
        self.configure(bg=self.bg_color)
        
        # Create main container
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.container)
        self.notebook.pack(expand=True, fill='both')
        
        # Create status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(
            self.container,
            textvariable=self.status_var,
            style='Status.TLabel',
            padding=(10, 5)
        )
        self.status_bar.pack(fill='x', pady=(5, 0))
        
        # Create tabs
        self.mods_tab = ModsTab(self.notebook, self.status_var)
        self.fastflags_tab = FastFlagsTab(self.notebook, self.status_var)
        
        self.notebook.add(self.mods_tab, text="Mods")
        self.notebook.add(self.fastflags_tab, text="Fast Flags")
        
        # Configure styles
        self._configure_styles()
        
        # Initial status
        self.status_var.set("Ready")
        self.check_sober_installation()
    
    def _configure_styles(self):
        """Configure ttk styles."""
        # Configure button styles
        button_font = ('Segoe UI', 9)
        
        # Regular button
        self.style.configure('TButton',
                           padding=6,
                           relief='flat',
                           background=self.bg_color,
                           foreground=self.fg_color,
                           font=button_font)
        
        self.style.map('TButton',
                     background=[('active', self.highlight_bg)],
                     foreground=[('active', self.fg_color)])
        
        # Accent button (blue)
        self.style.configure('Accent.TButton',
                           foreground='white',
                           background=self.accent_color,
                           font=button_font)
        self.style.map('Accent.TButton',
                     background=[('active', '#3a7bc8')],
                     foreground=[('active', 'white')])
        
        # Success button (green)
        self.style.configure('Success.TButton',
                           foreground='white',
                           background=self.success_color,
                           font=button_font)
        self.style.map('Success.TButton',
                     background=[('active', '#43a047')],
                     foreground=[('active', 'white')])
        
        # Danger button (red)
        self.style.configure('Danger.TButton',
                           foreground='white',
                           background=self.danger_color,
                           font=button_font)
        self.style.map('Danger.TButton',
                     background=[('active', '#d32f2f')],
                     foreground=[('active', 'white')])
        
        # Entry and Combobox styles
        self.style.configure('TEntry',
                           fieldbackground='#3a3a3a',
                           foreground=self.fg_color,
                           insertcolor=self.fg_color,
                           borderwidth=1,
                           relief='solid')
        
        self.style.map('TEntry',
                     fieldbackground=[('readonly', '#3a3a3a')],
                     foreground=[('readonly', self.fg_color)])
        
        # Scrollbar style
        self.style.configure('TScrollbar',
                           background=self.highlight_bg,
                           troughcolor=self.bg_color,
                           borderwidth=0,
                           arrowsize=12)
        
        # Treeview style
        self.style.configure('Treeview',
                           background='#3a3a3a',
                           fieldbackground='#3a3a3a',
                           foreground=self.fg_color,
                           borderwidth=0,
                           rowheight=25)
        
        self.style.map('Treeview',
                     background=[('selected', self.accent_color)],
                     foreground=[('selected', 'white')])
        
        # Treeview heading
        self.style.configure('Treeview.Heading',
                           background=self.highlight_bg,
                           foreground=self.fg_color,
                           font=('Segoe UI', 9, 'bold'),
                           relief='flat')
        
        # Status bar style
        self.style.configure('Status.TLabel',
                           background=self.highlight_bg,
                           foreground=self.fg_color,
                           font=('Segoe UI', 8),
                           anchor='w')
        
        # Frame style
        self.style.configure('TFrame', background=self.bg_color)
        
        # Label style
        self.style.configure('TLabel',
                           background=self.bg_color,
                           foreground=self.fg_color)
        
        # Notebook style
        self.style.configure('TNotebook', background=self.bg_color)
        self.style.configure('TNotebook.Tab',
                           background=self.bg_color,
                           foreground=self.fg_color,
                           padding=[10, 5],
                           font=('Segoe UI', 9))
        
        self.style.map('TNotebook.Tab',
                     background=[('selected', self.highlight_bg)],
                     foreground=[('selected', self.fg_color), ('active', self.accent_color)])
    
    def check_sober_installation(self):
        """Check if Sober is installed and update status."""
        sober_config = Path.home() / ".var/app/org.vinegarhq.Sober/config/sober/config.json"
        if sober_config.exists():
            self.status_var.set("Ready - Sober installation found")
        else:
            self.status_var.set("Warning: Sober installation not found")
            messagebox.showwarning(
                "Sober Not Found",
                "Sober installation not found. Some features may not work correctly.\n\n"
                "Please install Sober from https://github.com/vinegarhq/vinegar"
            )


def main():
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    # Enable high DPI scaling if available
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass  # Not on Windows or DPI scaling not available
    
    main()
