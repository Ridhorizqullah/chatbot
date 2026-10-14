from dataclasses import dataclass
from typing import Optional
import cv2
import numpy as np
from core.logger import logger


@dataclass
class CVQualityResult:
    """Hasil analisis prapemrosesan citra berbasis OpenCV."""
    is_valid: bool
    is_blurry: bool
    blur_score: float
    is_plant: bool
    plant_coverage: float
    organ_hint: str  # 'buah', 'daun', 'tanaman_utuh', atau 'tidak_diketahui'
    rejection_reason: Optional[str] = None


class CVPreprocessor:
    """
    Service prapemrosesan citra pertanian menggunakan OpenCV.
    Berfungsi sebagai gatekeeper ringan (CPU < 15ms) sebelum pemanggilan model AI berat:
    1. Memvalidasi integritas data biner citra.
    2. Deteksi foto kabur/goyang (Laplacian variance test).
    3. Segmentasi warna HSV untuk memastikan objek adalah tanaman/daun/buah.
    4. Ekstraksi petunjuk organ tanaman (daun, buah, tanaman utuh).
    """

    # Ambang batas variansi Laplacian untuk mendeteksi blur
    BLUR_THRESHOLD: float = 75.0

    # Ambang batas minimal luas area warna tanaman (10%)
    MIN_PLANT_COVERAGE: float = 0.08

    @classmethod
    def inspect_image(cls, image_bytes: bytes) -> CVQualityResult:
        """
        Menganalisis kualitas dan konten fisik foto tanaman menggunakan OpenCV.
        """
        if not image_bytes or len(image_bytes) < 100:
            return CVQualityResult(
                is_valid=False,
                is_blurry=True,
                blur_score=0.0,
                is_plant=False,
                plant_coverage=0.0,
                organ_hint="tidak_diketahui",
                rejection_reason="File foto kosong atau data citra rusak."
            )

        try:
            # 1. Decode byte stream ke matriks OpenCV (BGR uint8)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img_bgr is None or img_bgr.size == 0:
                return CVQualityResult(
                    is_valid=False,
                    is_blurry=True,
                    blur_score=0.0,
                    is_plant=False,
                    plant_coverage=0.0,
                    organ_hint="tidak_diketahui",
                    rejection_reason="Format citra tidak didukung atau file terkorupsi."
                )

            # Optimasi ukuran jika foto terlalu besar (resize dengan tetap menjaga aspek rasio)
            h, w = img_bgr.shape[:2]
            max_dim = 1024
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                h, w = img_bgr.shape[:2]

            total_pixels = h * w

            # 2. Deteksi Blur menggunakan Laplacian Operator
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            blur_score = float(laplacian.var())
            is_blurry = blur_score < cls.BLUR_THRESHOLD

            if is_blurry:
                return CVQualityResult(
                    is_valid=False,
                    is_blurry=True,
                    blur_score=round(blur_score, 2),
                    is_plant=False,
                    plant_coverage=0.0,
                    organ_hint="tidak_diketahui",
                    rejection_reason=(
                        f"Foto terdeteksi buram atau goyang (skor fokus: {blur_score:.1f} < {cls.BLUR_THRESHOLD}). "
                        "Mohon ambil foto ulang dengan pencahayaan cukup dan fokus stabil pada bagian tanaman yang sakit."
                    )
                )

            # 3. Analisis Ruang Warna HSV untuk Validasi Tanaman (Plant Foliage & Fruit Masking)
            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

            # Range Warna Hijau (Daun Sehat)
            green_lower = np.array([25, 30, 30])
            green_upper = np.array([88, 255, 255])
            mask_green = cv2.inRange(hsv, green_lower, green_upper)

            # Range Warna Kuning / Klorosis / Bulai
            yellow_lower = np.array([15, 40, 40])
            yellow_upper = np.array([25, 255, 255])
            mask_yellow = cv2.inRange(hsv, yellow_lower, yellow_upper)

            # Range Warna Buah Merah Cabai / Patek
            red_lower1 = np.array([0, 50, 40])
            red_upper1 = np.array([12, 255, 255])
            red_lower2 = np.array([168, 50, 40])
            red_upper2 = np.array([180, 255, 255])
            mask_red = cv2.bitwise_or(
                cv2.inRange(hsv, red_lower1, red_upper1),
                cv2.inRange(hsv, red_lower2, red_upper2)
            )

            # Range Warna Coklat / Nekrosis / Lesi
            brown_lower = np.array([8, 40, 20])
            brown_upper = np.array([24, 255, 200])
            mask_brown = cv2.inRange(hsv, brown_lower, brown_upper)

            # Gabungkan seluruh area tanaman (hijau + kuning klorosis + merah buah + coklat lesi)
            plant_mask = cv2.bitwise_or(mask_green, mask_yellow)
            plant_mask = cv2.bitwise_or(plant_mask, mask_red)
            plant_mask = cv2.bitwise_or(plant_mask, mask_brown)

            # Operasi Morfologi untuk menghilangkan noise kecil
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            plant_mask = cv2.morphologyEx(plant_mask, cv2.MORPH_OPEN, kernel)

            plant_pixels = int(cv2.countNonZero(plant_mask))
            plant_coverage = plant_pixels / total_pixels

            is_plant = plant_coverage >= cls.MIN_PLANT_COVERAGE

            if not is_plant:
                return CVQualityResult(
                    is_valid=False,
                    is_blurry=False,
                    blur_score=round(blur_score, 2),
                    is_plant=False,
                    plant_coverage=round(plant_coverage, 3),
                    organ_hint="tidak_diketahui",
                    rejection_reason=(
                        f"Foto tidak menunjukkan objek tanaman atau daun/buah yang cukup jelas "
                        f"(area tanaman hanya {plant_coverage*100:.1f}%). "
                        "Pastikan objek foto terfokus pada daun, buah, atau batang tanaman cabai/padi."
                    )
                )

            # 4. Deteksi Petunjuk Organ (Organ Hint)
            red_pixels = int(cv2.countNonZero(mask_red))
            leaf_pixels = int(cv2.countNonZero(cv2.bitwise_or(mask_green, mask_yellow)))

            red_ratio = red_pixels / total_pixels
            leaf_ratio = leaf_pixels / total_pixels

            if red_ratio > 0.05 or (red_pixels > 0 and red_pixels > leaf_pixels * 0.4):
                organ_hint = "buah"
            elif leaf_ratio > 0.08:
                organ_hint = "daun"
            else:
                organ_hint = "tanaman_utuh"

            logger.info(
                f"[CVPreprocessor] Foto lolos inspeksi | Blur: {blur_score:.1f} | "
                f"Plant Area: {plant_coverage*100:.1f}% | Organ: {organ_hint}"
            )

            return CVQualityResult(
                is_valid=True,
                is_blurry=False,
                blur_score=round(blur_score, 2),
                is_plant=True,
                plant_coverage=round(plant_coverage, 3),
                organ_hint=organ_hint,
                rejection_reason=None
            )

        except Exception as e:
            logger.error(f"[CVPreprocessor] Terjadi kesalahan prapemrosesan: {e}", exc_info=True)
            # Fail-safe: jika ada error OpenCV internal, loloskan agar tetap bisa diproses LLM
            return CVQualityResult(
                is_valid=True,
                is_blurry=False,
                blur_score=100.0,
                is_plant=True,
                plant_coverage=0.5,
                organ_hint="umum",
                rejection_reason=None
            )
