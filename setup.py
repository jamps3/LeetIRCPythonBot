import os
import subprocess
import sys

from setuptools import setup
from setuptools.command.install import install


class CustomInstall(install):
    def run(self):
        # Run the normal install process
        install.run(self)

        # Step 1: Install dependencies from requirements.txt
        req_file = "requirements.txt"
        if os.path.exists(req_file):
            print(f"\nInstalling dependencies from {req_file}...\n")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", req_file]
            )
        else:
            print(f"\n{req_file} not found — skipping dependency installation.\n")

        # Step 2: Install the Playwright Firefox browser
        print("\nInstalling Playwright Firefox browser...\n")
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "firefox"]
        )


setup(
    name="my_app",
    version="0.1.0",
    packages=[
        "voikko",
        "services",
        "word_tracking",
    ],  # Excplicitly list packages, required
    install_requires=[],
    cmdclass={
        "install": CustomInstall,
    },
)
