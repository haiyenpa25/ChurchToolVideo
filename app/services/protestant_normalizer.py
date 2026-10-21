"""
protestant_normalizer.py
Module chuyên trách chuẩn hóa chính tả Kinh Thánh & Từ vựng Tin Lành Việt Nam (Bản Truyền Thống RVV1925 / RVV2011).
Tự động khắc phục các lỗi nhận diện phổ biến của AI Whisper (phiên âm không gạch nối, nhầm lẫn với Công giáo, lỗi ngữ âm).
"""

import re
import unicodedata
from typing import List, Tuple, Dict, Any
from app.services.protestant_vocabulary import BIBLE_BOOKS, NAMED_TERMS

# Danh sách quy tắc chuẩn hóa: (Regex pattern, Chuỗi thay thế chuẩn Tin Lành)
# Thứ tự ưu tiên: Cụm từ dài/chi tiết trước -> Từ ngắn/đơn sau
PROTESTANT_RULES: List[Tuple[re.Pattern, str]] = [
    # ─── 1. DANH XƯNG BA NGÔI ĐỨC CHÚA TRỜI ─────────────────────────────────
    (re.compile(r"\b(?:đức\s+chúa\s+trời\s+ba\s+ngôi|ba\s+ngôi\s+đức\s+chúa\s+trời)\b", re.I), "Đức Chúa Trời Ba Ngôi"),
    (re.compile(r"\bđức\s+chúa\s+trời\b", re.I), "Đức Chúa Trời"),
    (re.compile(r"\bđức\s+chúa\s+cha\b", re.I), "Đức Chúa Cha"),
    (re.compile(r"\b(?:chúa\s+cứu\s+thế\s+giê[\s\-]xu|cứu\s+chúa\s+giê[\s\-]xu)\b", re.I), "Cứu Chúa Giê-xu"),
    (re.compile(r"\bđức\s+chúa\s+giê[\s\-]xu\s+christ\b", re.I), "Đức Chúa Giê-xu Christ"),
    (re.compile(r"\bđức\s+chúa\s+giê[\s\-]xu\b", re.I), "Đức Chúa Giê-xu"),
    (re.compile(r"\bchúa\s+giê[\s\-]xu\s+christ\b", re.I), "Chúa Giê-xu Christ"),
    (re.compile(r"\bchúa\s+giê[\s\-]xu\b", re.I), "Chúa Giê-xu"),
    (re.compile(r"\bgiê[\s\-]xu\s+christ\b", re.I), "Giê-xu Christ"),
    # Chuyển đổi tên Chúa Giê-su / Ki-tô (dạng phổ thông/Công giáo) -> Chúa Giê-xu / Đấng Christ (chuẩn Tin Lành)
    (re.compile(r"\bđức\s+chúa\s+giê[\s\-]su\s+ki[\s\-]tô\b", re.I), "Đức Chúa Giê-xu Christ"),
    (re.compile(r"\bchúa\s+giê[\s\-]su\s+ki[\s\-]tô\b", re.I), "Chúa Giê-xu Christ"),
    (re.compile(r"\bđức\s+giê[\s\-]su\s+ki[\s\-]tô\b", re.I), "Đức Chúa Giê-xu Christ"),
    (re.compile(r"\bđức\s+chúa\s+giê[\s\-]su\b", re.I), "Đức Chúa Giê-xu"),
    (re.compile(r"\bchúa\s+giê[\s\-]su\b", re.I), "Chúa Giê-xu"),
    (re.compile(r"\bgiê[\s\-]su\s+ki[\s\-]tô\b", re.I), "Giê-xu Christ"),
    (re.compile(r"\b(?:đấng|đức|chúa)\s+ki[\s\-]tô\b", re.I), "Đấng Christ"),
    (re.compile(r"\bđấng\s+christ\b", re.I), "Đấng Christ"),
    (re.compile(r"\b(?:ki[\s\-]tô\s+hữu|kitô\s+hữu|cơ\s+đốc\s+nhân)\b", re.I), "Cơ Đốc nhân"),
    (re.compile(r"\b(?:ki[\s\-]tô\s+giáo|kitô\s+giáo|cơ\s+đốc\s+giáo)\b", re.I), "Cơ Đốc giáo"),
    (re.compile(r"\bchúa\s+jesu\b", re.I), "Chúa Giê-xu"),
    (re.compile(r"\bgiê[\s\-]xu\b", re.I), "Giê-xu"),
    # Chúa Cứu Thế
    (re.compile(r"\bchúa\s+cứu\s+thế\b", re.I), "Chúa Cứu Thế"),
    # Đức Thánh Linh (thay Chúa Thánh Thần / Đức Thánh Thần)
    (re.compile(r"\b(?:chúa|đức)\s+thánh\s+thần\b", re.I), "Đức Thánh Linh"),
    (re.compile(r"\bơn\s+thánh\s+thần\b", re.I), "ơn Đức Thánh Linh"),
    (re.compile(r"\bquyền\s+năng\s+thánh\s+thần\b", re.I), "quyền năng Đức Thánh Linh"),
    (re.compile(r"\bđầy\s+dẫy\s+(?:thánh\s+thần|đức\s+thánh\s+linh)\b", re.I), "đầy dẫy Đức Thánh Linh"),
    (re.compile(r"\bđức\s+thánh\s+linh\b", re.I), "Đức Thánh Linh"),
    # Đức Giê-hô-va (thay Gia-vê)
    (re.compile(r"\bđức\s+giê[\s\-]hô[\s\-]va\b", re.I), "Đức Giê-hô-va"),
    (re.compile(r"\bgiê[\s\-]hô[\s\-]va\b", re.I), "Giê-hô-va"),
    (re.compile(r"\b(?:đức\s+chúa\s+)?gia[\s\-]vê\b", re.I), "Đức Giê-hô-va"),
    # Danh xưng Thiên Chúa theo ngữ cảnh Kinh Thánh -> Đức Chúa Trời
    (re.compile(r"\b(?:nước|vương\s+quốc)\s+thiên\s+chúa\b", re.I), "Nước Đức Chúa Trời"),
    (re.compile(r"\bcon\s+(?:thiên\s+chúa|đức\s+chúa\s+trời)\b", re.I), "Con Đức Chúa Trời"),
    (re.compile(r"\blời\s+(?:thiên\s+chúa|đức\s+chúa\s+trời)\b", re.I), "Lời Đức Chúa Trời"),
    (re.compile(r"\bchiên\s+con\s+của\s+(?:thiên\s+chúa|đức\s+chúa\s+trời)\b", re.I), "Chiên Con của Đức Chúa Trời"),

    # ─── 2. NHÂN VẬT KINH THÁNH TIN LÀNH (BẢN TRUYỀN THỐNG) ─────────────────
    # Sứ đồ Phao-lô
    (re.compile(r"\b(?:sứ|tông)\s+đồ\s+phao[\s\-]lô\b", re.I), "sứ đồ Phao-lô"),
    (re.compile(r"\bphao[\s\-]lô\b", re.I), "Phao-lô"),
    (re.compile(r"\b(?:phào|pháo)\s+lô\b", re.I), "Phao-lô"),
    # Sứ đồ Phi-e-rơ
    (re.compile(r"\b(?:sứ|tông)\s+đồ\s+(?:phi[\s\-]e[\s\-]rơ|phê[\s\-]rô)\b", re.I), "sứ đồ Phi-e-rơ"),
    (re.compile(r"\bphê[\s\-]rô\b", re.I), "Phi-e-rơ"),
    (re.compile(r"\bphi[\s\-]e[\s\-]rơ\b", re.I), "Phi-e-rơ"),
    (re.compile(r"\bphi[\s\-]ê[\s\-]rơ\b", re.I), "Phi-e-rơ"),
    (re.compile(r"\bphi\s+rơ\b", re.I), "Phi-e-rơ"),
    # Ba-na-ba
    (re.compile(r"\bba[\s\-]na[\s\-]ba\b", re.I), "Ba-na-ba"),
    (re.compile(r"\bbá\s+nạp\s+ba\b", re.I), "Ba-na-ba"),
    # Áp-ra-ham
    (re.compile(r"\báp[\s\-]ra[\s\-]ham\b", re.I), "Áp-ra-ham"),
    (re.compile(r"\babraham\b", re.I), "Áp-ra-ham"),
    # Môi-se
    (re.compile(r"\bmô[\s\-]sê\b", re.I), "Môi-se"),
    (re.compile(r"\bmôi[\s\-]se\b", re.I), "Môi-se"),
    # Đa-vít
    (re.compile(r"\bđa[\s\-]vít\b", re.I), "Đa-vít"),
    (re.compile(r"\bđavít\b", re.I), "Đa-vít"),
    # Sa-lô-môn
    (re.compile(r"\b(?:sa|xa)[\s\-]lô[\s\-]môn\b", re.I), "Sa-lô-môn"),
    # Ti-mô-thê
    (re.compile(r"\bti[\s\-]mô[\s\-]thê\b", re.I), "Ti-mô-thê"),
    # Nê-hê-mi
    (re.compile(r"\bnê[\s\-]hê[\s\-]mi\b", re.I), "Nê-hê-mi"),
    # Ê-xơ-tê
    (re.compile(r"\bê[\s\-]xơ[\s\-]tê\b", re.I), "Ê-xơ-tê"),
    (re.compile(r"\bexơtê\b", re.I), "Ê-xơ-tê"),
    # Ê-sai
    (re.compile(r"\bê[\s\-]sai\b", re.I), "Ê-sai"),
    (re.compile(r"\bisaia\b", re.I), "Ê-sai"),
    # Giê-rê-mi
    (re.compile(r"\bgiê[\s\-]rê[\s\-]mi\b", re.I), "Giê-rê-mi"),
    (re.compile(r"\bgiêrêmia\b", re.I), "Giê-rê-mi"),
    # Ê-xê-chi-ên
    (re.compile(r"\bê[\s\-]xê[\s\-]chi[\s\-]ên\b", re.I), "Ê-xê-chi-ên"),
    # Đa-ni-ên
    (re.compile(r"\bđa[\s\-]ni[\s\-]ên\b", re.I), "Đa-ni-ên"),
    # Y-sác
    (re.compile(r"\by[\s\-]sác\b", re.I), "Y-sác"),
    # Gia-cốp
    (re.compile(r"\bgia[\s\-]cốp\b", re.I), "Gia-cốp"),
    # Giô-sép
    (re.compile(r"\bgiô[\s\-]sép\b", re.I), "Giô-sép"),
    # Giô-suê
    (re.compile(r"\bgiô[\s\-]suê\b", re.I), "Giô-suê"),
    (re.compile(r"\bgiôsua\b", re.I), "Giô-suê"),
    # Ê-li & Ê-li-sê
    (re.compile(r"\bê[\s\-]li[\s\-]sê\b", re.I), "Ê-li-sê"),
    (re.compile(r"\bê[\s\-]li\b", re.I), "Ê-li"),
    # Ê-tiên
    (re.compile(r"\bê[\s\-]tiên\b", re.I), "Ê-tiên"),
    (re.compile(r"\btêphanô\b", re.I), "Ê-tiên"),
    # Si-la, A-pô-lô
    (re.compile(r"\bsi[\s\-]la\b", re.I), "Si-la"),
    (re.compile(r"\ba[\s\-]pô[\s\-]lô\b", re.I), "A-pô-lô"),
    # A-đam, Ê-va, Nô-ê
    (re.compile(r"\ba[\s\-]đam\b", re.I), "A-đam"),
    (re.compile(r"\bê[\s\-]va\b", re.I), "Ê-va"),
    (re.compile(r"\bnô[\s\-]ê\b", re.I), "Nô-ê"),
    # Các Tác Giả Tin Lành (Ma-thi-ơ, Mác, Lu-ca, Giăng)
    (re.compile(r"\bma[\s\-]thi[\s\-]ơ\b", re.I), "Ma-thi-ơ"),
    (re.compile(r"\bmát[\s\-]thêu\b", re.I), "Ma-thi-ơ"),
    (re.compile(r"\blu[\s\-]ca\b", re.I), "Lu-ca"),
    (re.compile(r"\b(?:sứ\s+đồ\s+giăng|(?:sứ|tông)\s+đồ\s+gio[\s\-]an|thánh\s+gio[\s\-]an)\b", re.I), "sứ đồ Giăng"),
    (re.compile(r"\b(?:giăng\s+báp[\s\-]tít|gio[\s\-]an\s+báp[\s\-]tít|gio[\s\-]an\s+tẩy\s+giả)\b", re.I), "Giăng Báp-tít"),
    (re.compile(r"\b(?:tin\s+lành|tin\s+mừng|phúc\s+âm)\s+(?:giăng|gio[\s\-]an)\b", re.I), "Tin Lành Giăng"),
    (re.compile(r"\b(?:tin\s+lành|tin\s+mừng|phúc\s+âm)\s+(?:ma[\s\-]thi[\s\-]ơ|mát[\s\-]thêu)\b", re.I), "Tin Lành Ma-thi-ơ"),
    (re.compile(r"\b(?:tin\s+lành|tin\s+mừng|phúc\s+âm)\s+(?:mác|mác[\s\-]cô)\b", re.I), "Tin Lành Mác"),
    (re.compile(r"\b(?:tin\s+lành|tin\s+mừng|phúc\s+âm)\s+lu[\s\-]ca\b", re.I), "Tin Lành Lu-ca"),
    (re.compile(r"\bsách\s+gio[\s\-]an\b", re.I), "sách Giăng"),
    (re.compile(r"\b(?:gia[\s\-]cơ|gia[\s\-]cô[\s\-]bê)\b", re.I), "Gia-cơ"),
    (re.compile(r"\b(?:pha[\s\-]ri[\s\-]si|pha[\s\-]ri[\s\-]sêu)\b", re.I), "Pha-ri-si"),
    (re.compile(r"\b(?:sa[\s\-]đu[\s\-]sê|sa[\s\-]đu[\s\-]kê)\b", re.I), "Sa-đu-sê"),
    (re.compile(r"\bphi[\s\-]lê[\s\-]môn\b", re.I), "Phi-lê-môn"),
    (re.compile(r"\bsa[\s\-]mu[\s\-]ên\b", re.I), "Sa-mu-ên"),
    (re.compile(r"\bgióp\b", re.I), "Gióp"),
    (re.compile(r"\bru[\s\-]tơ\b", re.I), "Ru-tơ"),
    (re.compile(r"\bsa[\s\-]tan\b", re.I), "Sa-tan"),
    (re.compile(r"\b(?:xa\s+tan|sa\s+tăng)\b", re.I), "Sa-tan"),

    # ─── 3. ĐỊA DANH KINH THÁNH ──────────────────────────────────────────────
    (re.compile(r"\bdân\s+(?:y[\s\-]sơ[\s\-]ra[\s\-]ên|i[\s\-]xra[\s\-]en|ít[\s\-]ra[\s\-]en|israel)\b", re.I), "dân Y-sơ-ra-ên"),
    (re.compile(r"\b(?:i[\s\-]xra[\s\-]en|ít[\s\-]ra[\s\-]en)\b", re.I), "Y-sơ-ra-ên"),
    (re.compile(r"\bgiê[\s\-]ru[\s\-][sx]a[\s\-]lem\b", re.I), "Giê-ru-sa-lem"),
    (re.compile(r"\bbết[\s\-]lê[\s\-]hem\b", re.I), "Bết-lê-hem"),
    (re.compile(r"\bbê\s+lem\b", re.I), "Bết-lê-hem"),
    (re.compile(r"\bna[\s\-]xa[\s\-]rét\b", re.I), "Na-xa-rét"),
    (re.compile(r"\bga[\s\-]li[\s\-]lê\b", re.I), "Ga-li-lê"),
    (re.compile(r"\bca[\s\-]bê[\s\-]na[\s\-]um\b", re.I), "Ca-bê-na-um"),
    (re.compile(r"\bgô[\s\-]gô[\s\-]tha\b", re.I), "Gô-gô-tha"),
    (re.compile(r"\bđồi\s+can[\s\-]vê\b", re.I), "Đồi Gô-gô-tha"),
    (re.compile(r"\bvườn\s+(?:gết|ghết)[\s\-]sê[\s\-]ma[\s\-]nê\b", re.I), "Vườn Gết-sê-ma-nê"),
    (re.compile(r"\b(?:gết|ghết)[\s\-]sê[\s\-]ma[\s\-]nê\b", re.I), "Gết-sê-ma-nê"),
    (re.compile(r"\bnúi\s+si[\s\-]na[\s\-]i\b", re.I), "Núi Si-na-i"),
    (re.compile(r"\bsông\s+giô[\s\-]đanh\b", re.I), "Sông Giô-đanh"),
    (re.compile(r"\ban[\s\-]ti[\s\-]ốt\b", re.I), "An-ti-ốt"),
    (re.compile(r"\bê[\s\-]díp[\s\-]tô\b", re.I), "Ê-díp-tô"),
    (re.compile(r"\bba[\s\-]by[\s\-]lôn\b", re.I), "Ba-by-lôn"),
    (re.compile(r"\bê[\s\-]phê[\s\-]sô\b", re.I), "Ê-phê-sô"),
    (re.compile(r"\bcô[\s\-]rinh[\s\-]tô\b", re.I), "Cô-rinh-tô"),
    (re.compile(r"\bga[\s\-]la[\s\-]ti\b", re.I), "Ga-la-ti"),
    (re.compile(r"\bphi[\s\-]líp\b", re.I), "Phi-líp"),
    (re.compile(r"\bcô[\s\-]lô[\s\-]se\b", re.I), "Cô-lô-se"),
    (re.compile(r"\btê[\s\-]sa[\s\-]lô[\s\-]ni[\s\-]ca\b", re.I), "Tê-sa-lô-ni-ca"),
    (re.compile(r"\bbê[\s\-]tha[\s\-]ni\b", re.I), "Bê-tha-ni"),
    (re.compile(r"\bsô[\s\-]đôm\b", re.I), "Sô-đôm"),
    (re.compile(r"\bgô[\s\-]mô[\s\-]rơ\b", re.I), "Gô-mô-rơ"),
    (re.compile(r"\bca[\s\-]na[\s\-]an\b", re.I), "Ca-na-an"),
    (re.compile(r"\bđất\s+hứa\b", re.I), "Đất Hứa"),
    (re.compile(r"\bbiển\s+chết\b", re.I), "Biển Chết"),
    (re.compile(r"\bnúi\s+cạt[\s\-]mên\b", re.I), "Núi Cạt-mên"),

    # ─── 4. MỤC LỤC KINH THÁNH ──────────────────────────────────────────────
    (re.compile(r"\bsáng\s+thế\s+ký\b", re.I), "Sáng Thế Ký"),
    (re.compile(r"\bxuất\s+ê[\s\-]díp[\s\-]tô\s+ký\b", re.I), "Xuất Ê-díp-tô Ký"),
    (re.compile(r"\bsách\s+xuất\s+hành\b", re.I), "sách Xuất Ê-díp-tô Ký"),
    (re.compile(r"\blê[\s\-]vi\s+ký\b", re.I), "Lê-vi Ký"),
    (re.compile(r"\bdân\s+số\s+ký\b", re.I), "Dân Số Ký"),
    (re.compile(r"\bphục\s+truyền\s+luật\s+lệ\s+ký\b", re.I), "Phục Truyền Luật Lệ Ký"),
    (re.compile(r"\bphục\s+truyền\b", re.I), "Phục Truyền"),
    (re.compile(r"\bcác\s+quan\s+xét\b", re.I), "Các Quan Xét"),
    (re.compile(r"\bnhã\s+ca\b", re.I), "Nhã Ca"),
    (re.compile(r"\bca\s+thương\b", re.I), "Ca Thương"),
    (re.compile(r"\bthi\s+thiên\b", re.I), "Thi Thiên"),
    (re.compile(r"\bthánh\s+thi\b", re.I), "Thi Thiên"),
    (re.compile(r"\bchâm\s+ngôn\b", re.I), "Châm Ngôn"),
    (re.compile(r"\bcông\s+vụ\s+các\s+(?:sứ|tông)\s+đồ\b", re.I), "Công Vụ Các Sứ Đồ"),
    (re.compile(r"\bcông\s+vụ\b", re.I), "Công Vụ"),
    (re.compile(r"\bhê[\s\-]bơ[\s\-]rơ\b", re.I), "Hê-bơ-rơ"),
    (re.compile(r"\bsách\s+khải\s+thị\b", re.I), "sách Khải Huyền"),
    (re.compile(r"\bkhải\s+huyền\b", re.I), "Khải Huyền"),
    (re.compile(r"\bcựu\s+ước\b", re.I), "Cựu Ước"),
    (re.compile(r"\btân\s+ước\b", re.I), "Tân Ước"),

    # ─── 5. GIÁO LÝ, BÍ TÍCH & NGHI LỄ TIN LÀNH ─────────────────────────────
    # Lễ Báp-têm (thay Phép rửa tội)
    (re.compile(r"\blễ\s+báp[\s\-]têm\b", re.I), "Lễ Báp-têm"),
    (re.compile(r"\bphép\s+báp[\s\-]têm\b", re.I), "phép Báp-têm"),
    (re.compile(r"\bbáp[\s\-]têm\b", re.I), "Báp-têm"),
    (re.compile(r"\bbáp[\s\-]tem\b", re.I), "Báp-têm"),
    # Tiệc Thánh
    (re.compile(r"\blễ\s+tiệc\s+thánh\b", re.I), "Lễ Tiệc Thánh"),
    (re.compile(r"\btiệc\s+thánh\b", re.I), "Tiệc Thánh"),
    # Giảng luận (sửa các lỗi nghe nhầm của Whisper)
    (re.compile(r"\bgiảng\s+(?:lựng|loạn|lận)\b", re.I), "giảng luận"),
    (re.compile(r"\bbài\s+giảng\s+(?:lựng|loạn|lận)\b", re.I), "bài giảng luận"),
    (re.compile(r"\bgiảng\s+luận\b", re.I), "giảng luận"),
    (re.compile(r"\bbài\s+giảng\s+luận\b", re.I), "bài giảng luận"),
    # Ân Điển & Cứu Rỗi (sửa lỗi dấu hỏi/ngã)
    (re.compile(r"\bân\s+(?:điền|điện)\b", re.I), "ân điển"),
    (re.compile(r"\bân\s+điển\b", re.I), "ân điển"),
    (re.compile(r"\bsự\s+cứu\s+(?:rối|rổi)\b", re.I), "sự cứu rỗi"),
    (re.compile(r"\bcứu\s+(?:rối|rổi)\b", re.I), "cứu rỗi"),
    # Xưng Công Bình & Tái Sanh
    (re.compile(r"\bxưng\s+công\s+chính\b", re.I), "xưng công bình"),
    (re.compile(r"\bxưng\s+công\s+bình\b", re.I), "xưng công bình"),
    (re.compile(r"\btái\s+sanh\b", re.I), "tái sanh"),
    # Tái Lâm, Nước Đức Chúa Trời
    (re.compile(r"\bsự\s+tái\s+lâm\b", re.I), "sự Tái Lâm"),
    (re.compile(r"\bnước\s+đức\s+chúa\s+trời\b", re.I), "Nước Đức Chúa Trời"),
    (re.compile(r"\bsự\s+sống\s+đời\s+đời\b", re.I), "sự sống đời đời"),

    # ─── 6. TỔ CHỨC & CHỨC VỤ HỘI THÁNH TIN LÀNH ────────────────────────────
    (re.compile(r"\bhội\s+thánh\s+tin\s+lành\b", re.I), "Hội Thánh Tin Lành"),
    (re.compile(r"\bchi\s+hội\b", re.I), "Chi Hội"),
    (re.compile(r"\bđiểm\s+nhóm\b", re.I), "Điểm Nhóm"),
    (re.compile(r"\bphòng\s+nhóm\b", re.I), "Phòng Nhóm"),
    (re.compile(r"\bmục\s+sư\s+quản\s+nhiệm\b", re.I), "Mục sư Quản nhiệm"),
    (re.compile(r"\bmục\s+sư\s+nhiệm\s+chức\b", re.I), "Mục sư Nhiệm chức"),
    (re.compile(r"\bmục\s+sư\b", re.I), "Mục sư"),
    (re.compile(r"\bban\s+chấp\s+sự\b", re.I), "Ban Chấp sự"),
    (re.compile(r"\bban\s+trị\s+sự\b", re.I), "Ban Trị sự"),
    (re.compile(r"\bchấp\s+sự\b", re.I), "Chấp sự"),
    (re.compile(r"\btrưởng\s+lão\b", re.I), "Trưởng lão"),
    (re.compile(r"\bban\s+thờ\s+phượng\b", re.I), "Ban Thờ Phượng"),
    (re.compile(r"\bban\s+hát\b", re.I), "Ban Hát"),
    (re.compile(r"\btrường\s+chúa\s+nhật\b", re.I), "Trường Chúa Nhật"),
    (re.compile(r"\bkinh\s+thánh\s+hè\b", re.I), "Kinh Thánh Hè"),

    # ─── 7. LỜI CHÀO & TÔN VINH (AMEN, HALELUJAH) ───────────────────────────
    (re.compile(r"\b(?:ha[\s\-]lê[\s\-]lu[\s\-]gia|hallelujah|alleluia|haleluia)\b", re.I), "Ha-lê-lu-gia"),
    (re.compile(r"\b(?:a[\s\-]men|amen)\b", re.I), "A-men"),
    (re.compile(r"\bkinh\s+thánh\b", re.I), "Kinh Thánh"),
    (re.compile(r"\blời\s+chúa\b", re.I), "Lời Chúa"),
    (re.compile(r"\bphúc\s+âm\b", re.I), "Phúc Âm")
]


def _spelling_pattern(term):
    # Spaces and common Unicode hyphens are equivalent, but never consume SRT line breaks.
    tokens = re.split(r"[ -]+", term)
    return re.compile(r"\b" + r"[ \t\-\u2010\u2011\u2013\u2014]+".join(map(re.escape,tokens)) + r"\b",re.I)


# Longer names/book titles win over their embedded short names.
# Keep single common words (e.g. "mác", "tít") out of global case conversion.
_extended = [( _spelling_pattern(t),t) for t in dict.fromkeys((*BIBLE_BOOKS,*NAMED_TERMS))
             if (' ' in t or '-' in t) and t != 'Truyền Đạo']
_extended.sort(key=lambda rule:len(rule[1]),reverse=True)
for term in BIBLE_BOOKS:
    if term == 'Truyền Đạo' or (' ' not in term and '-' not in term):
        body=_spelling_pattern(term).pattern
        _extended.insert(0,(re.compile(r'(?<=sách )'+body,re.I),term))
        _extended.insert(0,(re.compile(body+r'(?=[ \t]+\d)',re.I),term))
PROTESTANT_RULES = _extended + PROTESTANT_RULES
PROTESTANT_RULES = [(re.compile(p.pattern.replace(r'[\s\-]',r'[ \t\-]').replace(r'\s',r'[ \t]'),re.I),t)
                    for p,t in PROTESTANT_RULES]
PROTESTANT_RULES.sort(key=lambda rule:len(rule[1]),reverse=True)
_combined_rules = re.compile('|'.join(f'(?P<R{i}>{p.pattern})' for i,(p,_) in enumerate(PROTESTANT_RULES)),re.I)


def normalize_protestant_text(text: str) -> Tuple[str, int]:
    """
    Chuẩn hóa chuỗi văn bản theo chính tả Tin Lành Bản Truyền Thống.
    Trả về: (text_đã_chuẩn_hóa, số_lượng_từ_đã_thay_thế)
    """
    if not text:
        return text, 0

    normalized = unicodedata.normalize('NFC',text)
    total_replacements = int(normalized != text)
    def replace(match):
        nonlocal total_replacements
        replacement = PROTESTANT_RULES[int(match.lastgroup[1:])][1]
        if match.group() != replacement:
            total_replacements += 1
        return replacement
    return _combined_rules.sub(replace,normalized), total_replacements


def normalize_subtitle_items(subtitle_items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Chuẩn hóa toàn bộ danh sách phân đoạn phụ đề.
    Cập nhật trường 'text' của từng item và đếm tổng số thay thế.
    """
    total_changes = 0
    for item in subtitle_items:
        old_text = item.get("text", "")
        new_text, changes = normalize_protestant_text(old_text)
        if changes > 0:
            item["text"] = new_text
            total_changes += changes

    return subtitle_items, total_changes


def get_core_hotwords_prompt() -> str:
    """
    Tạo chuỗi Hotwords tối ưu cao độ dành cho Whisper (dưới 200 token),
    bao gồm các từ khóa định hình bối cảnh đức tin Tin Lành.
    """
    return (
        "Đức Chúa Trời, Chúa Giê-xu Christ, Đức Thánh Linh, Đức Giê-hô-va, Kinh Thánh, "
        "Phao-lô, Phi-e-rơ, Môi-se, Áp-ra-ham, Đa-vít, Giăng, Giu-đa, Y-sơ-ra-ên, "
        "ân điển, cứu rỗi, Báp-têm, Tiệc Thánh, Thi Thiên, Rô-ma, A-men."
    )
