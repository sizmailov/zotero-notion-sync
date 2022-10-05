# Zotero ↔ Notion

Synchronize Zotero with Notion via public APIs.

Here is the assumed workflow:

1. Add a paper to Zotero
2. Wait for synchronization
3. Go to corresponding Notion page and annotate paper

At synchronization `sync-zotero-notion`:
- Creates new items in Notion database
- Creates Zotero note with link to corresponding Notion page
- Updates Zotero fields in Notion database


👨‍🎓📗 Notion fields — Columns in Notion database that SHOULD BE edited manually.

🤖📕 Zotero fields — Columns in Notion database that MUST NOT be edited by users. Those columns are continuously overwritten with values from Zotero.

## How to

### Setup
#### Notion
1. Create Notion database with `Title`, `Authors`, `Link`, `Published at`, `Zotero 🖥️`, `Zotero 🌐`, `Zotero ItemID` fields.
2. Create [integration token](https://www.notion.so/my-integrations/) with read/write permissions
3. Share database with integration (from top-right conner of database page):
![Share database with integration](images/share-with-integration.png)
#### Zotero
1. Create [new group](https://www.zotero.org/groups/new)
2. Create [API token](https://www.zotero.org/settings/keys) with read/write permissions

### Sync

1. Create `config.yml` and fill with values obtained earlier
```yaml
notion:
  token: "<...>"
  database_id: "<...>"

zotero:
  token: "<...>"
  group_id: 123456789

```

2. Install `zotero-notion-sync`
```bash
pip install git+https://github.com/sizmailov/zotero-notion-sync.git
```

3. Synchronize
```bash
sync-zotero-notion --config=./config.yml
```

## Development

### Set up environment and install dependencies

```bash
python3.9 -m venv venv
source venv/bin/activate
pip install -U pip wheel setuptools
pip install pip-tools
pip-sync requirements-dev.txt
pre-commit install
```

### Run linters

```bash
# Pre-commit hooks
pre-commit run --all-files
```

### Integration with systemd


1. Create two files `sync-zotero-notion.*` in `/etc/systemd/system/` using template below.
2. Activate sync via

```bash
sudo systemctl start sync-zotero-notion.timer
sudo systemctl enable sync-zotero-notion.timer
```

<details><summary><code>sync-zotero-notion.service</code></summary>

```
# TODO: replace `<USERNAME>` with actual user name
[Unit]
Description=Sync Notion with Zotero
After=network.target network-online.target

[Service]
User=<USERNAME>
Group=<USERNAME>
Type=simple
ExecStart=/home/<USERNAME>/venv/bin/sync-zotero-notion --config=/home/<USERNAME>/config.yml
```


</details>


<details><summary><code>sync-zotero-notion.timer</code></summary>

```
[Unit]
Description=Sync Notion with Zotero

[Timer]
OnUnitInactiveSec=1m
OnBootSec=2m

[Install]
WantedBy=timers.target
```

</details>
