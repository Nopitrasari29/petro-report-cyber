import time
from collections import defaultdict
from threading import Lock
from fastapi import HTTPException, status


class InMemoryRateLimiter:
    """
    Rate limiter sederhana berbasis memory (per-process, per-key), tanpa dependency tambahan.

    CATATAN PENTING: ini BUKAN solusi production-grade untuk deployment multi-worker/multi-instance
    (misal beberapa proses uvicorn di belakang load balancer) — counter-nya tidak sinkron antar
    proses, jadi batasnya efektif jadi (max_attempts x jumlah_proses). Untuk internal tool skala
    kecil dengan 1 instance backend, ini cukup untuk mencegah brute-force/spam kasar. Kalau nanti
    di-deploy multi-worker, ganti dengan limiter berbasis Redis (misal slowapi + Redis backend).
    """

    def __init__(self):
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str, max_attempts: int, window_seconds: int):
        """
        Cek & catat satu percobaan untuk `key`. Melempar HTTP 429 kalau sudah melebihi
        `max_attempts` dalam `window_seconds` detik terakhir.
        """
        now = time.time()
        with self._lock:
            attempts = self._hits[key]
            attempts[:] = [t for t in attempts if now - t < window_seconds]

            if len(attempts) >= max_attempts:
                retry_after = int(window_seconds - (now - attempts[0]))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Terlalu banyak percobaan. Coba lagi dalam {max(retry_after, 1)} detik."
                )

            attempts.append(now)


# Singleton — dipakai bareng di semua endpoint yang butuh rate limit
rate_limiter = InMemoryRateLimiter()