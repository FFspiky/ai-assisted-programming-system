import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
PAGES = {
    "官网通知": "https://www.cmit.cn/wap/tongzhigonggao/show-144-45826-1.html",
    "电脑版提交流程": "https://www.cmit.cn/wap/liucheng/show-277-45689-1.html",
    "手机版提交流程": "https://www.cmit.cn/wap/liucheng/show-277-45691-1.html",
    "院校联系人通知": "https://www.cmit.cn/wap/tongzhigonggao/show-144-45827-1.html",
    "公告列表": "https://www.cmit.cn/wap/tongzhigonggao/list-144-1.html",
    "历史2025年问答_不作为2026确定规则": "https://www.cmit.cn/wap/tongzhigonggao/show-144-45766-1.html",
}


def fetch_page(item):
    name, url = item
    response = requests.get(url, timeout=40)
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    links = [
        {"text": a.get_text(" ", strip=True), "url": urljoin(url, a["href"])}
        for a in soup.select("a[href]")
    ]
    (OUT / (name + ".txt")).write_text(
        "来源："
        + url
        + "\n核对日期：2026-09-26\n\n"
        + soup.get_text("\n", strip=True)
        + "\n\n链接：\n"
        + json.dumps(links, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return name, links


if __name__ == "__main__":
    results = dict(ThreadPoolExecutor(6).map(fetch_page, PAGES.items()))
    records = []
    for link in results["官网通知"]:
        if not link["url"].lower().endswith(".pdf"):
            continue
        r = requests.get(link["url"], timeout=40)
        r.raise_for_status()
        name = unquote(link["url"].split("/")[-1])
        local = ROOT / name
        digest = hashlib.sha256(r.content).hexdigest()
        match = local.exists() and hashlib.sha256(local.read_bytes()).hexdigest() == digest
        records.append(
            {
                "name": name,
                "url": link["url"],
                "bytes": len(r.content),
                "sha256": digest,
                "matches_local": match,
            }
        )
        if not match:
            (OUT / ("官网当前_" + name)).write_bytes(r.content)
    (OUT / "官网附件核对.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(records, ensure_ascii=False, indent=2))
