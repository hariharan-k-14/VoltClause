"""Download PDF documents linked from the URLs in a text file."""

import argparse
import csv
import email.message
import hashlib
import re
import sys
import time
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

ROOT_DIRECTORY = Path(__file__).resolve().parents[1]
URL_LIST_FILE = Path(__file__).resolve().with_name("urls.txt")
DATA_DIRECTORY = ROOT_DIRECTORY / "data"
RAW_DIRECTORY = DATA_DIRECTORY / "raw"
MANIFEST_FILE = DATA_DIRECTORY / "manifest.csv"
USER_AGENT = "VoltClausePDFDownloader/1.0 (educational document downloader)"
HEADERS = {"User-Agent": USER_AGENT}
REQUEST_DELAY_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 30


class PDFLinkParser(HTMLParser):
    """Collect document downloads and regulation category pages."""

    def __init__(self):
        super().__init__()
        self.links = []
        self.category_links = []
        self._current_href = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._current_href = dict(attrs).get("href")
            self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._current_href is not None:
            label = " ".join(self._current_text).lower()
            path = urlparse(self._current_href).path.lower()
            if path.lower().endswith(".pdf") or "pdf" in label or "/download/" in path:
                self.links.append(self._current_href)
            if "/regulations-category/" in path:
                self.category_links.append(self._current_href)
            self._current_href = None
            self._current_text = []


def read_urls(list_file):
    """Read non-empty, non-comment URLs from a text file."""
    with Path(list_file).open(encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip() and not line.lstrip().startswith("#")]


def is_allowed_by_robots(url, robots_cache):
    """Check robots.txt, allowing access with a warning if it cannot be read."""
    parsed_url = urlparse(url)
    site_root = f"{parsed_url.scheme}://{parsed_url.netloc}"
    if site_root not in robots_cache:
        parser = RobotFileParser(f"{site_root}/robots.txt")
        try:
            parser.read()
        except (OSError, URLError) as error:
            print(
                f"Warning: could not read robots.txt for {site_root}: {error}",
                file=sys.stderr,
            )
            parser = None
        robots_cache[site_root] = parser

    parser = robots_cache[site_root]
    return parser is None or parser.can_fetch(USER_AGENT, url)


def document_extension(response):
    content = response.content
    if content.lstrip().startswith(b"%PDF-"):
        return ".pdf"

    disposition = email.message.Message()
    disposition["content-disposition"] = response.headers.get("Content-Disposition", "")
    filename = disposition.get_filename() or urlparse(response.url).path.rsplit("/", 1)[-1]
    extension = Path(unquote(filename)).suffix.lower()
    if extension == ".docx" and content.startswith(b"PK\x03\x04"):
        return extension
    if extension == ".doc" and content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return extension
    return None


def is_document_response(response):
    content_type = response.headers.get("Content-Type", "").lower()
    return document_extension(response) is not None or "application/pdf" in content_type


def document_links_from_page(response):
    parser = PDFLinkParser()
    parser.feed(response.text)
    return list(
        dict.fromkeys(
            urljoin(response.url, href)
            for href in parser.links
            if urlparse(urljoin(response.url, href)).scheme in {"http", "https"}
        )
    )


def filename_for(response):
    disposition = email.message.Message()
    disposition["content-disposition"] = response.headers.get("Content-Disposition", "")
    filename = disposition.get_filename()
    if not filename:
        filename = urlparse(response.url).path.rsplit("/", 1)[-1]
    filename = unquote(filename)
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename).strip(" .")
    extension = document_extension(response) or ".pdf"
    if not filename or Path(filename).suffix.lower() not in {".pdf", ".docx", ".doc"}:
        filename = f"document-{hashlib.sha256(response.url.encode()).hexdigest()[:12]}{extension}"
    return filename


def save_document(response, downloaded_urls, manifest_writer):
    content = response.content
    if not is_document_response(response):
        print(f"Skipped unsupported document response: {response.url}", file=sys.stderr)
        return False
    if response.url in downloaded_urls:
        print(f"Skipped (already downloaded): {response.url}")
        return False

    filename = filename_for(response)
    destination = RAW_DIRECTORY / filename
    if destination.exists():
        filename_path = Path(filename)
        suffix = hashlib.sha256(response.url.encode()).hexdigest()[:8]
        destination = RAW_DIRECTORY / f"{filename_path.stem}-{suffix}{filename_path.suffix}"
    if destination.exists():
        print(f"Skipped (already downloaded): {destination}")
        return False

    destination.write_bytes(content)
    manifest_writer.writerow(
        [
            str(destination.relative_to(ROOT_DIRECTORY)),
            response.url,
            date.today().isoformat(),
            len(content),
            hashlib.sha256(content).hexdigest(),
        ]
    )
    downloaded_urls.add(response.url)
    print(f"Saved {destination} ({len(content)} bytes)")
    return True


def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response


def download_pdfs(list_file=URL_LIST_FILE):
    urls = read_urls(list_file)
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RAW_DIRECTORY.mkdir(parents=True, exist_ok=True)
    manifest_exists = MANIFEST_FILE.exists()
    downloaded_urls = set()
    if manifest_exists:
        with MANIFEST_FILE.open(newline="", encoding="utf-8") as existing_manifest:
            downloaded_urls.update(
                row["source_url"] for row in csv.DictReader(existing_manifest) if row.get("source_url")
            )
    robots_cache = {}
    page_queue = list(urls)
    visited_pages = set()

    with MANIFEST_FILE.open("a", newline="", encoding="utf-8") as manifest_file:
        manifest_writer = csv.writer(manifest_file)
        if not manifest_exists:
            manifest_writer.writerow(["file", "source_url", "downloaded_on", "bytes", "sha256"])

        while page_queue:
            source_url = page_queue.pop(0)
            if source_url in visited_pages:
                continue
            visited_pages.add(source_url)
            if urlparse(source_url).scheme not in {"http", "https"}:
                print(f"Skipped invalid URL: {source_url}", file=sys.stderr)
                continue
            if not is_allowed_by_robots(source_url, robots_cache):
                print(f"Blocked by robots.txt: {source_url}", file=sys.stderr)
                continue

            try:
                source_response = fetch(source_url)
            except requests.RequestException as error:
                print(f"Failed to fetch {source_url}: {error}", file=sys.stderr)
                continue

            if is_document_response(source_response):
                save_document(source_response, downloaded_urls, manifest_writer)
                time.sleep(REQUEST_DELAY_SECONDS)
                continue

            parser = PDFLinkParser()
            parser.feed(source_response.text)
            document_urls = list(
                dict.fromkeys(
                    urljoin(source_response.url, href)
                    for href in parser.links
                    if urlparse(urljoin(source_response.url, href)).scheme in {"http", "https"}
                )
            )
            if not document_urls:
                print(f"No document download links found at {source_url}")

            source_origin = (
                urlparse(source_response.url).scheme,
                urlparse(source_response.url).netloc,
            )
            for category_href in parser.category_links:
                category_url = urljoin(source_response.url, category_href)
                parsed_category = urlparse(category_url)
                if (
                    parsed_category.scheme,
                    parsed_category.netloc,
                ) == source_origin and category_url not in visited_pages:
                    page_queue.append(category_url)

            for document_url in document_urls:
                if document_url in downloaded_urls:
                    continue
                if not is_allowed_by_robots(document_url, robots_cache):
                    print(f"Blocked by robots.txt: {document_url}", file=sys.stderr)
                    continue
                try:
                    document_response = fetch(document_url)
                except requests.RequestException as error:
                    print(f"Failed to fetch {document_url}: {error}", file=sys.stderr)
                    continue
                save_document(document_response, downloaded_urls, manifest_writer)
                time.sleep(REQUEST_DELAY_SECONDS)


def main():
    argument_parser = argparse.ArgumentParser(
        description="Download PDFs linked from the configured URL list."
    )
    argument_parser.add_argument(
        "url_file",
        nargs="?",
        type=Path,
        default=URL_LIST_FILE,
        help=f"Text file with one URL per line (default: {URL_LIST_FILE})",
    )
    arguments = argument_parser.parse_args()
    download_pdfs(arguments.url_file)


if __name__ == "__main__":
    main()
