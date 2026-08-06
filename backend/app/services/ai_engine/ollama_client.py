# app/services/ai_engine/ollama_client.py
import json
import re
import ollama
import requests
from app.core.config import settings
from app.services.ai_engine.prompts import (
    SYSTEM_PROMPT,
    get_analysis_prompt,
    SECTION_SUGGESTION_SYSTEM_PROMPT,
    get_section_suggestion_prompt,
)
from app.services.ai_engine.data_profiler import (
    compute_statistics,
    compute_schema_summary,
    format_statistics_as_text,
    format_schema_as_text,
)

# Dipakai bersama oleh _normalize_json_keys (nilai fallback per key) dan analysis.py
# (Fix deteksi laporan yang "sukses" tapi isinya cuma teks default ini semua).
_REQUIRED_KEY_DEFAULTS = {
    "executive_summary": "Ringkasan analisis tidak berhasil dimuat secara otomatis.",
    "trend_analysis": "Analisis tren tidak tersedia.",
    "severity_analysis": "Detail tingkat keparahan tidak dapat dipetakan.",
    "risk_assessment": "Penilaian risiko tidak dapat dirumuskan.",
    "recommendations": ["Tinjau kembali log siber secara manual."],
    "conclusion": "Analisis selesai dengan penyesuaian manual."
}

# Alias key Bahasa Indonesia yang umum dipakai model walau SYSTEM_PROMPT sudah minta
# snake_case Inggris persis — dicocokkan lewat _normalize_single_key (bukan match string
# apa adanya), jadi "Ringkasan Eksekutif" atau "ringkasan-eksekutif" ikut ketangkap juga.
_KEY_ALIASES: dict[str, list[str]] = {
    "executive_summary": ["executive_summary", "ringkasan_eksekutif", "ringkasan_eksekutif_summary", "summary"],
    "trend_analysis": ["trend_analysis", "analisis_tren", "analisa_tren", "tren"],
    "severity_analysis": ["severity_analysis", "analisis_severity", "analisis_tingkat_keparahan", "tingkat_keparahan"],
    "risk_assessment": ["risk_assessment", "penilaian_risiko", "analisis_risiko", "risiko"],
    "recommendations": ["recommendations", "rekomendasi", "recommendation"],
    "conclusion": ["conclusion", "kesimpulan"],
}

# Fase B — key TAMBAHAN opsional (bukan bagian dari 6 key wajib): tidak memicu retry/fallback
# di analysis.py kalau kosong, cuma disalin apa adanya kalau model AI menyertakannya.
# "sections" (PART A3): array {id,title,content} dinamis, diisi HANYA kalau prompt menyertakan
# daftar section terpilih (lihat get_analysis_prompt selected_sections) — additive, tidak
# menggantikan 6 key wajib, supaya laporan lama & rendering lama tetap kompatibel.
_OPTIONAL_KEYS = ["key_findings", "metrics_table", "chart_captions", "sections"]

_NUMBERED_OR_BULLET_RE = re.compile(r"\s*(?:\d+[\)\.]|[•\-\*])\s+")
_TITLE_DETAIL_RE = re.compile(r"^([A-Z][^:]{2,50}):\s*(.+)$", re.DOTALL)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])")
_INTRO_LEADIN_RE = re.compile(r"^(berikut|adapun)\b.*:$", re.IGNORECASE)
_LEADING_INTRO_RE = re.compile(r"^\s*(?:berikut(?:\s+ini)?(?:\s+adalah)?|adapun)\b[^:]{0,80}:\s*", re.IGNORECASE)

_DASH_RE = re.compile(r"\s*[—–]\s*")
_DOUBLE_PUNCT_RE = re.compile(r"([.,;])\s*\1+")
# Frasa filler khas AI, dibuang di AWAL kalimat/paragraf
_FILLER_PATTERNS = [
    re.compile(r"^Berdasarkan analisis di atas,\s*", re.IGNORECASE),
    re.compile(r"^Berdasarkan data yang ada,\s*", re.IGNORECASE),
    re.compile(r"^Sebagaimana telah disebutkan,\s*", re.IGNORECASE),
    re.compile(r"^Mengacu pada data tersebut,\s*", re.IGNORECASE),
    re.compile(r"^Penting untuk dicatat bahwa\s*", re.IGNORECASE),
    re.compile(r"^Dapat disimpulkan bahwa\s*", re.IGNORECASE),
    re.compile(r"^Hal ini menunjukkan bahwa\s*", re.IGNORECASE),
    re.compile(r"^Perlu diketahui bahwa\s*", re.IGNORECASE),
    re.compile(r"^Perlu diperhatikan bahwa\s*", re.IGNORECASE),
    re.compile(r"^Perlu dicatat bahwa\s*", re.IGNORECASE),
    re.compile(r"^Perlu diingat bahwa\s*", re.IGNORECASE),
    re.compile(r"^Secara keseluruhan,\s*", re.IGNORECASE),
    re.compile(r"^Sebagai catatan,\s*", re.IGNORECASE),
    re.compile(r"^Dalam rangka\s+", re.IGNORECASE),
    re.compile(r"^Dengan demikian,\s*", re.IGNORECASE),
    re.compile(r"^Secara umum,\s*", re.IGNORECASE),
    re.compile(r"^Pada dasarnya,\s*", re.IGNORECASE),
    # Konektor transisi antar-poin — wajar di tengah paragraf mengalir, tapi jadi ganjil kalau
    # nempel di awal KARTU/POIN yang berdiri sendiri (recommendations/key_findings), terutama
    # karena _split_multi_action_string() memang membelah satu paragraf jadi beberapa item
    # persis di batas kalimat semacam ini — jadi konektornya ikut terbawa ke item baru.
    re.compile(r"^Selain itu,\s*", re.IGNORECASE),
    re.compile(r"^Selanjutnya,\s*", re.IGNORECASE),
    re.compile(r"^(?:In addition|Additionally|Furthermore|Moreover),\s*", re.IGNORECASE),
]


def sanitize_text(text) -> str:
    """
    Bersihkan teks narasi AI sebelum dirender ke laporan: buang em dash/en dash,
    buang frasa filler khas AI di AWAL SETIAP KALIMAT (bukan hanya kalimat pertama),
    dan rapikan tanda baca ganda.
    """
    if not text:
        return ""
    
    raw = _DASH_RE.sub(". ", str(text).strip())
    
    # RCA-03: Pecah per kalimat agar filler di tengah paragraf juga terbuang
    sentences = re.split(r"(?<=[.!?])\s+", raw)
    cleaned_sentences = []
    for s in sentences:
        s_clean = s.strip()
        for pattern in _FILLER_PATTERNS:
            s_clean = pattern.sub("", s_clean)
        if s_clean:
            if s_clean[0].islower():
                s_clean = s_clean[0].upper() + s_clean[1:]
            cleaned_sentences.append(s_clean)

    result = " ".join(cleaned_sentences)
    result = _DOUBLE_PUNCT_RE.sub(r"\1", result)
    result = re.sub(r"\s{2,}", " ", result).strip()
    return result


def _split_multi_action_string(text: str) -> list:
    """Pecah SATU string panjang jadi beberapa tindakan terpisah — model sering mengembalikan
    beberapa tindakan digabung jadi satu paragraf/satu elemen list, bukan array yang sudah
    terpisah per tindakan. Buang dulu kalimat pembuka generik yang MENEMPEL di awal teks
    ("Berikut adalah rekomendasi: Perbarui firewall..." -> "Perbarui firewall...") SEBELUM
    memecah, supaya kalimat pembuka itu tidak ikut terbawa jadi judul/kartu sendiri. Lalu coba
    pola paling eksplisit dulu (bernomor/bullet), lalu titik-koma, lalu batas kalimat (otomatis
    menangkap transisi "Selain itu, ..."/"Perlu juga ..." karena keduanya mengawali kalimat
    baru) — dan buang lagi kalau ada fragmen yang TERNYATA cuma kalimat pembuka berdiri sendiri
    (mis. hasil pemisahan bernomor/bullet). Kalau tidak ada pola manapun yang memecah jadi ≥2
    bagian, kembalikan teks apa adanya (berarti ini genuinely satu tindakan/satu kalimat)."""
    text = _LEADING_INTRO_RE.sub("", text.strip(), count=1).strip()
    if not text:
        return []
    for splitter in (
        lambda t: _NUMBERED_OR_BULLET_RE.split(t),
        lambda t: t.split(";"),
        lambda t: _SENTENCE_SPLIT_RE.split(t),
    ):
        parts = [p.strip() for p in splitter(text) if p.strip()]
        parts = [p for p in parts if not _INTRO_LEADIN_RE.match(p)]
        if len(parts) >= 2:
            return parts
    return [text]


def _clean_recommendation_text(text: str) -> str:
    """Buang sisa nomor manual di awal ('1) ', '2. ', '• ') dan tanda kurung yang tidak
    berpasangan (mis. sisa '(' menggantung tanpa ')' penutup, atau sebaliknya) — biasanya
    muncul karena kalimat lain "1) ... (2) ..." terpotong pas dipisah per poin."""
    text = str(text).strip()
    text = _NUMBERED_OR_BULLET_RE.sub("", text, count=1).strip()
    if text.count("(") != text.count(")"):
        if text.endswith("(") or text.endswith(" ("):
            text = text.rsplit("(", 1)[0].strip()
        elif text.startswith(")"):
            text = text[1:].strip()
        elif text.startswith("(") and ")" not in text:
            text = text[1:].strip()
        elif text.endswith(")") and "(" not in text:
            text = text[:-1].strip()
    return re.sub(r"\s{2,}", " ", text).strip()


def coerce_finding_text(item) -> str:
    """Model AI kadang salah format "key_findings" — harusnya array teks polos (1 kalimat per
    poin), tapi kadang malah diisi objek section ({"id","title","content"}, bentuk yang
    sebenarnya untuk field "sections"). Kalau item ternyata dict, ambil "content"/"title"-nya
    saja — JANGAN str()-kan seluruh dict apa adanya (dulu bug-nya begitu: repr Python mentah
    seperti "{'id': ..., 'title': ...}" muncul di laporan)."""
    if isinstance(item, dict):
        return str(item.get("content") or item.get("title") or "").strip()
    return str(item or "").strip()


def _split_recommendation_item(text: str) -> dict:
    """Pisah 'Judul singkat: detail' jadi {title, detail} kalau polanya jelas (judul pendek,
    diawali huruf kapital, diakhiri titik dua) — kalau tidak, semua masuk ke detail saja."""
    cleaned = _clean_recommendation_text(text)
    m = _TITLE_DETAIL_RE.match(cleaned)
    if m:
        return {"title": m.group(1).strip(), "detail": m.group(2).strip()}
    return {"title": None, "detail": cleaned}


def normalize_recommendations(value) -> list:
    """
    Ubah "recommendations" APAPUN bentuknya (satu string gabungan, array string polos, array
    campuran string/dict, atau sudah {title, detail}) jadi list[{title, detail}] yang bersih &
    konsisten. Dipakai DUA tempat: (1) _normalize_json_keys saat parsing respons AI baru, dan
    (2) langsung oleh export_ppt.py/export_pdf.py saat render — supaya laporan LAMA yang
    recommendations-nya masih array string mentah (belum pernah lewat fungsi ini) tetap
    dirender bersih & konsisten juga, tanpa perlu migrasi data.
    """
    if isinstance(value, str):
        value = _split_multi_action_string(value)

    if not isinstance(value, list):
        return []

    result = []
    for item in value:
        if isinstance(item, dict):
            title = item.get("title")
            detail = item.get("detail") or item.get("description") or ""
            detail = _clean_recommendation_text(detail) if detail else ""
            if detail:
                result.append({"title": _clean_recommendation_text(title) if title else None, "detail": detail})
        elif isinstance(item, str) and item.strip():
            # Satu ITEM di dalam list bisa jadi masih berupa paragraf gabungan beberapa
            # tindakan sekaligus (bukan cuma top-level value yang berupa satu string) —
            # pecah lagi per item, bukan langsung dipakai apa adanya sebagai satu kartu.
            for sub in _split_multi_action_string(item):
                result.append(_split_recommendation_item(sub))
    return result


def get_ai_settings() -> dict:
    """
    Membaca konfigurasi AI secara dinamis dengan default fallback yang terpadu.
    Mencegah error jika konfigurasi tabel settings belum terbuat di DB.
    """
    try:
        from app.api.v1.endpoints.settings import load_settings
        config = load_settings()
        return {
            "model": config.get("ai_model", settings.OLLAMA_MODEL),
            "temperature": float(config.get("ai_temperature", 0.3))
        }
    except Exception as err:
        print(f"[OLLAMA SETTINGS WARNING] Gagal membaca settings dari DB: {err}")
    return {
        "model": settings.OLLAMA_MODEL,
        "temperature": 0.3
    }


class OllamaClient:
    def __init__(self):
        self.client = ollama.Client(host=settings.OLLAMA_HOST)

    def is_available(self) -> bool:
        """
        Memeriksa apakah service Ollama aktif dan merespon request.
        """
        try:
            self.client.list()
            return True
        except Exception:
            try:
                res = requests.get(settings.OLLAMA_HOST, timeout=2)
                return res.status_code == 200
            except Exception:
                return False

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        on_progress=None,
    ) -> str:
        """
        Mengirimkan pesan prompt ke Ollama lokal dengan parameter dinamis.

        CATATAN PENTING (dikonfirmasi lewat debugging langsung): qwen3:8b yang dipakai di sini
        adalah model "thinking" (lihat capabilities di `ollama list` / API tags) — secara default
        dia menghasilkan penalaran step-by-step yang PANJANG sebelum jawaban akhir, di LUAR tag
        <think> yang sudah ditangani _extract_json_robust. Ini dua masalah sekaligus: (1) sangat
        lambat (satu request bisa >3 menit untuk data kecil sekalipun), dan (2) jawaban akhirnya
        kadang berupa narasi penalaran biasa, bukan JSON, sehingga parsing gagal total.

        Dipanggil lewat HTTP langsung (bukan lewat ollama.Client().chat()) karena versi paket
        `ollama` yang terinstall belum mengekspos parameter `think` sebagai argumen — padahal
        Ollama SERVER (dicek: v0.32.3) sudah mendukungnya di endpoint /api/chat. `think: false`
        mematikan mode penalaran itu (jawaban langsung, jauh lebih cepat), dan `format: "json"`
        memaksa constrained-decoding supaya keluarannya PASTI JSON valid secara sintaks — jauh
        lebih andal daripada cuma mengandalkan instruksi di system prompt.

        `stream: True` dipakai (bukan `False` seperti sebelumnya) supaya token generation bisa
        diamati SAAT terjadi — tiap baris NDJSON yang dikembalikan Ollama berisi satu potongan
        `message.content` (kira-kira 1 token). `on_progress(tokens_so_far, done)` dipanggil tiap
        potongan datang, dipakai backend buat mencatat progress asli (bukan animasi) ke DB supaya
        estimasi sisa waktu di frontend bisa dihitung dari kecepatan generate token yang genuinely
        terukur — sama seperti ETA download dihitung dari bytes/detik yang benar-benar diukur.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Load settings secara dinamis dari DB / config
        ai_cfg = get_ai_settings()

        payload = {
            "model": ai_cfg["model"],
            "messages": messages,
            "stream": True,
            "think": False,
            "options": {"temperature": ai_cfg["temperature"]},
        }
        if json_mode:
            payload["format"] = "json"

        content_parts: list[str] = []
        token_count = 0
        with requests.post(
            f"{settings.OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=settings.OLLAMA_TIMEOUT_SECONDS,
            stream=True,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                piece = (chunk.get("message") or {}).get("content", "")
                if piece:
                    content_parts.append(piece)
                    token_count += 1
                is_done = bool(chunk.get("done"))
                if on_progress and (piece or is_done):
                    # eval_count (jumlah token final dari Ollama sendiri) dipakai sebagai angka
                    # otoritatif begitu selesai — lebih akurat daripada hitungan baris NDJSON kita.
                    reported_count = chunk.get("eval_count", token_count) if is_done else token_count
                    on_progress(reported_count, done=is_done)
                if is_done:
                    break

        return "".join(content_parts)

    @staticmethod
    def _normalize_single_key(k: str) -> str:
        """'Executive Summary' / 'executive-summary' / 'EXECUTIVE_SUMMARY' -> 'executive_summary'."""
        return re.sub(r"[\s\-]+", "_", str(k).strip().lower())

    def _find_source_key(self, lookup: dict, target_key: str) -> str | None:
        """lookup: {key_ternormalisasi: key_asli_di_dict}. Coba semua alias termasuk camelCase."""
        for alias in _KEY_ALIASES.get(target_key, [target_key]):
            norm_alias = self._normalize_single_key(alias)
            if norm_alias in lookup:
                return lookup[norm_alias]

        camel_case = "".join(x.capitalize() or "_" for x in target_key.split("_"))
        camel_case = camel_case[0].lower() + camel_case[1:]
        norm_camel = self._normalize_single_key(camel_case)
        if norm_camel in lookup:
            return lookup[norm_camel]
        return None

    def _normalize_json_keys(self, data: dict) -> dict:
        """
        Menjamin bahwa semua kunci JSON yang diperlukan oleh Frontend Next.js pasti ada dengan
        format penulisan yang konsisten, walau model AI menjawab dengan variasi nama key:
        - kapitalisasi/spasi bebas ("Executive Summary")
        - alias Bahasa Indonesia ("ringkasan_eksekutif", dst — lihat _KEY_ALIASES)
        - dibungkus SATU objek dict lain (mis. {"laporan": {...6 key...}}) — kalau 0 dari 6 key
          ketemu di level atas dan ada TEPAT SATU value bertipe dict, cari lagi di dalamnya.
        """
        def build_lookup(d: dict) -> dict:
            return {self._normalize_single_key(k): k for k in d.keys()}

        lookup = build_lookup(data)
        search_data = data
        found_count = sum(
            1 for k in _REQUIRED_KEY_DEFAULTS if self._find_source_key(lookup, k) is not None
        )

        if found_count == 0:
            nested_dicts = [v for v in data.values() if isinstance(v, dict)]
            if len(nested_dicts) == 1:
                search_data = nested_dicts[0]
                lookup = build_lookup(search_data)

        normalized = {}
        for key, default_val in _REQUIRED_KEY_DEFAULTS.items():
            found_key = self._find_source_key(lookup, key)

            if found_key is not None:
                value = search_data[found_key]
                if key == "recommendations":
                    cleaned = normalize_recommendations(value)
                    normalized[key] = cleaned if cleaned else default_val
                else:
                    normalized[key] = value
            else:
                normalized[key] = default_val

        # Fase B — key opsional: disalin apa adanya kalau ada & berbentuk list, kalau tidak
        # ada/salah tipe cukup diisi list kosong (tidak pernah memicu fallback ke 6 key wajib).
        # "chart_captions" DIKECUALIKAN dari aturan list-only ini — modelnya sekarang objek
        # {"category"/"severity"/"status": "..."} (lihat prompts.py & report_render_logic.py:
        # _get_chart_caption), supaya narasi tidak salah pasang ke chart yang beda kalau ada
        # chart yang di-skip saat render (mis. user uncheck Include Sections > Severity
        # Analysis) — model TIDAK TAHU chart mana yang akhirnya benar-benar dirender, jadi
        # caption berbasis KEY, bukan posisi array. List lama (laporan sebelum fix ini) tetap
        # diterima apa adanya untuk kompatibilitas mundur.
        for opt_key in _OPTIONAL_KEYS:
            found_key = self._find_source_key(lookup, opt_key)
            value = search_data.get(found_key) if found_key is not None else None
            if opt_key == "chart_captions":
                value = value if isinstance(value, (list, dict)) else []
            else:
                value = value if isinstance(value, list) else []
            if opt_key == "key_findings":
                # Jaga-jaga di sumber juga (bukan cuma saat render) — model kadang mengisi
                # key_findings dengan objek section {"id","title","content"} yang salah bentuk.
                value = [coerce_finding_text(v) for v in value if coerce_finding_text(v)]
            normalized[opt_key] = value

        return normalized

    def _extract_json_robust(self, raw_text: str) -> dict:
        """
        Mengekstrak JSON valid dari teks mentah model AI secara robust.
        Menangani: tag <think>...</think> (Qwen3 Thinking Mode),
        markdown fenced code blocks, dan teks pengantar/penutup.
        """
        text = raw_text.strip()

        # 1. Strip tag <think>...</think> — muncul di Qwen3 thinking mode
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 2. Strip markdown fenced code blocks (```json ... ``` atau ``` ... ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
        text = text.strip()

        parsed_dict = None

        # 3. Coba parse langsung
        try:
            parsed_dict = json.loads(text)
        except json.JSONDecodeError:
            pass

        # 4. Cari blok JSON {...} terbesar menggunakan regex greedy jika parse langsung gagal
        if not parsed_dict:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    parsed_dict = json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

        if parsed_dict and isinstance(parsed_dict, dict):
            return self._normalize_json_keys(parsed_dict)

        raise ValueError(f"Tidak dapat mengekstrak JSON valid. Preview: {text[:300]}")

    def suggest_sections(
        self,
        schema_text: str,
        stats_text: str,
        file_name: str | None = None,
        domain_hint: str | None = None,
    ) -> list[dict] | None:
        """
        PART A1 — usulkan struktur section laporan (bebas, boleh di luar preset 4-domain) lewat
        AI, dipanggil section_suggester.py SEBELUM user masuk ke langkah Settings. SELALU return
        None (bukan raise) kalau Ollama offline/timeout/JSON tidak valid/shape tidak sesuai —
        caller (section_suggester.py) WAJIB fallback ke preset heuristik saat None, supaya upload
        file tetap responsif & tidak pernah error walau AI gagal/lambat.
        """
        if not self.is_available():
            return None

        prompt = get_section_suggestion_prompt(
            schema_text=schema_text,
            stats_text=stats_text,
            file_name=file_name,
            domain_hint=domain_hint,
        )
        try:
            raw_response = self.generate(
                prompt, system_prompt=SECTION_SUGGESTION_SYSTEM_PROMPT, json_mode=True
            )
            text = raw_response.strip()
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
            text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE).strip()

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None

            # Ollama json_mode (format="json") memaksa root berupa OBJECT (mirip OpenAI json
            # mode) — array telanjang di root ditolak/diabaikan oleh constrained decoding-nya,
            # makanya kontraknya {"sections": [...]}. Tetap terima array telanjang sebagai
            # fallback defensif kalau suatu saat perilaku model/versi Ollama berubah.
            sections_list = None
            if isinstance(parsed, dict):
                sections_list = parsed.get("sections")
            elif isinstance(parsed, list):
                sections_list = parsed

            if not isinstance(sections_list, list):
                array_text = None
                keyed_match = re.search(r'"sections"\s*:\s*(\[.*\])', text, re.DOTALL)
                if keyed_match:
                    array_text = keyed_match.group(1)
                else:
                    bare_match = re.search(r"\[.*\]", text, re.DOTALL)
                    if bare_match:
                        array_text = bare_match.group(0)
                if not array_text:
                    return None
                try:
                    sections_list = json.loads(array_text)
                except json.JSONDecodeError:
                    return None

            if not isinstance(sections_list, list) or not sections_list:
                return None
            parsed = sections_list

            result = []
            for idx, item in enumerate(parsed):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                key = str(item.get("id") or item.get("key") or f"section_{idx}").strip() or f"section_{idx}"
                recommended = item.get("recommended")
                recommended = True if recommended is None else bool(recommended)
                order_val = item.get("order")
                order = order_val if isinstance(order_val, (int, float)) else idx
                result.append({
                    "key": key,
                    "title": title,
                    "description": str(item.get("description") or "").strip(),
                    "order": order,
                    "recommended": recommended,
                    "enabled": recommended,
                })

            return result if result else None
        except Exception as e:
            print(f"[SECTION SUGGESTER] Gagal mendapatkan usulan section dari AI: {e}")
            return None

    def analyze_security_data(
        self,
        data_type: str,
        parsed_data: list,
        period_start: str | None = None,
        period_end: str | None = None,
        template_type: str | None = None,
        language: str | None = None,
        domain_type: str | None = None,
        selected_sections: list[dict] | None = None,
        tone: str | None = None,
        default_level: str | None = None,
        on_progress=None,
    ) -> dict:
        """
        Mengonversi data (log keamanan, keuangan, KPI, atau data umum) ke string,
        memicu Ollama Qwen dengan prompt yang disesuaikan per domain data,
        dan memformat hasilnya kembali menjadi dictionary/JSON secara robust.

        selected_sections: daftar section dinamis hasil pilihan user di Settings (PART A2/A3).
        Diteruskan apa adanya ke get_analysis_prompt — None berarti jalur lama (checkbox preset
        6-section), tidak ada perubahan perilaku apapun.
        """
        # Guard clause jika data log kosong
        if not parsed_data:
            return {
                "executive_summary": "Tidak ada data log yang berhasil dibaca atau diekstrak.",
                "trend_analysis": "Analisis tren ditiadakan karena file data kosong.",
                "severity_analysis": "Data log kosong.",
                "risk_assessment": "Potensi risiko nihil.",
                "recommendations": [
                    "Pastikan file log siber yang diunggah berisi rekaman aktivitas keamanan.",
                    "Periksa kembali format file (CSV, XLSX, JSON) dan pastikan baris data tidak kosong."
                ],
                "conclusion": "Proses selesai tanpa analisis data karena input kosong."
            }

        if not self.is_available():
            # Dulu ini mengembalikan dict "berhasil" berisi teks placeholder per field —
            # analysis.py tidak pernah mendeteksinya sebagai kegagalan (heuristik deteksi cuma
            # cocok untuk 1 dari 6 field), jadi laporan tersimpan status "analyzed" walau
            # Ollama benar-benar mati. Sekarang dilempar sebagai exception supaya mekanisme
            # retry/gagal yang SUDAH ADA di _run_analysis_job (analysis.py) menanganinya
            # secara wajar — retry 2x, lalu ditandai "failed" kalau tetap tidak tersedia.
            raise RuntimeError(
                "Layanan Ollama tidak aktif atau tidak dapat dihubungi. Pastikan Ollama "
                "berjalan di server/VM lokal dan model 'qwen3:8b' sudah diunduh."
            )

        # Precompute statistik & schema dari SELURUH data (bukan sampel) via pandas — deterministik,
        # selalu benar. Model tinggal MENARASIKAN angka ini, bukan menghitung sendiri dari data mentah.
        stats = compute_statistics(parsed_data, data_type)
        stats_text = format_statistics_as_text(stats)
        schema = compute_schema_summary(parsed_data)
        schema_text = format_schema_as_text(schema)

        # Cuma 15 baris ILUSTRATIF dikirim (bukan lagi ratusan baris) — sumber angka utama
        # sekarang stats_text di atas, bukan data mentah ini.
        sample_rows = parsed_data[:15]
        data_str = json.dumps(sample_rows, indent=2, ensure_ascii=False)

        # Hasilkan prompt dengan metadata lengkap + domain_type untuk konteks spesifik
        prompt = get_analysis_prompt(
            data_type=data_type,
            data_content=data_str,
            stats_text=stats_text,
            schema_text=schema_text,
            period_start=period_start,
            period_end=period_end,
            template_type=template_type,
            language=language,
            domain_type=domain_type,
            selected_sections=selected_sections,
            tone=tone,
            default_level=default_level,
        )

        raw_response = None
        try:
            raw_response = self.generate(
                prompt, system_prompt=SYSTEM_PROMPT, json_mode=True, on_progress=on_progress
            )
            print(f"[OLLAMA RAW]\n{raw_response[:2000]}")
            result_json = self._extract_json_robust(raw_response)
            
            # Fallback jika chart_captions kosong
            if not result_json.get("chart_captions"):
                from app.services.ai_engine.data_profiler import build_chart_captions_from_stats
                result_json["chart_captions"] = build_chart_captions_from_stats(stats, domain_type or "general")
                
            return result_json
        except Exception as e:
            # Sama seperti guard Ollama-offline di atas — dulu mengembalikan dict "berhasil"
            # berisi teks error mentah per field (termasuk potongan respons AI yang rusak,
            # yang akhirnya tercetak langsung ke PDF/PPTX client), dan tidak pernah terdeteksi
            # sebagai kegagalan oleh analysis.py. Sekarang dilempar ulang supaya mekanisme
            # retry/gagal yang sudah ada menanganinya, bukan disamarkan sebagai analisis sukses.
            preview = raw_response[:300] if raw_response else "Tidak ada respon"
            raise RuntimeError(
                f"Gagal memproses respons AI (timeout atau format tidak valid): {str(e)}. "
                f"Cuplikan respons: {preview}"
            ) from e

ollama_client = OllamaClient()