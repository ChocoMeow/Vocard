import os

# Branding replacements embedded directly
replacements = [
    {"from": "ChocoMeow/Vocard", "to": "Nischay876/MeCute"},
    {"from": "chocomeow/vocard", "to": "nischay876/mecute"},
    {"from": "Vocard", "to": "MeCute"},
    {"from": "vocard.xyz", "to": "mecute.bot.nu"},
    {"from": "wRCgB7vBQv", "to": "wRCgB7vBRS"},
    {"from": "https://ko-fi.com/chocoo", "to": "https://ko-fi.com/mecute"},
    {"from": "https://www.patreon.com/Vocard", "to": "https://www.patreon.com/mecute"},
    {"from": "https://www.termsfeed.com/live/4322db80-d6f4-4cd0-9aaf-73080323ff01", "to": "https://mecute.bot.nu/legal/pp"},
    {"from": "https://www.termsfeed.com/live/4d3977eb-65b6-4ce2-a446-1cd80e619ab0", "to": "https://mecute.bot.nu/legal/tos"}
]

# Directories to ignore during replacements
ignore_dirs = {".git", "node_modules", ".github", "__pycache__"}

# Script file itself should not be edited
self_file = os.path.basename(__file__)

def replace_in_file(file_path, replacements):
    """Replace all occurrences from embedded replacements in a single file"""
    if os.path.basename(file_path) == self_file:
        # Skip editing this script itself
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Skipping {file_path}: {e}")
        return

    for r in replacements:
        content = content.replace(r["from"], r["to"])

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"Failed to write {file_path}: {e}")

# Walk through all files recursively
for root, dirs, files in os.walk("."):
    # Skip ignored directories
    dirs[:] = [d for d in dirs if d not in ignore_dirs]

    for file in files:
        # Only process certain file types
        if file.endswith((".py", ".js", ".ts", ".json", ".md", ".yml", ".yaml", ".html", ".txt")):
            file_path = os.path.join(root, file)
            replace_in_file(file_path, replacements)

print("Branding replacement completed successfully!")
