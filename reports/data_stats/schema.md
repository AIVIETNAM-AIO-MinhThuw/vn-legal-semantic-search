# Schema dataset

- Dataset: `th1nhng0/vietnamese-legal-documents`
- Revision: `8977887f17be2defae4c5171d55562e1cde7d695`
- Config/split trên HF (theo README dataset): `metadata`/`data`, `content`/`data`, `relationships`/`data`; ngoài ra có `legacy_metadata`/`metadata` và `legacy_content`/`content` (bản cũ, schema khác, **không tải** trong phiên này).

## `metadata` — `data/metadata.parquet`

- Số dòng: 171,556
- Số row group: 35

| Cột | Kiểu Arrow |
|---|---|
| `id` | `string` |
| `title` | `string` |
| `so_ky_hieu` | `string` |
| `ngay_ban_hanh` | `string` |
| `loai_van_ban` | `string` |
| `ngay_co_hieu_luc` | `string` |
| `ngay_het_hieu_luc` | `string` |
| `nguon_thu_thap` | `string` |
| `ngay_dang_cong_bao` | `string` |
| `nganh` | `string` |
| `linh_vuc` | `string` |
| `co_quan_ban_hanh` | `string` |
| `chuc_danh` | `string` |
| `nguoi_ky` | `string` |
| `pham_vi` | `string` |
| `thong_tin_ap_dung` | `string` |
| `tinh_trang_hieu_luc` | `string` |

## `content` — `data/content.parquet`

- Số dòng: 170,824
- Số row group: 35

| Cột | Kiểu Arrow |
|---|---|
| `id` | `string` |
| `content_html` | `string` |

## `relationships` — `data/relationships.parquet`

- Số dòng: 1,033,255
- Số row group: 207

| Cột | Kiểu Arrow |
|---|---|
| `doc_id` | `string` |
| `other_doc_id` | `string` |
| `relationship` | `string` |
