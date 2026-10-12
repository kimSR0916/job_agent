"""기본 TLS 검증에 macOS가 신뢰하는 시스템 인증서를 추가합니다."""
from functools import lru_cache
import ssl
import subprocess
import sys


@lru_cache(maxsize=1)
def tls_context():
    context = ssl.create_default_context()
    if sys.platform == "darwin":
        for keychain in ("/System/Library/Keychains/SystemRootCertificates.keychain",
                         "/Library/Keychains/System.keychain"):
            result = subprocess.run(["/usr/bin/security", "find-certificate", "-a", "-p", keychain],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                context.load_verify_locations(cadata=result.stdout)
    return context
