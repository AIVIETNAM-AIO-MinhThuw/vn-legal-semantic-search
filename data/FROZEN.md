# FROZEN artifacts

Hash và thời điểm freeze của các mốc theo SPEC mục 15.

| Artifact | File | SHA-256 | Thời điểm freeze | Ghi chú |
|---|---|---|---|---|
| Mốc 1 — Danh sách lĩnh vực và ánh xạ loại quan hệ (OI-10) | `configs/data.yaml` tại commit `86809e450681c121b9352e8741fca81c108876a5` | `751c3cc58342f3c6f62e99604b5147648ec1e258e0388b3f1f01238d4aec014f` | `2026-10-22T08:39:32+07:00` | Nhóm chốt trước lọc và split; SHA-256 tính trên đúng nội dung file tại commit. Các trường OI-10 hiện tại vẫn khớp bản đã freeze. |
| Mốc 2 — `splits.json` (SPEC 4.1 phương án B) | `data/splits.json` (nội dung blob Git, xuống dòng LF) | `61475224522d78f2e4fa43389c66675d62d8c892d7e41a6b6430f0a0ab6ff519` | `2026-10-24T05:38:55+07:00` | Phạm Trần Minh Thư chấp nhận kết quả split sau review; seed 42, N = 569, A = 7.340, F = 1; leakage OK (`reports/data_stats/after_filter/leakage_report.json`). SHA-256 tính trên blob LF theo `.gitattributes` (`git show :data/splits.json \| sha256sum`); file local trên Windows xuống dòng CRLF nên có hash khác (`05f649cb…1be5`). Chưa có query nào được sinh. |
