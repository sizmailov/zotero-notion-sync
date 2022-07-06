from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
from notion_client import Client
from pyzotero.zotero import Zotero

from zotero_notion_sync.config import Config

TITLE = "Title"
AUTHORS = "Authors"
LINK = "Link"
PUBLISHED_AT = "Published at"
ZOTERO_URL = "Zotero URL"
ZOTERO_ITEM_ID = "Zotero ItemID"


@dataclass
class Paper:
    title: str
    authors: str
    link: Optional[str]
    published_at: Optional[str]
    zotero_url: str
    zotero_item_id: str
    notion_id: Optional[str]

    @property
    def notion_url(self) -> Optional[str]:
        if self.notion_id:
            return f"https://notion.so/{self.notion_id.replace('-', '')}"

    def zotero_eq(self, other: Paper) -> bool:
        return (
            self.title == other.title
            and self.authors == other.authors
            and self.link == other.link
            and self.published_at == other.published_at
            and self.zotero_url == other.zotero_url
            and self.zotero_item_id == other.zotero_item_id
        )


def notion_object_to_str(obj: dict):
    type_ = obj["type"]
    if type_ == "title":
        return "".join(notion_object_to_str(x) for x in obj["title"])
    if type_ == "text":
        return obj["text"]["content"]
    if type_ == "rich_text":
        return "".join(notion_object_to_str(x) for x in obj["rich_text"])
    if type_ == "select":
        return obj["select"]["name"]
    if type_ == "multi_select":
        return ", ".join(notion_object_to_str(x) for x in obj["multi_select"])
    if type_ == "date":
        date_ = obj["date"]
        if date_:
            return date_["start"]
        else:
            return ""
    if type_ == "url":
        return obj["url"]
    raise RuntimeError(f"Unexpected `{type_}` type")


def notion_page_to_paper(page: dict) -> Paper:
    assert page["object"] == "page"
    props = page["properties"]
    return Paper(
        title=notion_object_to_str(props[TITLE]),
        authors=notion_object_to_str(props[AUTHORS]),
        published_at=notion_object_to_str(props[PUBLISHED_AT]) or None,
        zotero_url=notion_object_to_str(props[ZOTERO_URL]),
        zotero_item_id=notion_object_to_str(props[ZOTERO_ITEM_ID]),
        link=notion_object_to_str(props[LINK]),
        notion_id=page["id"].replace("-", ""),
    )


def truncate_text(text: str, limit: int = 2000) -> str:
    """Notion imposes limit on rich text length"""
    if len(text) <= limit:
        return text
    logging.warning(f"Text truncated to {limit} symbols: `{text[:16]}...`")
    return text[: limit - 3] + "..."


def to_rich_text_dict(text: str):
    return {
        "type": "rich_text",
        "rich_text": [
            {
                "type": "text",
                "text": {"content": truncate_text(text)},
            },
        ],
    }


def create_notion_page(notion: Client, db_id: str, paper: Paper) -> Paper:
    return notion_page_to_paper(
        notion.pages.create(
            parent={"database_id": db_id}, properties=paper_to_notion_properties(paper)
        )
    )


def update_notion_page(notion: Client, paper: Paper) -> Paper:
    return notion_page_to_paper(
        notion.pages.update(
            page_id=paper.notion_id, properties=paper_to_notion_properties(paper)
        )
    )


def paper_to_notion_properties(paper):
    properties = {
        TITLE: {"title": [{"text": {"content": paper.title}}]},
        AUTHORS: to_rich_text_dict(paper.authors),
        ZOTERO_URL: {"url": paper.zotero_url},
        ZOTERO_ITEM_ID: to_rich_text_dict(paper.zotero_item_id),
    }
    if paper.link:
        properties[LINK] = {"url": paper.link}
    if paper.published_at:
        properties[PUBLISHED_AT] = {"date": {"start": str(paper.published_at)}}
    return properties


def get_all_pages(notion: Client, db_id: str) -> list:
    result = notion.databases.query(db_id)
    pages = result["results"]
    next_cursor = result.get("next_cursor")

    while next_cursor is not None:
        result = notion.databases.query(db_id, start_cursor=next_cursor)
        pages.extend(result["results"])
        next_cursor = result.get("next_cursor")
    return pages


def zotero_item_to_url(item: dict) -> str:
    key = item["key"]
    group_id = item["library"]["id"]
    return f"https://open-zotero.xyz/select/groups/{group_id}/items/{key}"


def zotero_author_to_str(author: dict) -> str:
    if "name" in author:
        return author["name"]
    return author["firstName"] + " " + author["lastName"]


def zotero_to_datetime_str(dt: str) -> Optional[str]:
    t = pd.to_datetime(dt)
    if not pd.isnull(t):
        return str(t.date())


def zotero_item_to_paper(item: dict) -> Optional[Paper]:
    data = item["data"]
    key = item["key"]
    return Paper(
        title=data["title"],
        zotero_item_id=key,
        zotero_url=zotero_item_to_url(item),
        authors=", ".join(
            zotero_author_to_str(author)
            for author in data["creators"]
            if author["creatorType"] == "author"
        ),
        published_at=zotero_to_datetime_str(data["date"]),
        link=data["url"],
        notion_id=None,
    )


def find_notion_note(children: list) -> Optional[dict]:
    for child in children:
        if (
            child["data"]["itemType"] == "note"
            and [{"tag": "notion-link"}] == child["data"]["tags"]
        ):
            return child


def update_zotero_notion_note(paper: Paper, zotero: Zotero):
    note = find_notion_note(children=zotero.children(paper.zotero_item_id))
    if note is None:
        note = zotero.item_template("note")
        note["tags"] = [{"tag": "notion-link"}]
        note["note"] = f'<a href="{paper.notion_url}">Notion</a>'
        zotero.create_items([note], parentid=paper.zotero_item_id)
    else:
        note = note["data"]
        note["note"] = f'<a href="{paper.notion_url}">Notion</a>'
        zotero.update_item(note)


_re_notion_link = re.compile("https://notion.so/([a-z0-9-]+)")


def find_notion_id(text: str):
    m = _re_notion_link.search(text)
    if m:
        return m.group(1)


def get_all_zotero_papers(zotero: Zotero) -> List[Paper]:
    all_notes = zotero.everything(zotero.items(itemType="note"))

    top_papers = {
        item["data"]["key"]: zotero_item_to_paper(item) for item in zotero.all_top()
    }

    for item in all_notes:
        if [{"tag": "notion-link"}] == item["data"]["tags"]:
            parent_item_id = item["data"]["parentItem"]
            if parent_item_id in top_papers:
                top_papers[parent_item_id].notion_id = find_notion_id(
                    item["data"]["note"]
                )

    return list(top_papers.values())


def synchronize(zotero: Zotero, notion: Client, database_id: str):
    notion_papers = [
        notion_page_to_paper(page) for page in get_all_pages(notion, database_id)
    ]
    zotero_papers = get_all_zotero_papers(zotero)

    by_zotero_id: Dict[str, Paper] = {p.zotero_item_id: p for p in notion_papers}

    logging.info(f"Found {len(zotero_papers):3} Zotero item(s)")
    logging.info(f"Found {len(notion_papers):3} Notion item(s)")

    for paper in zotero_papers:
        notion_paper = by_zotero_id.get(paper.zotero_item_id)
        if notion_paper is None:
            logging.info(f"Create notion page: {paper.zotero_item_id}...")
            notion_paper = create_notion_page(notion, db_id=database_id, paper=paper)
            logging.info(f"Update zotero note: {paper.zotero_item_id}...")
            update_zotero_notion_note(notion_paper, zotero)
        elif paper != notion_paper:
            if not paper.zotero_eq(notion_paper):
                logging.info(f"Update notion page: {paper.zotero_item_id}...")
                notion_paper = update_notion_page(notion, paper=paper)
            if paper.notion_id != notion_paper.notion_id:
                logging.info(f"Update zotero note: {paper.zotero_item_id}...")
                update_zotero_notion_note(notion_paper, zotero)
        else:
            logging.info(f"Already in sync: {paper.zotero_item_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Sync Notion database with Zotero library"
    )

    parser.add_argument("--config", type=str, required=True, help="Path to config")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level)

    config: Config = Config.read_config(args.config)

    notion = Client(auth=config.notion.token)
    zotero = Zotero(config.zotero.group_id, "group", config.zotero.token)

    synchronize(zotero, notion, database_id=config.notion.database_id)


if __name__ == "__main__":
    main()
