import PyInstaller.__main__
import customtkinter
import os

# Get path to customtkinter to include its assets
ctk_path = os.path.dirname(customtkinter.__file__)

print(f"CustomTkinter found at: {ctk_path}")

PyInstaller.__main__.run([
    'launcher.py',
    '--name=NVFT',
    '--onefile',
    '--noconsole',
    '--icon=icon.ico',
    f'--add-data={ctk_path};customtkinter',
    '--add-data=icon.png;.',
    '--clean',
])
