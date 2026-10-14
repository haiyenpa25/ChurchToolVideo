"""Project spelling reference; sources and editorial limits are documented in docs/QA_PM.md."""

BIBLE_BOOKS = (
    'Sáng Thế Ký', 'Xuất Ê-díp-tô Ký', 'Lê-vi Ký', 'Dân Số Ký',
    'Phục Truyền Luật Lệ Ký', 'Giô-suê', 'Các Quan Xét', 'Ru-tơ',
    'I Sa-mu-ên', 'II Sa-mu-ên', 'I Các Vua', 'II Các Vua', 'I Sử Ký', 'II Sử Ký',
    'E-xơ-ra', 'Nê-hê-mi', 'Ê-xơ-tê', 'Gióp', 'Thi Thiên', 'Châm Ngôn',
    'Truyền Đạo', 'Nhã Ca', 'Ê-sai', 'Giê-rê-mi', 'Ca Thương', 'Ê-xê-chi-ên',
    'Đa-ni-ên', 'Ô-sê', 'Giô-ên', 'A-mốt', 'Áp-đia', 'Giô-na', 'Mi-chê',
    'Na-hum', 'Ha-ba-cúc', 'Sô-phô-ni', 'A-ghê', 'Xa-cha-ri', 'Ma-la-chi',
    'Ma-thi-ơ', 'Mác', 'Lu-ca', 'Giăng', 'Công Vụ Các Sứ Đồ', 'Rô-ma',
    'I Cô-rinh-tô', 'II Cô-rinh-tô', 'Ga-la-ti', 'Ê-phê-sô', 'Phi-líp', 'Cô-lô-se',
    'I Tê-sa-lô-ni-ca', 'II Tê-sa-lô-ni-ca', 'I Ti-mô-thê', 'II Ti-mô-thê',
    'Tít', 'Phi-lê-môn', 'Hê-bơ-rơ', 'Gia-cơ', 'I Phi-e-rơ', 'II Phi-e-rơ',
    'I Giăng', 'II Giăng', 'III Giăng', 'Giu-đe', 'Khải Huyền',
)

NAMED_TERMS = (
    'Đức Chúa Trời', 'Đức Chúa Cha', 'Chúa Giê-xu Christ', 'Đức Thánh Linh',
    'Đức Giê-hô-va', 'Phao-lô', 'Phi-e-rơ', 'Ba-na-ba', 'Môi-se', 'Áp-ra-ham',
    'Đa-vít', 'Sa-lô-môn', 'Y-sác', 'Gia-cốp', 'Giô-sép', 'Ê-li-sê', 'Ê-li',
    'Ê-tiên', 'Si-la', 'A-pô-lô', 'A-đam', 'Ê-va', 'Nô-ê', 'Sa-mu-ên',
    'Giăng Báp-tít', 'Giu-đa', 'Giu-đa Ích-ca-ri-ốt', 'Si-môn', 'Anh-rê',
    'Phi-líp', 'Na-tha-na-ên', 'Thô-ma', 'Ma-ri', 'Ma-ri Ma-đơ-len', 'Mác',
    'La-xa-rơ', 'Ma-thê', 'Xa-chê', 'Ni-cô-đem', 'Bô-ô', 'Na-ô-mi',
    'A-rôn', 'Ca-lép', 'Ghê-đê-ôn', 'Sam-sôn', 'Ê-nóc', 'Mên-chi-xê-đéc',
    'Giê-ru-sa-lem', 'Bết-lê-hem', 'Na-xa-rét', 'Ga-li-lê', 'Ca-bê-na-um',
    'Gô-gô-tha', 'Gết-sê-ma-nê', 'Si-na-i', 'Giô-đanh', 'An-ti-ốt',
    'Ê-díp-tô', 'Ba-by-lôn', 'Bê-tha-ni', 'Sô-đôm', 'Gô-mô-rơ', 'Ca-na-an',
    'Y-sơ-ra-ên', 'Giu-đê', 'Sa-ma-ri', 'Giê-ri-cô', 'Bê-tên', 'Cạt-mên',
    'Báp-têm', 'Tiệc Thánh', 'Ha-lê-lu-gia', 'A-men', 'Kinh Thánh',
    'Lời Chúa', 'Cựu Ước', 'Tân Ước', 'Phúc Âm', 'Hội Thánh Tin Lành',
)

# Reference vocabulary aids recognition/review; these common words are not global replacements.
REFERENCE_TERMS = (
    'ân điển', 'sự cứu rỗi', 'cứu chuộc', 'xưng công bình', 'tái sanh',
    'thánh hóa', 'nên thánh', 'ăn năn', 'đức tin', 'sự tha thứ',
    'sự phục sinh', 'sự sống đời đời', 'sự tái lâm', 'sự thăng thiên',
    'giao ước', 'sự chuộc tội', 'thập tự giá', 'huyết của Đấng Christ',
    'trái Thánh Linh', 'ân tứ thuộc linh', 'sự thông công', 'sự cầu nguyện',
    'thờ phượng', 'ngợi khen', 'tôn vinh', 'truyền giảng', 'truyền giáo',
    'môn đồ', 'môn đệ hóa', 'tín hữu', 'tân tín hữu', 'con dân Chúa',
    'mục vụ', 'Mục sư', 'Truyền đạo', 'Chấp sự', 'Trưởng lão',
    'Trường Chúa Nhật', 'Thánh Kinh Căn Bản', 'giáo lý Báp-têm',
)


def reference_terms():
    return list(dict.fromkeys((*NAMED_TERMS, *BIBLE_BOOKS, *REFERENCE_TERMS)))
