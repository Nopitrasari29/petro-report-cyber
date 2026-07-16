# app/services/ai_engine/ollama_client.py
import json
import re
import ollama
import requests
from app.core.config import settings
from app.services.ai_engine.prompts import SYSTEM_PROMPT, get_analysis_prompt

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

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Mengirimkan pesan prompt ke Ollama lokal dengan parameter dinamis.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Load settings secara dinamis dari DB / config
        ai_cfg = get_ai_settings()
        
        response = self.client.chat(
            model=ai_cfg["model"],
            messages=messages,
            options={"temperature": ai_cfg["temperature"]}
        )
        return response["message"]["content"]

    def _normalize_json_keys(self, data: dict) -> dict:
        """
        Menjamin bahwa semua kunci JSON yang diperlukan oleh Frontend Next.js
        pasti ada dengan format penulisan yang konsisten. Mencegah error jika
        AI melakukan salah ketik nama kunci.
        """
        required_keys = {
            "executive_summary": "Ringkasan analisis tidak berhasil dimuat secara otomatis.",
            "trend_analysis": "Analisis tren tidak tersedia.",
            "severity_analysis": "Detail tingkat keparahan tidak dapat dipetakan.",
            "risk_assessment": "Penilaian risiko tidak dapat dirumuskan.",
            "recommendations": ["Tinjau kembali log siber secara manual."],
            "conclusion": "Analisis selesai dengan penyesuaian manual."
        }
        
        normalized = {}
        for key, default_val in required_keys.items():
            found_key = None
            key_variations = [key, key.replace("_", ""), key.lower(), key.upper()]
            
            # Konversi snake_case ke camelCase (contoh: executive_summary -> executiveSummary)
            camel_case = "".join(x.capitalize() or "_" for x in key.split("_"))
            camel_case = camel_case[0].lower() + camel_case[1:]
            key_variations.append(camel_case)

            for var in key_variations:
                if var in data:
                    found_key = var
                    break
            
            if found_key is not None:
                # Pastikan tipe data untuk recommendations adalah list
                if key == "recommendations" and not isinstance(data[found_key], list):
                    if isinstance(data[found_key], str):
                        normalized[key] = [data[found_key]]
                    else:
                        normalized[key] = default_val
                else:
                    normalized[key] = data[found_key]
            else:
                normalized[key] = default_val
                
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

    def _smart_sample_data(self, parsed_data: list) -> list:
        """
        Mengambil sampel data secara cerdas agar representatif:
        - <= 500 baris: ambil semua
        - > 500 baris: 200 pertama + 150 tengah + 150 terakhir
        """
        total = len(parsed_data)
        if total <= 500:
            return parsed_data
        first = parsed_data[:200]
        mid_start = max(0, (total // 2) - 75)
        middle = parsed_data[mid_start:mid_start + 150]
        last = parsed_data[-150:]
        return first + middle + last

    def analyze_security_data(
        self, 
        data_type: str, 
        parsed_data: list,
        period_start: str | None = None,
        period_end: str | None = None,
        template_type: str | None = None,
        language: str | None = None
    ) -> dict:
        """
        Mengonversi log parsed siber ke string, memicu Ollama Qwen,
        dan memformat hasilnya kembali menjadi dictionary/JSON secara robust.
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
            return {
                "executive_summary": "Gagal merumuskan ringkasan otomatis karena service Ollama tidak aktif.",
                "trend_analysis": "Ollama offline. Silakan pastikan aplikasi Ollama berjalan di server atau local VM Anda.",
                "severity_analysis": "Pengecekan koneksi ke host Ollama gagal.",
                "risk_assessment": "Penilaian risiko terhenti.",
                "recommendations": [
                    "Buka aplikasi Ollama di server/komputer Anda.",
                    "Pastikan port default 11434 aktif.",
                    "Jalankan command 'ollama pull qwen3:8b' jika model belum diunduh."
                ],
                "conclusion": "Ollama service connection failed."
            }

        # Smart sampling — representasi distribusi data tanpa membuat context limit penuh
        sampled_data = self._smart_sample_data(parsed_data)
        data_str = json.dumps(sampled_data, indent=2, ensure_ascii=False)

        # Hasilkan prompt dengan metadata lengkap
        prompt = get_analysis_prompt(
            data_type=data_type,
            data_content=data_str,
            period_start=period_start,
            period_end=period_end,
            template_type=template_type,
            language=language
        )

        raw_response = None
        try:
            raw_response = self.generate(prompt, system_prompt=SYSTEM_PROMPT)
            return self._extract_json_robust(raw_response)
        except Exception as e:
            preview = raw_response[:300] if raw_response else "Tidak ada respon"
            return {
                "executive_summary": "Gagal merumuskan ringkasan otomatis karena masalah timeout atau parser model.",
                "trend_analysis": f"Error parsing respon AI. Detail: {str(e)}",
                "severity_analysis": "Distribusi severity gagal dipetakan.",
                "risk_assessment": "Penilaian risiko gagal diproses.",
                "recommendations": [
                    "Periksa kestabilan service Ollama siber di server local.",
                    "Pastikan model 'qwen3:8b' telah terunduh.",
                    "Coba unggah ulang data dengan volume log yang lebih kecil."
                ],
                "conclusion": f"Proses terhenti. Preview respon: {preview}"
            }

ollama_client = OllamaClient()