# Reflection

Anti-pattern toi quan tam nhat la **small files khong co maintenance**. Voi he
thong LLM observability, moi request co the duoc ghi boi mot micro-batch rat nho.
Du lieu van dung ve mat logic, nhung hang tram nghin file nho lam tang chi phi
listing, mo file va doc metadata; latency truy van tang nhanh hon dung luong du
lieu. Ket qua NB2 va NB6 cho thay compaction giam ro ret so file, con clustering
lam min/max statistics huu ich cho file skipping.

De phong tranh, toi se dat SLO cho kich thuoc va so luong file, theo doi cac chi
so nay theo partition, va chay compaction/clustering dinh ky voi nguong kich
hoat ro rang. Vacuum, snapshot expiry va orphan removal phai co retention an
toan, duoc do truoc/sau va co canh bao khi reader cu van con hoat dong. Nhu vay,
maintenance tro thanh mot phan cua pipeline van hanh thay vi mot tac vu xu ly su
co.

Pham vi ho tro AI duoc khai bao tai [AI_USAGE.md](AI_USAGE.md).
