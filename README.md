# Discord Bot — Toko Produk + Premium

Discord bot toko digital sederhana berbasis **discord.py** + **SQLite**.
Mendukung produk manual & otomatis (auto delivery via DM), sistem pembayaran
manual, sistem premium dengan approve manual, lock fitur khusus premium,
dan log channel terpisah untuk pembelian produk maupun premium.

Siap di-push ke **GitHub** dan deploy ke **Railway** (worker service).

---

## 1. Struktur Project

```
discord-bot/
├── bot.py             # Entrypoint bot, semua slash command + UI
├── database.py        # Lapisan SQLite (products, transactions, stock, settings, premium_users)
├── config.py          # Loader environment variables
├── requirements.txt   # Dependencies Python
├── README.md          # Dokumen ini
├── Procfile           # Deklarasi worker untuk Railway / platform Procfile-based
├── railway.json       # Konfigurasi build/deploy Railway
├── runtime.txt        # Versi Python (untuk Railway)
├── .env.example       # Contoh environment variables (copy menjadi `.env` saat development)
└── .gitignore
```

---

## 2. Environment Variables

| Variable        | Wajib | Deskripsi                                                              |
| --------------- | :---: | ---------------------------------------------------------------------- |
| `DISCORD_TOKEN` |  Ya   | Token bot Discord (dari Developer Portal → Bot → Reset Token).         |
| `OWNER_ID`      |  Ya   | Discord user ID kamu (klik kanan profil → Copy ID, butuh Developer Mode aktif). |
| `DB_PATH`       | Tidak | Path file SQLite. Default: `bot.db`.                                   |

Saat development lokal, copy `.env.example` menjadi `.env` lalu isi value-nya.
Di Railway, isi semua variable ini lewat tab **Variables**.

---

## 3. Database (SQLite)

File DB dibuat otomatis saat bot pertama kali run.

| Tabel           | Kolom utama                                                                                        |
| --------------- | -------------------------------------------------------------------------------------------------- |
| `products`      | `id, name, description, price, type, image_url, discount, created_at`                              |
| `transactions`  | `id, user_id, product_id, price, final_price, status, kind, created_at`                            |
| `stock`         | `id, product_id, content, used, used_by, used_at`                                                  |
| `settings`      | `key, value` (key/value generic — untuk payment, lock fitur, log channel, dsb.)                    |
| `premium_users` | `user_id, status, created_at, approved_at`                                                         |

> ⚠️ **Catatan storage Railway:** filesystem Railway bersifat ephemeral.
> Untuk persistensi DB SQLite, attach **Volume** di service kamu dan mount
> ke (misal) `/data`, lalu set `DB_PATH=/data/bot.db`.

---

## 4. Slash Commands

### Produk
| Command                                                                 | Akses | Deskripsi                                              |
| ----------------------------------------------------------------------- | :---: | ------------------------------------------------------ |
| `/addproduct name description price type image_url? discount?`          | Owner | Tambah produk (`type`: `manual` / `otomatis`).         |
| `/editproduct product_id [field...]`                                    | Owner | Update field produk (yang dikirim saja).               |
| `/deleteproduct product_id`                                             | Owner | Hapus produk + stock-nya.                              |
| `/products`                                                             | Semua | Lihat daftar produk (embed).                           |
| `/buy product_id`                                                       | Semua | Beli produk; tampil tombol Konfirmasi/Batal.           |
| `/setstock product_id items`                                            | Owner | Tambah stock auto (pisah dengan `\|`, contoh `a\|b\|c`). |
| `/setproductpayment name info`                                          | Owner | Set metode pembayaran produk (DANA/OVO/QRIS/dst.).     |
| `/approvetransaction transaction_id`                                    | Owner | Tandai transaksi manual sebagai PAID.                  |

### Premium
| Command                                            | Akses | Deskripsi                                                 |
| -------------------------------------------------- | :---: | --------------------------------------------------------- |
| `/setpremiumprice price`                           | Owner | Set harga premium.                                        |
| `/setpremiumpayment name info`                     | Owner | Set metode pembayaran premium (terpisah dari produk).     |
| `/buypremium`                                      | Semua | Beli akses premium → status `pending` sampai owner approve. |
| `/setpremium user status`                          | Owner | Set status premium user (`paid` / `pending` / `revoke`).  |
| `/addpremiumuser user`                             | Owner | Approve manual user jadi premium.                         |
| `/lockfeature feature locked`                      | Owner | Kunci/buka fitur untuk premium-only.                      |

### System
| Command                                  | Akses | Deskripsi                                                  |
| ---------------------------------------- | :---: | ---------------------------------------------------------- |
| `/setlogchannel kind channel`            | Owner | Set channel log (`product` atau `premium`).                |

> Semua command **owner-only** dilindungi via decorator `owner_only()`.
> User non-owner yang mencoba akan menerima embed “Akses Ditolak” (ephemeral).

---

## 5. Sistem Pembelian Produk

1. User jalankan `/buy product_id`.
2. Bot menghitung **harga setelah diskon** (`price * (100 - discount) / 100`).
3. Buat row di `transactions` dengan status `pending`.
4. **Tipe `auto`** → bot mengambil 1 row di `stock` (yang `used = 0`),
   menandai sebagai used, mengirim isi via **DM** ke pembeli, dan langsung
   set status transaksi ke `paid`.
5. **Tipe `manual`** → bot menampilkan instruksi pembayaran (dari
   `settings.product_payment*`); status tetap `pending` sampai owner
   menjalankan `/approvetransaction <id>`.
6. Setiap pembelian (dan approve) dikirim sebagai embed ke channel log produk
   (jika diset).

---

## 6. Sistem Premium

* `/setpremiumprice` & `/setpremiumpayment` → owner mengatur harga & metode
  pembayaran khusus premium (data terpisah dari payment produk).
* `/buypremium` → user lihat instruksi bayar, lalu klik tombol
  **“Saya Sudah Bayar”**. Row di `premium_users` dibuat dengan status `pending`.
* Owner **approve manual** dengan `/addpremiumuser <user>` atau
  `/setpremium <user> status:paid`.
* `/setpremium <user> status:revoke` untuk mencabut premium.
* Semua aksi premium di-log ke channel log premium (jika diset).

---

## 7. Lock Fitur (Premium-Only)

Owner bisa mengunci fitur tertentu lewat `/lockfeature feature:<x> locked:true`.
Fitur yang tersedia:

| Fitur            | Efek saat dikunci (untuk non-premium)                                          |
| ---------------- | ------------------------------------------------------------------------------ |
| `product_count`  | `/products` hanya menampilkan 5 produk pertama (premium melihat semua).        |
| `auto_delivery`  | `/buy` produk tipe auto: stock tidak dikirim, transaksi jadi `pending`.        |
| `discount`       | Diskon produk diabaikan (user bayar harga normal).                             |

Owner & user premium **selalu** bypass lock.
Saat user non-premium memicu fitur yang dikunci, bot mengirim pesan:

> **Fitur ini hanya untuk user premium**

---

## 8. Log Channel

Set channel log dengan:

```
/setlogchannel kind:produk channel:#log-pembelian
/setlogchannel kind:premium channel:#log-premium
```

* **Log produk** → setiap `/buy` (pending/paid) dan `/approvetransaction`.
* **Log premium** → setiap `/buypremium`, `/addpremiumuser`, `/setpremium`.

---

## 9. Permission

Hanya `OWNER_ID` (dari env) yang bisa:

* Add/edit/delete produk
* Set stock
* Set payment produk & premium
* Set harga premium
* Approve / revoke premium
* Approve transaksi manual
* Set log channel
* Atur lock fitur

---

## 10. Menjalankan Lokal

```bash
cd discord-bot
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # lalu isi DISCORD_TOKEN & OWNER_ID

python bot.py
```

Saat pertama login, bot otomatis **sync slash commands** secara global.
Sync global butuh waktu **hingga 1 jam** sampai muncul di semua server.
Untuk testing cepat, pakai **server testing pribadi** dan tunggu beberapa menit.

---

## 11. Deploy ke GitHub

```bash
cd discord-bot
git init
git add .
git commit -m "feat: initial discord bot"
git branch -M main
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

`.env` sudah di-ignore via `.gitignore` — jangan pernah commit token bot.

---

## 12. Deploy ke Railway

1. Buka **railway.app** → **New Project** → **Deploy from GitHub repo** →
   pilih repository hasil push di atas.
2. Setelah project terbuat, masuk ke **Variables** dan tambahkan:
   * `DISCORD_TOKEN` = token bot kamu
   * `OWNER_ID` = Discord user ID kamu
   * (opsional) `DB_PATH` = `/data/bot.db` jika kamu attach Volume di `/data`
3. (Direkomendasikan) Tab **Volumes** → **New Volume** → mount path `/data`.
   Ini menjaga `bot.db` tidak hilang saat redeploy/restart.
4. Railway akan auto-detect Python via `requirements.txt` + `runtime.txt`,
   dan menjalankan `python bot.py` (sudah dideklarasikan di
   `Procfile` & `railway.json`).
5. Cek tab **Deployments → Logs** — harus muncul:
   ```
   Bot login sebagai <NamaBot> (id=...)
   Sinkron N slash commands.
   ```

Selesai — bot siap dipakai 🎉

---

## 13. Troubleshooting

* **Slash command tidak muncul** → tunggu sync global selesai (s/d 1 jam),
  atau invite bot ke server baru. Pastikan saat invite kamu mencentang
  scope `applications.commands`.
* **`Akses Ditolak` di command yang harusnya kamu boleh** → cek `OWNER_ID`
  benar (Discord ID kamu, bukan username).
* **Auto delivery tidak mengirim DM** → user menutup DM. Cek log channel
  untuk indikatornya. Stock tetap ter-claim.
* **`bot.db` hilang setelah redeploy di Railway** → attach Volume dan set
  `DB_PATH=/data/bot.db`.
* **`Improper token has been passed`** → `DISCORD_TOKEN` salah/expired.
  Reset di Developer Portal lalu update di Variables.

