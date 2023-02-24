import requests, zipfile, os, sys, shutil, traceback
from io import BytesIO

root_dir = os.path.dirname(os.path.abspath(__file__))
install_pack_dir = os.path.join(root_dir, "Vocard.zip")
__version__ = "v2.5.6"

def checkVersion(withMsg = False):
    resp = requests.get("https://api.github.com/repos/ChocoMeow/Vocard/releases/latest")
    version = resp.json().get("name", __version__)
    if withMsg:
        if version == __version__:
            print(f"Your bot is up-to-date! - {version}")
        else:
            print(f"Your bot is not up-to-date! This latest version is {version} and you are currently running version {__version__}\n. Run `python update.py --start` to update your bot!")
    return version
    
def downloadFile(version:str = None):
    if not version:
        version = checkVersion()
    print("Downloading Vocard version: " + version)
    response = requests.get("https://github.com/ChocoMeow/Vocard/archive/" + version + ".zip")
    print("Download Completed")
    unZip(response, version)

def unZip(response, version: str):
    print("Installing ...")
    zfile = zipfile.ZipFile(BytesIO(response.content))
    zfile.extractall(root_dir)

    version = version.replace("v", "")
    source_dir = os.path.join(root_dir, f"Vocard-{version}")
    if os.path.exists(source_dir):
        for filename in os.listdir(root_dir):
            if filename in ["settings.json", ".env", f"Vocard-{version}"]:
                continue
            filename = os.path.join(root_dir, filename)
            if os.path.isdir(filename):
                shutil.rmtree(filename)
            else:
                os.remove(filename)
        for filename in os.listdir(source_dir):
            shutil.move(os.path.join(source_dir, filename), os.path.join(root_dir, filename))
        os.rmdir(source_dir)

def start():
    try:
        downloadFile()
        if os.path.exists(install_pack_dir):
            os.remove(install_pack_dir)
        print("Update Successfully! Run `python main.py` to start your bot")
    except Exception as e:
        print(traceback.format_exc())

if "--start" in sys.argv:
    start()

if "--check" in sys.argv:
    checkVersion(withMsg = True)