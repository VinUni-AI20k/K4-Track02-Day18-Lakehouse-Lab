# Evidence Summary

| Notebook | Ket qua thuc thi | Dien giai |
|---|---|---|
| NB1 Delta basics | Transaction log co commit; bad write `age='thirty'` bi chan; `tier` duoc them bang schema merge | Delta log tao lich su giao dich, schema enforcement ngan du lieu sai kieu, con evolution chi xay ra khi opt-in. |
| NB2 Optimize/Z-order | 200 -> 55 files; speedup 8.0x; pruning 55.0x, chi 1/55 file chua `user_id=4242` | Compaction giam overhead file; Z-order thu hep min/max range nen engine bo qua 54 file. Wall-clock co the dao dong, pruning la bang chung on dinh hon. |
| NB3 Time travel | MERGE 100K rows; 5 versions gom MERGE va RESTORE; `score < 0` con 0 dong | RESTORE tao mot transaction moi thay vi xoa lich su, nen van audit va time travel duoc cac version cu. |
| NB4 Medallion | Bronze 200,000; Silver 190,052; Gold 24 dong tren 8 ngay va 3 model | Bronze giu raw, Silver loai 9,948 ban trung, Gold cung cap p50/p95, error rate va cost cho truy van nghiep vu. |
| NB5 Iceberg catalog | Hidden-partition pruning 10x; field ID 4 duoc giu khi rename; spec IDs `[1, 2]`; 5,500 rows doc duoc | Filter tren `ts` duoc bien doi sang partition day ma nguoi dung khong can viet cot partition; field ID tach dinh danh khoi ten cot. |
| NB6 Maintenance | Compaction 200 -> 11 files; clustering skip >= 50%; vacuum thu hoi bytes; 3 Delta orphan bi xoa; Iceberg con 3 snapshots; checkpoint duoc tao | Expiry va orphan sweep la hai buoc rieng trong stack cua lab; maintenance phai do ca metadata reference va file vat ly. |
| NB7 Vectors/multimodal | Random-read amplification 200x; int8 nho hon 5.8x; recall@10 0.904; topic fidelity 1.000; stale index con 8 hits trong khi bang co 0 | Quantization tiet kiem storage voi chat luong truy hoi chap nhan duoc, nhung delete phai duoc dong bo qua CDF toi moi external index. |
| NB8 Agents/provenance | Silver co 2 partition policy; replay version 0 khop 1,578 steps; 5 turns chi 1 catalog read; 4 bucket co partition va loai `UNCLASSIFIED` | Pin table version tao kha nang tai lap; provenance can duoc ghi tu ingest. MCP trong lab chi la mo phong offline, khong phai server production. |

Anh tuong ung nam trong `submission/screenshots/`; notebook day du output nam trong
`submission/notebooks/`.

## Luu y khi doc NB6

- Dong dry-run hien `0 B` do danh sach tu `vacuum(dry_run=True)` khong duoc resolve
  dung khi tinh kich thuoc. Bang chung thu hoi dung la so byte cua toan bang truoc
  va sau vacuum: data giam tu 16.1 MB xuong 6.2 MB, trong khi 100,000 dong van con.
- Hai file checkpoint Parquet nam trong `_delta_log` khong phai orphan. Phep quet
  orphan co loai `_delta_log`, ap dung age guard va tim/xoa dung 3 file da cay.

Bang chung reproducibility nam tai [VERIFICATION.md](VERIFICATION.md).
