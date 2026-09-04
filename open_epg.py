import gzip
import html
import time
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


SOURCES = [
    "https://www.open-epg.com/files/turkey1.xml.gz",
    "https://www.open-epg.com/files/turkey2.xml.gz",
    "https://www.open-epg.com/files/turkey3.xml.gz",
    "https://www.open-epg.com/files/turkey4.xml.gz",
    "https://www.open-epg.com/files/turkey5.xml.gz",
]

OUTPUT_XML = "epg.xml"
OUTPUT_GZ = "epg.xml.gz"

TIMEOUT = 60
RETRIES = 3


def download(url):
    last_error = None

    for attempt in range(1, RETRIES + 1):
        try:
            print(f"İndiriliyor: {url}")

            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/gzip,application/xml,text/xml,*/*",
                    "Accept-Encoding": "gzip",
                    "Cache-Control": "no-cache",
                },
            )

            with urlopen(request, timeout=TIMEOUT) as response:
                data = response.read()

            if not data:
                raise RuntimeError("Boş dosya geldi.")

            return data

        except Exception as exc:
            last_error = exc

            print(
                f"Hata ({attempt}/{RETRIES}): {exc}"
            )

            if attempt < RETRIES:
                time.sleep(3)

    raise RuntimeError(
        f"İndirme başarısız: {url} -> {last_error}"
    )


def get_text(element):
    if element is None:
        return ""

    return "".join(
        element.itertext()
    ).strip()


def parse_source(data, source_name):
    try:
        try:
            xml_data = gzip.decompress(data)
        except gzip.BadGzipFile:
            xml_data = data

        root = ET.fromstring(xml_data)

        channels = {}
        programmes = []

        for channel in root.findall("channel"):
            channel_id = channel.get("id")

            if not channel_id:
                continue

            display_name = ""

            for item in channel.findall("display-name"):
                text = get_text(item)

                if text:
                    display_name = text
                    break

            if not display_name:
                display_name = channel_id

            channels[channel_id] = {
                "id": channel_id,
                "name": display_name,
            }

        for programme in root.findall("programme"):
            channel_id = programme.get("channel")
            start = programme.get("start")
            stop = programme.get("stop")

            if not channel_id:
                continue

            if not start or not stop:
                continue

            title_element = programme.find("title")

            if title_element is None:
                continue

            title = get_text(title_element)

            if not title:
                continue

            programmes.append(
                (
                    channel_id,
                    start,
                    stop,
                    title,
                )
            )

        print(
            f"{source_name}: "
            f"{len(channels)} kanal, "
            f"{len(programmes)} program"
        )

        return channels, programmes

    except Exception as exc:
        raise RuntimeError(
            f"{source_name} okunamadı: {exc}"
        )


def merge_data(
    all_channels,
    all_programmes,
):
    merged_channels = {}
    merged_programmes = {}

    for source_channels in all_channels:
        for channel_id, channel in source_channels.items():

            if channel_id not in merged_channels:
                merged_channels[channel_id] = {
                    "id": channel_id,
                    "name": channel["name"],
                }

    for source_programmes in all_programmes:
        for (
            channel_id,
            start,
            stop,
            title,
        ) in source_programmes:

            key = (
                channel_id,
                start,
                stop,
                title,
            )

            if key not in merged_programmes:
                merged_programmes[key] = {
                    "channel": channel_id,
                    "start": start,
                    "stop": stop,
                    "title": title,
                }

    programmes = list(
        merged_programmes.values()
    )

    return (
        list(merged_channels.values()),
        programmes,
    )


def build_xml(
    channels,
    programmes,
):
    root = ET.Element(
        "tv",
        {
            "generator-info-name": "Open-EPG Turkey",
            "generator-info-url": "https://www.open-epg.com/",
        },
    )

    for channel in channels:
        channel_element = ET.SubElement(
            root,
            "channel",
            {
                "id": channel["id"],
            },
        )

        display = ET.SubElement(
            channel_element,
            "display-name",
            {
                "lang": "tr",
            },
        )

        display.text = channel["name"]

    programmes = sorted(
        programmes,
        key=lambda item: (
            item["start"],
            item["channel"],
            item["stop"],
            item["title"],
        ),
    )

    for programme in programmes:
        element = ET.SubElement(
            root,
            "programme",
            {
                "channel": programme["channel"],
                "start": programme["start"],
                "stop": programme["stop"],
            },
        )

        title = ET.SubElement(
            element,
            "title",
            {
                "lang": "tr",
            },
        )

        title.text = programme["title"]

    ET.indent(
        root,
        space="  ",
    )

    tree = ET.ElementTree(root)

    tree.write(
        OUTPUT_XML,
        encoding="utf-8",
        xml_declaration=True,
    )


def create_gzip():
    with open(
        OUTPUT_XML,
        "rb",
    ) as source:

        with gzip.open(
            OUTPUT_GZ,
            "wb",
            compresslevel=9,
        ) as target:

            while True:
                chunk = source.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                target.write(chunk)


def main():
    print()
    print("=" * 70)
    print("OPEN-EPG TURKEY - HAFİF EPG")
    print("=" * 70)
    print()

    all_channels = []
    all_programmes = []

    for index, url in enumerate(
        SOURCES,
        start=1,
    ):
        source_name = f"Turkey {index}"

        data = download(
            url
        )

        channels, programmes = parse_source(
            data,
            source_name,
        )

        all_channels.append(
            channels
        )

        all_programmes.append(
            programmes
        )

    print()
    print("Kaynaklar birleştiriliyor...")

    channels, programmes = merge_data(
        all_channels,
        all_programmes,
    )

    if not channels:
        raise RuntimeError(
            "Hiç kanal bulunamadı."
        )

    if not programmes:
        raise RuntimeError(
            "Hiç program bulunamadı."
        )

    print(
        f"Toplam kanal   : {len(channels)}"
    )

    print(
        f"Toplam program  : {len(programmes)}"
    )

    print()
    print("Hafif XML oluşturuluyor...")

    build_xml(
        channels,
        programmes,
    )

    create_gzip()

    xml_size = Path(
        OUTPUT_XML
    ).stat().st_size

    gz_size = Path(
        OUTPUT_GZ
    ).stat().st_size

    print()
    print("=" * 70)
    print("TAMAMLANDI")
    print("=" * 70)
    print(
        f"XML   : {xml_size / 1024 / 1024:.2f} MB"
    )
    print(
        f"GZIP  : {gz_size / 1024 / 1024:.2f} MB"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
