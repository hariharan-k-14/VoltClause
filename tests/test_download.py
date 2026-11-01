import csv

from tools import download


class FakeResponse:
    def __init__(self, url, content, content_type="text/html", headers=None):
        self.url = url
        self.content = content
        self.headers = {"Content-Type": content_type, **(headers or {})}
        self.text = content.decode("utf-8", errors="replace")

    def raise_for_status(self):
        return None


def test_downloads_pdf_links_and_skips_them_on_rerun(tmp_path, monkeypatch):
    root = tmp_path
    data_directory = root / "data"
    raw_directory = data_directory / "raw"
    manifest_file = data_directory / "manifest.csv"
    url_file = root / "url.txt"
    url_file.write_text(
        "# source page\nhttps://example.test/regulations/\n", encoding="utf-8"
    )

    monkeypatch.setattr(download, "ROOT_DIRECTORY", root)
    monkeypatch.setattr(download, "DATA_DIRECTORY", data_directory)
    monkeypatch.setattr(download, "RAW_DIRECTORY", raw_directory)
    monkeypatch.setattr(download, "MANIFEST_FILE", manifest_file)
    monkeypatch.setattr(download, "REQUEST_DELAY_SECONDS", 0)
    monkeypatch.setattr(download, "is_allowed_by_robots", lambda url, cache: True)

    page = FakeResponse(
        "https://example.test/regulations/",
        b'<a href="../files/rule.pdf">Download PDF</a>',
    )
    pdf_url = "https://example.test/files/rule.pdf"
    pdf = FakeResponse(pdf_url, b"%PDF-1.7\ncontent", "application/pdf")
    requests_made = []

    def fake_get(url, **kwargs):
        requests_made.append(url)
        return page if url.endswith("/regulations/") else pdf

    monkeypatch.setattr(download.requests, "get", fake_get)

    download.download_pdfs(url_file)

    downloaded_files = list(raw_directory.glob("*.pdf"))
    assert len(downloaded_files) == 1
    assert downloaded_files[0].read_bytes() == pdf.content
    with manifest_file.open(newline="", encoding="utf-8") as manifest:
        rows = list(csv.DictReader(manifest))
    assert len(rows) == 1
    assert rows[0]["source_url"] == pdf_url
    assert requests_made == ["https://example.test/regulations/", pdf_url]

    requests_made.clear()
    download.download_pdfs(url_file)

    assert requests_made == ["https://example.test/regulations/"]
    assert len(list(raw_directory.glob("*.pdf"))) == 1


def test_downloads_direct_pdf_url(tmp_path, monkeypatch):
    url_file = tmp_path / "url.txt"
    url_file.write_text("https://example.test/files/rule.pdf\n", encoding="utf-8")
    data_directory = tmp_path / "data"
    monkeypatch.setattr(download, "ROOT_DIRECTORY", tmp_path)
    monkeypatch.setattr(download, "DATA_DIRECTORY", data_directory)
    monkeypatch.setattr(download, "RAW_DIRECTORY", data_directory / "raw")
    monkeypatch.setattr(download, "MANIFEST_FILE", data_directory / "manifest.csv")
    monkeypatch.setattr(download, "REQUEST_DELAY_SECONDS", 0)
    monkeypatch.setattr(download, "is_allowed_by_robots", lambda url, cache: True)
    pdf = FakeResponse(
        "https://example.test/files/rule.pdf", b"%PDF-1.7\ncontent", "application/pdf"
    )
    monkeypatch.setattr(download.requests, "get", lambda url, **kwargs: pdf)

    download.download_pdfs(url_file)

    assert (data_directory / "raw" / "rule.pdf").read_bytes() == pdf.content


def test_downloads_all_documents_on_regulation_category_pages(
    tmp_path, monkeypatch
):
    url_file = tmp_path / "url.txt"
    start_url = "https://example.test/regulations/"
    category_url = "https://example.test/regulations-category/category-id"
    url_file.write_text(f"{start_url}\n", encoding="utf-8")
    data_directory = tmp_path / "data"
    monkeypatch.setattr(download, "ROOT_DIRECTORY", tmp_path)
    monkeypatch.setattr(download, "DATA_DIRECTORY", data_directory)
    monkeypatch.setattr(download, "RAW_DIRECTORY", data_directory / "raw")
    monkeypatch.setattr(download, "MANIFEST_FILE", data_directory / "manifest.csv")
    monkeypatch.setattr(download, "REQUEST_DELAY_SECONDS", 0)
    monkeypatch.setattr(download, "is_allowed_by_robots", lambda url, cache: True)

    page = FakeResponse(
        start_url,
        (
            b'<a href="/api/download/one">First</a>'
            b'<a href="/api/download/two">Second</a>'
            b'<a href="/regulations-category/category-id">Category</a>'
        ),
    )
    category = FakeResponse(
        category_url, b'<a href="/api/download/three">Third</a>'
    )
    document_responses = {
        "https://example.test/api/download/one": FakeResponse(
            "https://example.test/api/download/one",
            b"%PDF-1.7\nfirst",
            "application/octet-stream",
            {"Content-Disposition": 'attachment; filename="first.pdf"'},
        ),
        "https://example.test/api/download/two": FakeResponse(
            "https://example.test/api/download/two",
            b"%PDF-1.7\nsecond",
            "application/octet-stream",
            {"Content-Disposition": 'attachment; filename="second.pdf"'},
        ),
        "https://example.test/api/download/three": FakeResponse(
            "https://example.test/api/download/three",
            b"%PDF-1.7\nthird",
            "application/octet-stream",
            {"Content-Disposition": 'attachment; filename="third.pdf"'},
        ),
    }
    requests_made = []

    def fake_get(url, **kwargs):
        requests_made.append(url)
        if url == start_url:
            return page
        if url == category_url:
            return category
        return document_responses[url]

    monkeypatch.setattr(download.requests, "get", fake_get)

    download.download_pdfs(url_file)

    assert sorted(path.name for path in (data_directory / "raw").glob("*.pdf")) == [
        "first.pdf",
        "second.pdf",
        "third.pdf",
    ]
    assert len(requests_made) == 5
