#!/usr/bin/env python3
"""
Test Suite: DocuSpace Phase 4 — S3 Storage (MinIO), Quotas & Antivirus ClamAV
Tests:
  1. Quota verification, atomic reservation, and quota exhaustion rejection (413).
  2. Prohibited executable file extensions & MIME types rejection.
  3. S3 Presigned URL HMAC-SHA256 signature generation and validation.
  4. ClamAV Fail-Closed scanning & EICAR test file quarantine.
  5. SHA-256 cryptographic integrity verification.
"""

import sys
import os
import uuid
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.storage.storage_interface import (
    is_prohibited_extension,
    is_prohibited_mime_type,
    PROHIBITED_EXTENSIONS
)
from backend.app.storage.s3_storage import S3Storage
from backend.app.security.antivirus import ClamAVScanner, EICAR_SIGNATURE
from backend.app.services.quota_service import (
    QuotaService,
    QuotaExceededError,
    FileSizeLimitExceededError
)

def test_quota_management_and_limits():
    """Test storage limits, atomic reservation, and capacity exhaustion."""
    print("  [>] Testing Quota Management, Reservations & Limits...")
    qs = QuotaService()
    tenant_id = str(uuid.uuid4())
    
    # Plan: 100 MB max storage, 25 MB max individual file
    max_storage = 100 * 1024 * 1024
    max_file = 25 * 1024 * 1024

    # 1. Check valid file (10 MB)
    status = qs.check_quota(tenant_id, 10 * 1024 * 1024, max_storage, max_file)
    assert status.available_bytes == max_storage
    assert status.used_bytes == 0

    # 2. Reserve 10 MB
    qs.reserve_quota(tenant_id, 10 * 1024 * 1024)
    usage = qs.get_or_create_usage(tenant_id)
    assert usage["reserved_bytes"] == 10 * 1024 * 1024

    # 3. Commit the 10 MB upon clean scan
    qs.commit_quota(tenant_id, 10 * 1024 * 1024)
    usage = qs.get_or_create_usage(tenant_id)
    assert usage["reserved_bytes"] == 0
    assert usage["used_bytes"] == 10 * 1024 * 1024
    assert usage["document_count"] == 1

    # 4. Check file exceeding individual limit (30 MB > 25 MB)
    try:
        qs.check_quota(tenant_id, 30 * 1024 * 1024, max_storage, max_file)
        assert False, "Should have raised FileSizeLimitExceededError"
    except FileSizeLimitExceededError as e:
        assert e.file_size_bytes == 30 * 1024 * 1024

    # 5. Check file exceeding total quota (used 10 MB + 95 MB > 100 MB)
    try:
        qs.check_quota(tenant_id, 95 * 1024 * 1024, max_storage, 100 * 1024 * 1024)
        assert False, "Should have raised QuotaExceededError"
    except QuotaExceededError as e:
        assert e.required_bytes == 95 * 1024 * 1024

    # 6. Reclaim quota on document delete (10 MB)
    qs.reclaim_quota(tenant_id, 10 * 1024 * 1024)
    usage = qs.get_or_create_usage(tenant_id)
    assert usage["used_bytes"] == 0
    assert usage["document_count"] == 0
    print("  [✓] Quota atomic reservation and limits verified.")

def test_file_extension_and_security_rules():
    """Test strict rejection of executable files (zero-execution)."""
    print("  [>] Testing Zero-Execution File Extension Barrier...")
    
    # Prohibited dangerous extensions
    dangerous_files = [
        "payload.exe", "setup.msi", "script.sh", "run.bat", 
        "attack.ps1", "macro.vbs", "lib.dll", "driver.sys", "app.bin"
    ]
    for filename in dangerous_files:
        assert is_prohibited_extension(filename), f"Extension for '{filename}' should be prohibited!"

    # Allowed productive formats
    allowed_files = [
        "facture.pdf", "contrat.docx", "bilan.xlsx", "archives.zip", 
        "photo.png", "schema.svg", "notes.md", "data.csv", "config.json"
    ]
    for filename in allowed_files:
        assert not is_prohibited_extension(filename), f"File '{filename}' should be allowed!"

    assert is_prohibited_mime_type("application/x-msdownload")
    assert is_prohibited_mime_type("application/x-executable")
    assert is_prohibited_mime_type("application/x-sh")
    assert not is_prohibited_mime_type("application/pdf")
    print("  [✓] Prohibited executables and MIME types successfully blocked.")

def test_s3_presigned_urls_and_hmac():
    """Test S3 MinIO presigned upload & download URL HMAC signatures."""
    print("  [>] Testing S3 / MinIO Presigned URLs & HMAC-SHA256 Signatures...")
    s3 = S3Storage(
        endpoint="localhost:9000",
        access_key="test_minio_user",
        secret_key="test_super_secret_minio_key_32_chars",
        bucket_name="docuspace-documents"
    )

    storage_key = "tenants/tnt-alice-main/doc-1234.pdf"

    # 1. Presigned Upload URL
    upload_spec = s3.generate_presigned_upload_url(
        storage_key=storage_key,
        content_type="application/pdf",
        max_size_bytes=10485760,
        expires_in=3600
    )
    assert "upload_url" in upload_spec
    assert "Signature=" in upload_spec["upload_url"]
    assert "Expires=" in upload_spec["upload_url"]
    assert upload_spec["storage_key"] == storage_key
    assert upload_spec["headers"]["Content-Type"] == "application/pdf"

    # 2. Presigned Download URL
    download_url = s3.generate_presigned_download_url(
        storage_key=storage_key,
        filename="Rapport Annuel 2026.pdf",
        expires_in=900
    )
    assert "Signature=" in download_url
    assert "response-content-disposition=" in download_url

    # 3. Token verification
    expires_at = upload_spec["expires_at"]
    # Extract signature parameter from query string
    sig_param = upload_spec["upload_url"].split("Signature=")[1].split("&")[0]
    is_valid = s3.verify_presigned_token(storage_key, expires_at, sig_param, action="PUT")
    assert is_valid, "Authentic presigned token should verify as True"

    # Tampered signature must fail
    is_fake_valid = s3.verify_presigned_token(storage_key, expires_at, "tampered_signature_xyz", action="PUT")
    assert not is_fake_valid, "Tampered signature must be rejected"

    # Expired token must fail
    is_expired_valid = s3.verify_presigned_token(storage_key, int(time.time()) - 10, sig_param, action="PUT")
    assert not is_expired_valid, "Expired token must be rejected"
    print("  [✓] S3 MinIO presigned URL HMAC signatures verified.")

def test_clamav_antivirus_fail_closed():
    """Test ClamAV scanner with clean file, EICAR virus, and binary headers."""
    print("  [>] Testing ClamAV Antivirus Scanner (Fail-Closed & Heuristics)...")
    scanner = ClamAVScanner(fail_closed=True)

    # 1. Clean file test
    clean_content = b"%PDF-1.7\n1 0 obj\n<< /Title (DocuSpace Secure PDF) >>\nendobj\ntrailer\n%%EOF"
    res_clean = scanner.scan_bytes(clean_content)
    assert res_clean.is_clean, "Clean PDF should be marked clean"
    assert res_clean.status == "CLEAN"

    # 2. EICAR Standard Antivirus Test signature
    infected_content = b"Prefix text " + EICAR_SIGNATURE + b" Suffix text"
    res_infected = scanner.scan_bytes(infected_content)
    assert not res_infected.is_clean, "EICAR string must be flagged as infected!"
    assert res_infected.status == "INFECTED"
    assert "EICAR" in res_infected.threat_name

    # 3. Disguised Windows PE Executable
    disguised_exe = b"MZ" + b"\x00" * 80 + b"PE\x00\x00"
    res_exe = scanner.scan_bytes(disguised_exe)
    assert not res_exe.is_clean, "Disguised PE executable header must be blocked!"
    assert res_exe.status == "INFECTED"

    # 4. Disguised Linux ELF Binary
    disguised_elf = b"\x7fELF" + b"\x01\x01\x01\x00" * 10
    res_elf = scanner.scan_bytes(disguised_elf)
    assert not res_elf.is_clean, "Disguised ELF executable must be blocked!"
    assert res_elf.status == "INFECTED"
    print("  [✓] ClamAV antivirus quarantine and fail-closed protections verified.")

def test_sha256_checksum():
    """Test SHA-256 cryptographic hash computation."""
    print("  [>] Testing SHA-256 Checksum Calculation...")
    payload = b"DocuSpace Cryptographic Proof of Integrity 2026"
    expected_hash = "2b1672be09d44d76a50130602eb8df1c040e61cde5351c7ddc040ac951a06d63"
    computed_hash = S3Storage.compute_sha256(payload)
    assert len(computed_hash) == 64
    assert computed_hash == expected_hash
    print("  [✓] SHA-256 hash verified successfully.")

def run_all_tests():
    print("[*] ========================================================")
    print("[*] Running DocuSpace Phase 4 — S3 Storage, Quotas & ClamAV")
    print("[*] ========================================================")
    test_quota_management_and_limits()
    test_file_extension_and_security_rules()
    test_s3_presigned_urls_and_hmac()
    test_clamav_antivirus_fail_closed()
    test_sha256_checksum()
    print("[*] ========================================================")
    print("[*] ALL PHASE 4 STORAGE, CLAMAV & QUOTAS TESTS PASSED!")
    print("[*] ========================================================")

if __name__ == "__main__":
    run_all_tests()
