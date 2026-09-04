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

OUTPUT_FILE = "epg.xml"
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
                },
            )

            with urlopen(request, timeout=TIMEOUT) as response:
                data = response.read()

            if not data:
                raise RuntimeError("Boş dosya geldi.")

            return data

        except Exception as e:
            last_error = e
            print(
                f"Hata ({attempt}/{RETRIES}): {e}"
            )

            if attempt < RETRIES:
                time.sleep(3)

    raise RuntimeError(
        f"İndirme başarısız: {url} -> {last_error}"
    )


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

            display_names = []

            for item in channel.findall("display-name"):
                text = "".join(item.itertext()).strip()

                if text:
                    display_names.append(text)

            icon = channel.find("icon")
            icon_src = ""

            if icon is not None:
                icon_src = icon.get("src", "")

            channels[channel_id] = {
                "id": channel_id,
                "names": display_names,
                "icon": icon_src,
            }

        for programme in root.findall("programme"):
            channel_id = programme.get("channel")

            start = programme.get("start")
            stop = programme.get("stop")

            if not channel_id or not start or not stop:
                continue

            title_element = programme.find("title")

            if title_element is None:
                continue

            title = "".join(
                title_element.itertext()
            ).strip()

            if not title:
                continue

            programmes.append(
                {
                    "channel": channel_id,
                    "start": start,
                    "stop": stop,
                    "title": title,
                    "desc": get_element_text(
                        programme,
                        "desc"
                    ),
                    "category": get_element_text(
                        programme,
                        "category"
                    ),
                    "sub-title": get_element_text(
                        programme,
                        "sub-title"
                    ),
                }
            )

        print(
            f"{source_name}: "
            f"{len(channels)} kanal, "
            f"{len(programmes)} program"
        )

        return channels, programmes

    except Exception as e:
        raise RuntimeError(
            f"{source_name} XML okunamadı: {e}"
        )


def get_element_text(parent, tag):
    element = parent.find(tag)

    if element is None:
        return ""

    return "".join(
        element.itertext()
    ).strip()


def merge_data(all_channels, all_programmes):
    merged_channels = {}
    merged_programmes = {}

    for source_channels in all_channels:
        for channel_id, channel in source_channels.items():

            if channel_id not in merged_channels:
                merged_channels[channel_id] = {
                    "id": channel_id,
                    "names": [],
                    "icon": channel.get(
                        "icon",
                        ""
                    ),
                }

            existing = merged_channels[channel_id]

            for name in channel.get(
                "names",
                []
            ):
                if (
                    name
                    and name not in existing["names"]
                ):
                    existing["names"].append(
                        name
                    )

            if (
                not existing["icon"]
                and channel.get("icon")
            ):
                existing["icon"] = channel[
                    "icon"
                ]

    for source_programmes in all_programmes:
        for programme in source_programmes:

            key = (
                programme["channel"],
                programme["start"],
                programme["stop"],
                programme["title"],
            )

            if key not in merged_programmes:
                merged_programmes[key] = programme

    return (
        list(merged_channels.values()),
        list(merged_programmes.values()),
    )


def write_xml(
    channels,
    programmes
):
    tv = ET.Element(
        "tv",
        {
            "generator-info-name": (
                "Open-EPG Turkey Birleştirici"
            ),
            "generator-info-url": (
                "https://www.open-epg.com/"
            ),
        },
    )

    for channel in channels:
        channel_element = ET.SubElement(
            tv,
            "channel",
            {
                "id": channel["id"]
            },
        )

        names = channel.get(
            "names",
            []
        )

        if not names:
            names = [
                channel["id"]
            ]

        for name in names:
            display = ET.SubElement(
                channel_element,
                "display-name",
                {
                    "lang": "tr"
                },
            )

            display.text = name

        icon = channel.get(
            "icon",
            ""
        )

        if icon:
            ET.SubElement(
                channel_element,
                "icon",
                {
                    "src": icon
                },
            )

    programmes = sorted(
        programmes,
        key=lambda p: (
            p["start"],
            p["channel"],
            p["stop"],
            p["title"],
        ),
    )

    for programme in programmes:
        programme_element = ET.SubElement(
            tv,
            "programme",
            {
                "channel": programme["channel"],
                "start": programme["start"],
                "stop": programme["stop"],
            },
        )

        title = ET.SubElement(
            programme_element,
            "title",
            {
                "lang": "tr"
            },
        )

        title.text = programme["title"]

        subtitle = programme.get(
            "sub-title",
            ""
        )

        if subtitle:
            element = ET.SubElement(
                programme_element,
                "sub-title",
                {
                    "lang": "tr"
                },
            )

            element.text = subtitle

        desc = programme.get(
            "desc",
            ""
        )

        if desc:
            element = ET.SubElement(
                programme_element,
                "desc",
                {
                    "lang": "tr"
                },
            )

            element.text = desc

        category = programme.get(
            "category",
            ""
        )

        if category:
            element = ET.SubElement(
                programme_element,
                "category",
                {
                    "lang": "tr"
                },
            )

            element.text = category

    tree = ET.ElementTree(tv)

    ET.indent(
        tree,
        space="  "
    )

    tree.write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )


def main():
    print()
    print("=" * 70)
    print("OPEN-EPG TURKEY BİRLEŞTİRİCİ")
    print("=" * 70)
    print()

    all_channels = []
    all_programmes = []

    for index, url in enumerate(
        SOURCES,
        start=1
    ):
        source_name = (
            f"Turkey {index}"
        )

        data = download(url)

        channels, programmes = parse_source(
            data,
            source_name
        )

        all_channels.append(
            channels
        )

        all_programmes.append(
            programmes
        )

    print()
    print(
        "5 kaynak birleştiriliyor..."
    )

    channels, programmes = merge_data(
        all_channels,
        all_programmes
    )

    print(
        f"Birleşik kanal sayısı : {len(channels)}"
    )

    print(
        f"Birleşik program sayısı: {len(programmes)}"
    )

    if not channels:
        raise RuntimeError(
            "Hiç kanal bulunamadı."
        )

    if not programmes:
        raise RuntimeError(
            "Hiç program bulunamadı."
        )

    write_xml(
        channels,
        programmes
    )

    file_size = Path(
        OUTPUT_FILE
    ).stat().st_size

    print()
    print("=" * 70)
    print("TAMAMLANDI")
    print("=" * 70)
    print(
        f"Dosya   : {OUTPUT_FILE}"
    )
    print(
        f"Kanal   : {len(channels)}"
    )
    print(
        f"Program : {len(programmes)}"
    )
    print(
        f"Boyut   : {file_size / 1024 / 1024:.2f} MB"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
