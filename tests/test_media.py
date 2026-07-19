import base64

import pytest

from backend.media import resolve_campaign_media, store_generated_image


PNG = b"\x89PNG\r\n\x1a\n" + b"test-image-data"


def test_generated_image_is_content_addressed_and_resolvable(tmp_path):
    source = tmp_path / "renderer.png"
    source.write_bytes(PNG)
    campaign_dir = tmp_path / "campaign"

    published = store_generated_image(campaign_dir, source_path=source)
    resolved = resolve_campaign_media(campaign_dir, published.filename)

    assert published.mime_type == "image/png"
    assert published.size == len(PNG)
    assert resolved.read_bytes() == PNG


def test_generated_image_accepts_base64_data_url(tmp_path):
    encoded = base64.b64encode(PNG).decode()

    published = store_generated_image(
        tmp_path,
        data_url=f"data:image/png;base64,{encoded}",
    )

    assert resolve_campaign_media(tmp_path, published.filename).read_bytes() == PNG


@pytest.mark.parametrize("filename", ["../world.json", "world.json", "a" * 32 + ".txt"])
def test_campaign_media_rejects_non_generated_paths(tmp_path, filename):
    with pytest.raises(FileNotFoundError):
        resolve_campaign_media(tmp_path, filename)


def test_generated_media_rejects_non_image_bytes(tmp_path):
    with pytest.raises(ValueError, match="supported raster"):
        store_generated_image(
            tmp_path,
            data_url="data:image/png;base64,bm90IGFuIGltYWdl",
        )
