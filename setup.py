from setuptools import setup

with open("requirements.txt") as f:
    required = f.readlines()

setup(
    name="zotero-notion-sync",
    version="0.1.1",
    packages=["zotero_notion_sync"],
    install_requires=required,
    entry_points={
        "console_scripts": [
            "sync-zotero-notion=zotero_notion_sync:main",
        ]
    },
)
