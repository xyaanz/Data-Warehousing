"""
Peta sebaran Jawa Timur (Leaflet + Leaflet.markercluster).

Satu gelembung = satu kabupaten/kota. Gelembung yang berdekatan menyatu saat peta
di-zoom out (jumlahnya dijumlahkan) dan terpecah lagi saat di-zoom in.

Data batas wilayah: data/jatim_kabkota.geojson
  Sumber  : Badan Pusat Statistik (BPS), World Food Programme, OCHA ROAP,
            disebarkan melalui geoBoundaries (gbOpen, IDN ADM2, tahun batas 2020).
  Lisensi : Creative Commons Attribution 3.0 IGO (CC BY 3.0 IGO).
  Catatan : geometri sudah disederhanakan agar ringan. Properti lat/lon adalah titik
            gelembung, dihitung dari bagian daratan terbesar tiap wilayah.

Data yang ditampilkan adalah agregat per kabupaten/kota, bukan titik lokasi sekolah.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

GEOJSON_PATH = Path(__file__).parent / "data" / "jatim_kabkota.geojson"
ATRIBUSI_BATAS = "Batas wilayah: BPS, WFP, OCHA ROAP via geoBoundaries (CC BY 3.0 IGO)"

# Versi pustaka dipatok agar tampilan tidak berubah sewaktu CDN memperbarui paket
LEAFLET_VER = "1.9.4"
CLUSTER_VER = "1.5.3"


@lru_cache(maxsize=1)
def muat_geojson():
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def titik_wilayah(geojson):
    """{nama kabupaten/kota: (lat, lon)} untuk penempatan gelembung."""
    return {
        f["properties"]["kabupaten_kota"]: (f["properties"]["lat"], f["properties"]["lon"])
        for f in geojson["features"]
    }


def ambang_tiga_kelas(nilai):
    """Batas bawah kelas 'magenta' dan 'merah' (sepertiga dan dua pertiga terurut)."""
    v = sorted(float(x) for x in nilai)
    n = len(v)
    return v[n // 3], v[(2 * n) // 3]


def _js(obj):
    """JSON aman untuk disisipkan di dalam <script> (menetralkan </script> dan sejenisnya)."""
    teks = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return teks.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@__LV__/dist/leaflet.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@__CV__/dist/MarkerCluster.css">
<style>
  html, body, #peta { height: 100%; margin: 0; }
  body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  .bub-wrap { background: transparent; border: 0; }
  .bub { width: 100%; height: 100%; box-sizing: border-box; border-radius: 50%;
         display: flex; align-items: center; justify-content: center;
         color: #fff; font-weight: 700; font-size: 13px; text-shadow: 0 1px 2px rgba(0,0,0,.4); }
  .bub.ungu    { background: #8b5cf6; box-shadow: 0 0 0 6px rgba(139,92,246,.35); }
  .bub.magenta { background: #d946ef; box-shadow: 0 0 0 6px rgba(217,70,239,.35); }
  .bub.merah   { background: #f43f5e; box-shadow: 0 0 0 6px rgba(244,63,94,.35); }
  .legenda { background: rgba(255,255,255,.95); color: #1f2937; padding: 8px 10px; max-width: 230px;
             border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.3); font-size: 12px; line-height: 1.55; }
  .legenda .baris { display: flex; align-items: center; gap: 6px; }
  .legenda .kotak { width: 12px; height: 12px; border-radius: 50%; flex: none; }
  .legenda .grad { height: 10px; border-radius: 3px; margin: 3px 0 1px; }
  .legenda .ket { color: #6b7280; margin-top: 4px; }
  .legenda .skala { display: flex; justify-content: space-between; color: #4b5563; }
</style>
</head>
<body>
<div id="peta"></div>
<script src="https://unpkg.com/leaflet@__LV__/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@__CV__/dist/leaflet.markercluster.js"></script>
<script>
const DATA = __DATA__;
const GEO = __GEO__;
const CFG = __CFG__;

const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const id = n => Number(n).toLocaleString('id-ID');
function singkat(v) {
  if (v >= 1e6) return (v / 1e6).toFixed(1).replace('.', ',') + ' jt';
  if (v >= 1e4) return Math.round(v / 1e3) + ' rb';
  return id(v);
}

// ---- peta dasar ----
// zoom bulat (tanpa zoomSnap pecahan) agar ubin peta tidak menampilkan garis sambungan
const map = L.map('peta', {scrollWheelZoom: false, minZoom: 6, maxZoom: 15});
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors | ' + esc(CFG.atribusi)
}).addTo(map);
// zoom dengan roda mouse baru aktif setelah peta diklik, agar tidak mengganggu scroll halaman
map.on('click', () => map.scrollWheelZoom.enable());
map.getContainer().addEventListener('mouseleave', () => map.scrollWheelZoom.disable());

// ---- warna wilayah menurut IPM (opsional) ----
const STOPS = ['#ffffcc', '#c2e699', '#78c679', '#31a354', '#006837'];
const rgb = h => [1, 3, 5].map(i => parseInt(h.substr(i, 2), 16));
function warna(t) {
  t = Math.max(0, Math.min(1, t));
  const x = t * (STOPS.length - 1), i = Math.min(Math.floor(x), STOPS.length - 2), f = x - i;
  const a = rgb(STOPS[i]), b = rgb(STOPS[i + 1]);
  return 'rgb(' + a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(',') + ')';
}
const rentang = (CFG.ipmMax - CFG.ipmMin) || 1;
const isi = nama => (CFG.warnaIpm && CFG.ipm[nama] != null) ? warna((CFG.ipm[nama] - CFG.ipmMin) / rentang) : '#3b82f6';

// ---- batas kabupaten/kota ----
const terpilih = new Set(DATA.map(d => d.nama));
L.geoJSON(GEO, {
  style: f => {
    const aktif = terpilih.has(f.properties.kabupaten_kota);
    return {
      color: '#2563eb', weight: aktif ? 1.8 : 1, opacity: aktif ? 0.95 : 0.45,
      fillColor: isi(f.properties.kabupaten_kota),
      fillOpacity: CFG.warnaIpm ? (aktif ? 0.6 : 0.2) : (aktif ? 0.05 : 0)
    };
  },
  onEachFeature: (f, layer) => {
    const n = f.properties.kabupaten_kota;
    const ipm = (CFG.warnaIpm && CFG.ipm[n] != null) ? '<br>IPM ' + CFG.ipm[n].toFixed(2).replace('.', ',') : '';
    layer.bindTooltip(esc(n) + ipm, {sticky: true});
  }
}).addTo(map);

// ---- gelembung bernomor ----
function bubble(v) {
  const kelas = v >= CFG.t2 ? 'merah' : (v >= CFG.t1 ? 'magenta' : 'ungu');
  const ukuran = {ungu: 38, magenta: 44, merah: 52}[kelas];
  return L.divIcon({
    html: '<div class="bub ' + kelas + '"><span>' + singkat(v) + '</span></div>',
    className: 'bub-wrap', iconSize: [ukuran, ukuran]
  });
}
function popupHtml(d) {
  let h = '<div style="min-width:200px"><div style="font-weight:700;font-size:14px;margin-bottom:4px">' + esc(d.nama) + '</div>';
  h += '<table style="border-collapse:collapse;font-size:12px;width:100%">';
  d.rincian.forEach(r => {
    h += '<tr><td style="padding:2px 10px 2px 0;color:#6b7280">' + esc(r[0]) + '</td>' +
         '<td style="padding:2px 0;text-align:right;font-weight:600">' + esc(r[1]) + '</td></tr>';
  });
  return h + '</table></div>';
}

const cluster = L.markerClusterGroup({
  maxClusterRadius: 48,
  showCoverageOnHover: false,
  spiderfyOnMaxZoom: true,
  iconCreateFunction: c => bubble(c.getAllChildMarkers().reduce((s, m) => s + m.options.nilai, 0))
});
DATA.forEach(d => {
  const m = L.marker([d.lat, d.lon], {icon: bubble(d.nilai), nilai: d.nilai, nama: d.nama});
  m.bindPopup(popupHtml(d), {maxWidth: 280});
  m.bindTooltip(esc(d.nama) + ': ' + id(d.nilai), {direction: 'top', offset: [0, -20]});
  cluster.addLayer(m);
});
cluster.on('clustermouseover', e => {
  const ms = e.layer.getAllChildMarkers();
  const total = ms.reduce((s, m) => s + m.options.nilai, 0);
  const nama = ms.map(m => m.options.nama);
  const ket = nama.slice(0, 6).join(', ') + (nama.length > 6 ? ', +' + (nama.length - 6) + ' lainnya' : '');
  e.layer.bindTooltip('<b>' + id(total) + '</b> (' + esc(CFG.judul.toLowerCase()) + ')<br>' + esc(ket), {direction: 'top'}).openTooltip();
});
map.addLayer(cluster);

// ---- bingkai awal: mengikuti titik wilayah yang sedang ditampilkan ----
if (DATA.length) {
  map.fitBounds(L.latLngBounds(DATA.map(d => [d.lat, d.lon])).pad(0.1), {maxZoom: 10, padding: [24, 24]});
} else {
  map.setView([-7.55, 112.3], 8);
}
// sesuaikan ukuran peta bila bingkai berubah (mis. sidebar dibuka/ditutup)
if (window.ResizeObserver) new ResizeObserver(() => map.invalidateSize()).observe(document.getElementById('peta'));

// ---- legenda ----
const legenda = L.control({position: 'topright'});
legenda.onAdd = () => {
  const el = L.DomUtil.create('div', 'legenda');
  const baris = (w, t) => '<div class="baris"><span class="kotak" style="background:' + w + '"></span>' + t + '</div>';
  let h = '<b>' + esc(CFG.judul) + '</b>';
  h += baris('#8b5cf6', 'kurang dari ' + id(CFG.t1));
  h += baris('#d946ef', id(CFG.t1) + ' sampai kurang dari ' + id(CFG.t2));
  h += baris('#f43f5e', id(CFG.t2) + ' atau lebih');
  if (CFG.warnaIpm) {
    h += '<div style="margin-top:6px"><b>IPM (warna wilayah)</b></div>' +
         '<div class="grad" style="background:linear-gradient(to right,' + STOPS.join(',') + ')"></div>' +
         '<div class="skala"><span>' + CFG.ipmMin.toFixed(1).replace('.', ',') + '</span><span>' +
         CFG.ipmMax.toFixed(1).replace('.', ',') + '</span></div>';
  }
  el.innerHTML = h;
  return el;
};
legenda.addTo(map);

window.__peta = {map: map, cluster: cluster};   // dipakai untuk pengujian otomatis
</script>
</body>
</html>
"""


def bangun_peta_html(wilayah, geojson, *, judul, ambang, ipm=None, warna_ipm=False):
    """
    Hasilkan HTML mandiri (Leaflet via CDN) untuk disematkan dengan st.iframe.

    wilayah : list of dict {nama, lat, lon, nilai, rincian=[[label, nilai], ...]}
    geojson : FeatureCollection batas kabupaten/kota (properti kabupaten_kota, lat, lon)
    judul   : judul indikator pada legenda, mis. "Jumlah sekolah"
    ambang  : (t1, t2) batas kelas warna gelembung
    ipm     : {nama: nilai IPM} untuk semua wilayah (dipakai bila warna_ipm=True)
    """
    ipm = {k: float(v) for k, v in (ipm or {}).items() if v is not None}
    nilai_ipm = list(ipm.values())
    cfg = {
        "judul": judul,
        "t1": int(round(ambang[0])),
        "t2": int(round(ambang[1])),
        "warnaIpm": bool(warna_ipm and nilai_ipm),
        "ipm": ipm,
        "ipmMin": min(nilai_ipm) if nilai_ipm else 0.0,
        "ipmMax": max(nilai_ipm) if nilai_ipm else 1.0,
        "atribusi": ATRIBUSI_BATAS,
    }
    isi = {
        "LV": LEAFLET_VER,
        "CV": CLUSTER_VER,
        "DATA": _js(wilayah),
        "GEO": _js(geojson),
        "CFG": _js(cfg),
    }
    # satu kali penggantian agar isi data tidak ikut diproses ulang
    return re.sub(r"__(LV|CV|DATA|GEO|CFG)__", lambda m: isi[m.group(1)], _TEMPLATE)
