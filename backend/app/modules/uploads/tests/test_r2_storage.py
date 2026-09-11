"""Unit tests for R2Storage — boto3's S3 client is mocked (no real R2
credentials/network needed, matching the explicit 'no real R2
credentials in CI' constraint). Verifies R2Storage builds the right
boto3 calls, not that R2 itself works (that requires real, manual
verification — see docs/Sprint27_R2_Media_Storage.md)."""
from unittest.mock import MagicMock, patch

from app.modules.uploads.storage import R2Storage


def make_storage(mock_boto_client):
    with patch("boto3.client", return_value=mock_boto_client):
        return R2Storage(
            account_id="acct123", access_key_id="key", secret_access_key="secret",
            bucket="bilimuz-media", endpoint="",
        )


def test_r2storage_builds_default_endpoint_from_account_id():
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client) as mock_boto3_client:
        R2Storage(account_id="acct123", access_key_id="k", secret_access_key="s", bucket="b", endpoint="")
    _, kwargs = mock_boto3_client.call_args
    assert kwargs["endpoint_url"] == "https://acct123.r2.cloudflarestorage.com"


def test_r2storage_uses_explicit_endpoint_override_when_given():
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client) as mock_boto3_client:
        R2Storage(account_id="acct123", access_key_id="k", secret_access_key="s", bucket="b", endpoint="https://custom.example.com")
    _, kwargs = mock_boto3_client.call_args
    assert kwargs["endpoint_url"] == "https://custom.example.com"


def test_create_presigned_upload_calls_put_object_with_correct_params():
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://signed-put-url"
    storage = make_storage(mock_client)

    result = storage.create_presigned_upload("lessons/l1/video/abc.mp4", "video/mp4", 900)

    mock_client.generate_presigned_url.assert_called_once_with(
        "put_object",
        Params={"Bucket": "bilimuz-media", "Key": "lessons/l1/video/abc.mp4", "ContentType": "video/mp4"},
        ExpiresIn=900,
    )
    assert result.url == "https://signed-put-url"
    assert result.required_headers == {"Content-Type": "video/mp4"}


def test_create_presigned_download_calls_get_object_with_correct_params():
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://signed-get-url"
    storage = make_storage(mock_client)

    url = storage.create_presigned_download("lessons/l1/video/abc.mp4", 300)

    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "bilimuz-media", "Key": "lessons/l1/video/abc.mp4"},
        ExpiresIn=300,
    )
    assert url == "https://signed-get-url"


def test_delete_calls_delete_object_and_is_idempotent_by_the_s3_api_itself():
    mock_client = MagicMock()
    storage = make_storage(mock_client)
    storage.delete("lessons/l1/video/abc.mp4")
    mock_client.delete_object.assert_called_once_with(Bucket="bilimuz-media", Key="lessons/l1/video/abc.mp4")


# --- Sprint 27 Amendment: R2 Multipart Upload ---

def test_create_multipart_upload_calls_the_right_boto3_api():
    mock_client = MagicMock()
    mock_client.create_multipart_upload.return_value = {"UploadId": "r2-mp-id-123"}
    storage = make_storage(mock_client)

    result = storage.create_multipart_upload("lessons/l1/video/big.mp4", "video/mp4")

    mock_client.create_multipart_upload.assert_called_once_with(
        Bucket="bilimuz-media", Key="lessons/l1/video/big.mp4", ContentType="video/mp4",
    )
    assert result == "r2-mp-id-123"


def test_create_presigned_part_url_calls_upload_part_with_correct_params():
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://signed-part-url"
    storage = make_storage(mock_client)

    url = storage.create_presigned_part_url("lessons/l1/video/big.mp4", "r2-mp-id-123", 5, 900)

    mock_client.generate_presigned_url.assert_called_once_with(
        "upload_part",
        Params={"Bucket": "bilimuz-media", "Key": "lessons/l1/video/big.mp4", "UploadId": "r2-mp-id-123", "PartNumber": 5},
        ExpiresIn=900,
    )
    assert url == "https://signed-part-url"


def test_complete_multipart_upload_calls_the_right_boto3_api():
    mock_client = MagicMock()
    storage = make_storage(mock_client)
    parts = [{"PartNumber": 1, "ETag": "e1"}, {"PartNumber": 2, "ETag": "e2"}]

    storage.complete_multipart_upload("lessons/l1/video/big.mp4", "r2-mp-id-123", parts)

    mock_client.complete_multipart_upload.assert_called_once_with(
        Bucket="bilimuz-media", Key="lessons/l1/video/big.mp4", UploadId="r2-mp-id-123",
        MultipartUpload={"Parts": parts},
    )


def test_abort_multipart_upload_calls_the_right_boto3_api():
    mock_client = MagicMock()
    storage = make_storage(mock_client)

    storage.abort_multipart_upload("lessons/l1/video/big.mp4", "r2-mp-id-123")

    mock_client.abort_multipart_upload.assert_called_once_with(
        Bucket="bilimuz-media", Key="lessons/l1/video/big.mp4", UploadId="r2-mp-id-123",
    )
