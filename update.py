import requests, zipfile, os, sys, shutil, traceback
from io import BytesIO

root_dir = os.path.dirname(os.path.abspath(__file__))
__version__ = "v2.6.6b1"

GITHUB_API_URL = "https://api.github.com/repos/ChocoMeow/Vocard/releases/latest"
VOCARD_URL = "https://github.com/ChocoMeow/Vocard/archive/"
IGNORE_FILES = ["settings.json", ".env"]

def check_version(with_msg=False):
    """Check for the latest version of the project.

    Args:
        with_msg (bool): option to print the message.

    Returns:
        str: the latest version.
    """
    response = requests.get(GITHUB_API_URL)
    latest_version = response.json().get("name", __version__)
    if with_msg:
        msg = f"Your bot is up-to-date! - {latest_version}" if latest_version == __version__ else \
            f"Your bot is not up-to-date! The latest version is {latest_version} and you are currently running version {__version__}\n. Run `python update.py --start` to update your bot!"
        print(msg)
    return latest_version

def download_file(version=None):
    """Download the latest version of the project.

    Args:
        version (str): the version to download. If None, download the latest version.

    Returns:
        BytesIO: the downloaded zip file.
    """
    version = version if version else check_version()
    print(f"Downloading Vocard version: {version}")
    response = requests.get(VOCARD_URL + version + ".zip")
    print("Download Completed")
    return response

def install(response, version):
    """Install the downloaded version of the project.

    Args:
        response (BytesIO): the downloaded zip file.
        version (str): the version to install.
    """
    print("Installing ...")
    zfile = zipfile.ZipFile(BytesIO(response.content))
    zfile.extractall(root_dir)

    version = version.replace("v", "")
    source_dir = os.path.join(root_dir, f"Vocard-{version}")
    if os.path.exists(source_dir):
        for filename in os.listdir(root_dir):
            if filename in IGNORE_FILES + [f"Vocard-{version}"]:
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
    """Start the update process."""
    try:
        response = download_file()
        version = check_version()
        install(response, version)
        print("Update Successfully! Run `python main.py` to start your bot")
    except Exception as e:
        print(traceback.format_exc())

if "--start" in sys.argv:
    start()

if "--check" in sys.argv:
    check_version(with_msg=True)