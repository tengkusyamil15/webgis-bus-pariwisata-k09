import pandas as pd
import json

# 1. Baca CSV mentah (bersihkan karakter escape jika ada)
with open('gps_mentah.csv', 'r', encoding='utf-8', errors='ignore') as f:
    raw_lines = [line.replace('\\_', '_').strip() for line in f if 'trip' in line or line.startswith('1,')]

from io import StringIO
df = pd.read_csv(StringIO('\n'.join(raw_lines)))
df.columns = [c.strip() for c in df.columns]

# 2. Hapus duplikat dan baris kosong
df = df.drop_duplicates().dropna().reset_index(drop=True)
df['waktu'] = pd.to_datetime(df['waktu'])
df['kecepatan_kmh'] = df['kecepatan_kmh'].astype(float)
df['jarak_km'] = df['jarak_km'].astype(float)
df['latitude'] = df['latitude'].astype(float)
df['longitude'] = df['longitude'].astype(float)

# 3. Model Konsumsi Bahan Bakar (Fleet Engineering Rationale):
# - Armada: Big Bus Pariwisata (Mesin Diesel 7.000 - 12.000 cc, AC Denso kabin selalu aktif)
# - Bahan Bakar: Pertamina Dexlite (Rp 13.000 / Liter)
# - Konsumsi Idle: 2.0 Liter/jam (beban kompresor AC ganda terus berputar saat mesin stasioner)
#   Per interval waypoint 30 detik = 2.0 * (30 / 3600) = 0.016667 Liter
# - Efisiensi Jelajah Bergerak (Cruising Efficiency): 126.71 km / 36.79 L = 3.444 km/L
# - Efisiensi Riil Gabungan (dengan 36 menit idle macet): 126.71 km / 38.0 L = 3.34 km/L
MOVING_EFFICIENCY_KM_PER_L = 126.71 / 36.79  # ~3.444 km/L
IDLE_RATE_L_PER_HOUR = 2.0                   # 2.0 Liter/jam dengan AC aktif

def hitung_bensin(row):
    if row['kecepatan_kmh'] == 0:
        return IDLE_RATE_L_PER_HOUR * (30.0 / 3600.0)  # 0.01667 L per 30 detik idle
    else:
        return row['jarak_km'] / MOVING_EFFICIENCY_KM_PER_L

df['fuel_liter'] = df.apply(hitung_bensin, axis=1)

# Klasifikasi status kecepatan & lalu lintas
# Idle: 0 km/h | Macet/Pelan: 1 - 25 km/h | Lancar: > 25 km/h
df['status'] = df['kecepatan_kmh'].apply(
    lambda v: 'Idle' if v == 0 else ('Macet/Pelan' if v <= 25 else 'Lancar')
)

# Hitung kumulatif
df['jarak_kumulatif_km'] = df['jarak_km'].cumsum().round(2)
df['fuel_kumulatif_liter'] = df['fuel_liter'].cumsum().round(2)
df['waktu_str'] = df['waktu'].dt.strftime('%H:%M:%S')

# 4. Export ke JSON untuk Front-End WebGIS
records = df[['waktu_str', 'latitude', 'longitude', 'kecepatan_kmh', 'jarak_km', 
              'jarak_kumulatif_km', 'fuel_liter', 'fuel_kumulatif_liter', 'status']].to_dict(orient='records')

with open('data_gps.json', 'w', encoding='utf-8') as f:
    json.dump(records, f, indent=2)

print("=" * 60)
print("PREPROCESSING TELEMATIKA BUS K-09 SELESAI!")
print(f"Total Data Waypoint : {len(records)} titik")
print(f"Total Jarak Tempuh  : {df['jarak_km'].sum():.2f} km")
print(f"Total Konsumsi BBM  : {df['fuel_liter'].sum():.2f} Liter")
print(f"Konsumsi Saat Idle  : {df[df['kecepatan_kmh'] == 0]['fuel_liter'].sum():.2f} Liter ({len(df[df['kecepatan_kmh'] == 0])} titik = 36 menit)")
print(f"Efisiensi Riil      : {(df['jarak_km'].sum() / df['fuel_liter'].sum()):.2f} km/Liter")
print("=" * 60)