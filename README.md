# 🎮 Free Fire Info API (HK345)

Free Fire player information API with multi-region support.
Get player name, UID, level, likes, and active status from multiple Free Fire servers.

---

## 🌍 Supported Regions

| Region | Code | Server | Token File | Status |
|--------|------|--------|-----------|--------|
| Bangladesh | `BD` | `clientbp.ggpolarbear.com` | `token_bd.json` | ✅ Active |
| India | `IND` | `client.ind.freefiremobile.com` | `token_ind.json` | ✅ Active |
| Indonesia | `ID` | `client.id.freefiremobile.com` | `token_id.json` | ⏳ Needs token |
| Pakistan | `PK` | `client.pk.freefiremobile.com` | `token_pk.json` | ⏳ Needs token |
| South America | `SA` | `client.us.freefiremobile.com` | `token_sa.json` | ⏳ Needs token |
| Singapore | `SG` | `client.sg.freefiremobile.com` | `token_sg.json` | ⏳ Needs token |

> ⚠️ **Note:** A region only works if its `token_<region>.json` file contains **real** valid tokens. Empty token files are automatically skipped (no crash).

---

## 🔑 API Key
