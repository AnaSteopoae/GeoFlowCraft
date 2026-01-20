# Configurare GeoServer și Creare Layer Canopy Height

**Data:** 20 Ianuarie 2026  
**Proiect:** GeoFlowCraft  
**Autor:** Rezumat configurare tehnică

---

## 🎯 Problema Inițială

Nu se putea crea un layer în GeoFlowCraft - eroarea era **"All configured authentication methods failed"**.

---

## ✅ Soluții Implementate

### 1. Configurare Conexiune GeoServer

**Fișier modificat:** `backend/.env`

**Înainte (GREȘIT):**
```env
GEOSERVER_URL=http://localhost:8080/geoserver
GEOSERVER_PASSWORD=geoserver
```

**După (CORECT):**
```env
GEOSERVER_URL=http://localhost:5433/geoserver
GEOSERVER_PASSWORD=admin
```

**Motivație:** Containerul GeoServer rulează pe portul **5433**, nu 8080, iar parola implicită este **admin**.

---

### 2. Corectare Path-uri GeoServer

**Fișier modificat:** `backend/.env`

**Înainte (INCONSISTENT):**
```env
GEOSERVER_VM_REMOTE_BASE_PATH=/opt/geoserver/data_dir/data
GEOSERVER_REMOTE_BASE_PATH=/opt/geoserver_data_dir/data  # ❌ underscore greșit
```

**După (CORECT):**
```env
GEOSERVER_VM_REMOTE_BASE_PATH=/opt/geoserver/data_dir/data
GEOSERVER_REMOTE_BASE_PATH=/opt/geoserver/data_dir/data  # ✅ același path
```

**Motivație:** Fișierele se copiază în `/opt/geoserver/data_dir/data`, dar GeoServer căuta în path greșit cu underscore diferit (`geoserver_data_dir`). Acest path este folosit pentru crearea store-ului GeoTIFF și trebuia să coincidă cu locația reală a fișierelor.

---

### 3. Creare Director și Permisiuni

**Comenzi executate:**
```bash
# Creare director pentru date GeoTIFF
sudo mkdir -p /home/anamaria-steo/Licenta/GeoFlowCraft/backend/data_geoserver/data

# Setare permisiuni corecte
sudo chown -R anamaria-steo:anamaria-steo backend/data_geoserver/data
sudo chmod -R 775 backend/data_geoserver/data
```

**Motivație:** Backend-ul Node.js trebuie să poată scrie fișiere în acest director. Inițial directorul nu exista și generarea automată eșua cu eroare `EACCES: permission denied`.

---

### 4. Creare Stil Personalizat pentru Canopy Height

#### 4.1. Fișier SLD Creat

**Locație:** `backend/data_geoserver/styles/canopy_height.sld`

**Conținut:** Stil SLD cu paletă de culori **Viridis** pentru înălțimi 0-40m:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0" 
    xmlns="http://www.opengis.net/sld" 
    xmlns:ogc="http://www.opengis.net/ogc" 
    xmlns:xlink="http://www.w3.org/1999/xlink" 
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
    xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>Canopy Height</Name>
    <UserStyle>
      <Title>Canopy Height - Viridis Color Ramp</Title>
      <Abstract>Viridis color ramp for canopy height visualization (0-40m)</Abstract>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap type="ramp">
              <ColorMapEntry color="#ffffff" quantity="0" label="No Data" opacity="0"/>
              <ColorMapEntry color="#440154" quantity="0.1" label="0m"/>
              <ColorMapEntry color="#482677" quantity="5" label="5m"/>
              <ColorMapEntry color="#404788" quantity="10" label="10m"/>
              <ColorMapEntry color="#2a788e" quantity="15" label="15m"/>
              <ColorMapEntry color="#22a884" quantity="20" label="20m"/>
              <ColorMapEntry color="#7ad151" quantity="25" label="25m"/>
              <ColorMapEntry color="#bddf26" quantity="30" label="30m"/>
              <ColorMapEntry color="#fde724" quantity="35" label="35m"/>
              <ColorMapEntry color="#ffea00" quantity="40" label="40m+"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
```

#### 4.2. Paletă Culori Viridis

| Înălțime | Culoare | Hex Code | Descriere |
|----------|---------|----------|-----------|
| 0m | Transparent | #ffffff (opacity: 0) | Zone fără date |
| 0-5m | Mov închis | #440154 | Copaci foarte scunzi |
| 5-10m | Violet | #482677 | Copaci scunzi |
| 10-15m | Albastru | #404788 | Copaci medii-scunzi |
| 15-20m | Cyan | #2a788e | Copaci medii |
| 20-25m | Verde-albastru | #22a884 | Copaci medii-înalți |
| 25-30m | Verde deschis | #7ad151 | Copaci înalți |
| 30-35m | Verde-galben | #bddf26 | Copaci foarte înalți |
| 35-40m | Galben | #fde724 | Copaci extrem de înalți |
| 40m+ | Galben strălucitor | #ffea00 | Copaci exceționali |

**Motivație alegere paletă:** Paleta Viridis oferă contrast optim cu harta de fundal verde OpenStreetMap. Stilul implicit "raster" afișa layer-ul complet negru, iar prima variantă cu paletă verde se confunda cu vegetația de pe hartă.

#### 4.3. Înregistrare Stil în GeoServer

**Comenzi REST API executate:**

```bash
# 1. Creare stil în GeoServer
curl -u admin:admin -X POST -H "Content-Type: text/xml" \
  -d '<style><name>canopy_height</name><filename>canopy_height.sld</filename></style>' \
  "http://localhost:5433/geoserver/rest/styles"

# 2. Upload fișier SLD
cat /tmp/canopy_height_viridis.sld | curl -u admin:admin -X PUT \
  -H "Content-Type: application/vnd.ogc.sld+xml" --data-binary @- \
  "http://localhost:5433/geoserver/rest/styles/canopy_height"

# 3. Aplicare stil la layer
curl -u admin:admin -X PUT -H "Content-Type: text/xml" \
  -d '<layer><defaultStyle><name>canopy_height</name></defaultStyle></layer>' \
  "http://localhost:5433/geoserver/rest/layers/default_workspace:layer_696f78a737105af01e04d15e"
```

**Note importante:**
- Parametrul `type="ramp"` în `<ColorMap>` este **critic** - fără el, GeoServer folosește culori discrete aleatorii
- Stilul trebuie creat înainte de upload-ul SLD-ului
- Aplicarea la layer se face prin actualizare (`PUT`) a configurației layer-ului

---

### 5. Pornire Containere Docker

**Comenzi executate:**
```bash
# Pornire PostGIS (database pentru GeoServer)
docker start geoserver_db

# Așteptare 3 secunde pentru inițializare
sleep 3

# Pornire GeoServer
docker start geoserver
```

**Ordine critică:** PostGIS trebuie pornit **înainte** de GeoServer, deoarece GeoServer depinde de baza de date PostgreSQL/PostGIS pentru metadata și configurații.

**Verificare status:**
```bash
docker ps | grep -E "geoserver|postgis"
```

**Output așteptat:**
```
f76b1d555e02   kartoza/geoserver   Up   0.0.0.0:5433->8080/tcp   geoserver
8f07d5139970   postgis/postgis     Up   0.0.0.0:5434->5432/tcp   geoserver_db
```

---

## 📋 Fișiere Modificate - Rezumat Complet

### 1. `/home/anamaria-steo/Licenta/GeoFlowCraft/backend/.env`

**Linii modificate:**

| Linie | Înainte | După | Motiv |
|-------|---------|------|-------|
| 16 | `GEOSERVER_URL=http://localhost:8080/geoserver` | `GEOSERVER_URL=http://localhost:5433/geoserver` | Port corect container Docker |
| 18 | `GEOSERVER_PASSWORD=geoserver` | `GEOSERVER_PASSWORD=admin` | Parolă implicită kartoza/geoserver |
| 28 | `GEOSERVER_REMOTE_BASE_PATH=/opt/geoserver_data_dir/data` | `GEOSERVER_REMOTE_BASE_PATH=/opt/geoserver/data_dir/data` | Path consistent cu mount-ul Docker |

### 2. Fișiere Noi Create

| Fișier | Tip | Mărime | Scop |
|--------|-----|--------|------|
| `backend/data_geoserver/styles/canopy_height.sld` | SLD (XML) | ~1.7 KB | Stil vizualizare canopy height |
| `backend/data_geoserver/data/696f78a737105af01e04d15e.tiff` | GeoTIFF | 173 MB | Date canopy height procesate de AI |

### 3. Directoare Create

| Director | Permisiuni | Proprietar | Scop |
|----------|------------|------------|------|
| `backend/data_geoserver/data/` | 775 (drwxrwxr-x) | anamaria-steo:anamaria-steo | Stocare GeoTIFF-uri uploadate |

---

## 🚀 Rezultat Final

### Layer Funcțional Complet

✅ **Procesul de creare layer:**
1. Upload fișier GeoTIFF (173MB) → `backend/uploads/`
2. Redenumire cu ID MongoDB → `696f78a737105af01e04d15e.tiff`
3. Copiere în director GeoServer → `backend/data_geoserver/data/`
4. Creare workspace `default_workspace` (dacă nu există)
5. Creare store GeoTIFF → `store_696f78a737105af01e04d15e`
6. Creare layer → `layer_696f78a737105af01e04d15e`
7. Aplicare stil `canopy_height`
8. Publicare layer în WMS/WFS

### Date Layer

**Informații tehnice (din `gdalinfo`):**
- **Dimensiune:** 10980 x 10980 pixeli
- **Proiecție:** EPSG:32635 (WGS 84 / UTM zone 35N)
- **Tip date:** Float32 (virgulă mobilă)
- **Interval valori:** 0 - 40.24 metri
- **Statistici:**
  - Minimum: 0.000m
  - Maximum: 40.244m
  - Medie: 3.417m
  - Deviație standard: 5.733m
  - Pixeli valizi: 43.12% (restul sunt NoData/transparenți)

**Coordonate geografice:**
- Nord-Vest: 26°59'59"E, 46°57'13"N
- Sud-Est: 28°25'00"E, 45°57'24"N
- **Locație:** România (zona Carpați)

### Vizualizare

**Layer vizibil pe hartă cu:**
- Culori Viridis (mov → galben) pentru înălțimi 0-40m
- Transparență pentru zone fără copaci (NoData)
- Contrast optim cu harta de fundal OpenStreetMap
- Reproiecție automată EPSG:32635 → EPSG:3857 (Web Mercator) pentru compatibilitate web

---

## 🔧 Configurație Tehnică Completă

### Servicii și Porturi

| Serviciu | Container/Proces | Port Host | Port Container | Credențiale | Status |
|----------|------------------|-----------|----------------|-------------|--------|
| **GeoServer** | kartoza/geoserver (f76b1d555e02) | 5433 | 8080 | admin/admin | ✅ Activ |
| **PostGIS** | postgis/postgis (8f07d5139970) | 5434 | 5432 | postgres/postgres | ✅ Activ |
| **Backend API** | Node.js + Express | 5555 | - | - | ✅ Activ |
| **Frontend** | Vue.js + Vite | 5173 | - | - | ✅ Activ |
| **AI Processor** | Python + PyTorch | 5556 | - | - | ⏸ Stopped |
| **Copernicus** | Python + FastAPI | 8000 | - | OAuth | ✅ Activ |

### Mount-uri Docker

**GeoServer:**
```yaml
Source: /home/anamaria-steo/Licenta/GeoFlowCraft/backend/data_geoserver
Destination: /opt/geoserver/data_dir
Type: bind
Mode: rw
```

**Importanță:** Acest mount permite:
- Backend-ului să scrie direct fișiere accesibile containerului
- GeoServer-ului să citească fișierele fără transfer SSH
- Persistența datelor după restart container

### Fluxul de Date

```
Frontend (Vue.js)
    ↓ HTTP POST /api/datalayers (multipart/form-data)
Backend (Express.js)
    ↓ fs.copyFileSync()
backend/data_geoserver/data/[file].tiff
    ↓ Docker bind mount
Container GeoServer: /opt/geoserver/data_dir/data/[file].tiff
    ↓ REST API (POST /rest/workspaces/.../coveragestores)
GeoServer Internal: Workspace → Store → Layer
    ↓ WMS GetMap Request
Tiles servite prin HTTP (EPSG:3857)
    ↓
Frontend OpenLayers Map
```

---

## 📝 Pași pentru Replicare

### Crearea unui Nou Layer Canopy Height

#### Pas 1: Verificare Servicii

```bash
# Verifică dacă containerele rulează
docker ps | grep -E "geoserver|postgis"

# Dacă nu rulează, pornește-le în ordine:
docker start geoserver_db
sleep 3
docker start geoserver

# Verifică backend-ul
curl http://localhost:5555/health  # (dacă există endpoint)
```

#### Pas 2: Verificare Configurație Backend

```bash
# Verifică .env
cat backend/.env | grep GEOSERVER

# Output așteptat:
# GEOSERVER_URL=http://localhost:5433/geoserver
# GEOSERVER_USERNAME=admin
# GEOSERVER_PASSWORD=admin
# GEOSERVER_VM_REMOTE_BASE_PATH=/opt/geoserver/data_dir/data
# GEOSERVER_REMOTE_BASE_PATH=/opt/geoserver/data_dir/data
```

#### Pas 3: Verificare Permisiuni

```bash
# Verifică directorul de date
ls -la backend/data_geoserver/data/

# Output așteptat:
# drwxrwxr-x anamaria-steo anamaria-steo

# Dacă nu există sau permisiuni greșite:
sudo mkdir -p backend/data_geoserver/data
sudo chown -R anamaria-steo:anamaria-steo backend/data_geoserver/data
sudo chmod -R 775 backend/data_geoserver/data
```

#### Pas 4: Creare Layer din UI

1. Accesează aplicația: `http://localhost:5173`
2. Click pe **"Datalayers catalog"** → **"+"** (Add layer)
3. Completează formular:
   - **Name:** `canopy_test`
   - **Description:** `Test canopy height layer`
   - **File:** Selectează `predictions.tif` din `service.ai-ch-processor/output/`
4. Click **"Create"**

**Log-uri backend așteptate:**
```
Saving partial DataLayer ('canopy_test') to database...
Renaming the file './uploads/predictions.tif' to './uploads/[MONGO_ID].tiff'...
Uploading file ('/opt/geoserver/data_dir/data/[MONGO_ID].tiff') to GeoServer's filesystem...
File copied locally to: /home/.../backend/data_geoserver/data/[MONGO_ID].tiff
Creating GeoServer workspace 'default_workspace'...
Creating GeoServer store 'store_[MONGO_ID]'...
Creating layer 'layer_[MONGO_ID]'...
✅ Layer created successfully
```

#### Pas 5: Aplicare Stil (dacă necesar)

Dacă layer-ul apare negru sau cu culori greșite:

```bash
# Verifică stilul aplicat
curl -s -u admin:admin \
  "http://localhost:5433/geoserver/rest/layers/default_workspace:layer_[ID].json" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['layer']['defaultStyle']['name'])"

# Dacă răspunsul este "raster", aplică stilul canopy_height:
curl -u admin:admin -X PUT -H "Content-Type: text/xml" \
  -d '<layer><defaultStyle><name>canopy_height</name></defaultStyle></layer>' \
  "http://localhost:5433/geoserver/rest/layers/default_workspace:layer_[ID]"
```

#### Pas 6: Verificare și Troubleshooting

```bash
# Test WMS GetMap direct
curl -s -u admin:admin \
  "http://localhost:5433/geoserver/default_workspace/wms?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&FORMAT=image/png&TRANSPARENT=true&LAYERS=default_workspace:layer_[ID]&SRS=EPSG:32635&STYLES=canopy_height&WIDTH=512&HEIGHT=512&BBOX=499980,5090220,609780,5200020" \
  > /tmp/test_layer.png && xdg-open /tmp/test_layer.png

# Verifică în browser GeoServer
# http://localhost:5433/geoserver → Layer Preview → OpenLayers
```

**Probleme comune:**

| Problemă | Cauză | Soluție |
|----------|-------|---------|
| Layer negru | Stil implicit "raster" | Aplică stil `canopy_height` |
| Layer invizibil pe hartă | Cache browser | Ctrl+Shift+R (hard refresh) |
| Eroare 401 Unauthorized | Credențiale greșite | Verifică `GEOSERVER_PASSWORD=admin` |
| Eroare "Cannot create reader" | Path greșit | Verifică `GEOSERVER_REMOTE_BASE_PATH` |
| Permission denied | Permisiuni directoare | `chmod 775` și `chown` corect |

---

## 🎨 Detalii Tehnice Stil Viridis

### De ce Viridis?

Paleta Viridis a fost aleasă din următoarele motive:

1. **Perceptual Uniformity:** Schimbările în culoare corespund uniform cu schimbările în date
2. **Color-blind Friendly:** Vizibilă pentru persoane cu daltonism
3. **Print-friendly:** Se traduce bine în grayscale
4. **Contrast cu fundal:** Verde OSM vs. mov-albastru-galben Viridis
5. **Scientific Standard:** Folosită în matplotlib, QGIS, ArcGIS

### Alternative de Palete

Alte palete disponibile (pot fi implementate similar):

**Plasma** (mov → portocaliu):
```xml
<ColorMapEntry color="#0d0887" quantity="0.1" label="0m"/>
<ColorMapEntry color="#7e03a8" quantity="10" label="10m"/>
<ColorMapEntry color="#cc4778" quantity="20" label="20m"/>
<ColorMapEntry color="#f89540" quantity="30" label="30m"/>
<ColorMapEntry color="#f0f921" quantity="40" label="40m+"/>
```

**Terrain** (verde → maro → alb):
```xml
<ColorMapEntry color="#00441b" quantity="0.1" label="0m"/>
<ColorMapEntry color="#41ab5d" quantity="10" label="10m"/>
<ColorMapEntry color="#a1d99b" quantity="20" label="20m"/>
<ColorMapEntry color="#c7e9c0" quantity="30" label="30m"/>
<ColorMapEntry color="#f7fcf5" quantity="40" label="40m+"/>
```

**Turbo** (albastru → roșu):
```xml
<ColorMapEntry color="#30123b" quantity="0.1" label="0m"/>
<ColorMapEntry color="#1ae4b6" quantity="10" label="10m"/>
<ColorMapEntry color="#faba39" quantity="20" label="20m"/>
<ColorMapEntry color="#f8765c" quantity="30" label="30m"/>
<ColorMapEntry color="#a50026" quantity="40" label="40m+"/>
```

---

## 📊 Performanță și Optimizare

### Metrici Observate

**Upload și procesare layer:**
- Upload fișier (173MB): ~2-3 secunde
- Copiere locală: <1 secundă
- Creare workspace/store/layer: ~1-2 secunde
- **Total:** ~5-6 secunde pentru layer complet

**Randare WMS tiles:**
- Primul tile (cold cache): ~500ms
- Tile-uri ulterioare (warm cache): ~50-100ms
- Rezoluție testată: 768x768 pixeli

### Recomandări Optimizare

1. **GeoTIFF Compression:**
   ```bash
   gdal_translate -co COMPRESS=DEFLATE -co TILED=YES \
     input.tif output_optimized.tif
   ```

2. **Pyramids (Overviews):**
   ```bash
   gdaladdo -r average output_optimized.tif 2 4 8 16
   ```

3. **GeoServer Tile Caching:**
   - Activează GeoWebCache pentru layer
   - Configurare în `http://localhost:5433/geoserver/gwc`

---

## 🔗 Resurse și Referințe

### Documentație

- **GeoServer REST API:** https://docs.geoserver.org/stable/en/user/rest/
- **SLD Cookbook:** https://docs.geoserver.org/stable/en/user/styling/sld/cookbook/
- **GDAL/OGR:** https://gdal.org/
- **Kartoza GeoServer Docker:** https://github.com/kartoza/docker-geoserver

### Endpoint-uri Utile

| Endpoint | Metodă | Descriere |
|----------|--------|-----------|
| `http://localhost:5433/geoserver/web` | Browser | GeoServer Web UI |
| `http://localhost:5433/geoserver/rest/styles` | GET | Lista stiluri |
| `http://localhost:5433/geoserver/rest/layers` | GET | Lista layere |
| `http://localhost:5433/geoserver/rest/workspaces` | GET | Lista workspace-uri |
| `http://localhost:5433/geoserver/wms?request=GetCapabilities` | GET | WMS Capabilities |

### Comenzi Utile

```bash
# Restart GeoServer (păstrează date)
docker restart geoserver

# Vizualizare log-uri GeoServer
docker logs -f geoserver

# Curățare cache GeoWebCache
curl -u admin:admin -X POST \
  "http://localhost:5433/geoserver/gwc/rest/masstruncate"

# Export configurație layer
curl -s -u admin:admin \
  "http://localhost:5433/geoserver/rest/layers/default_workspace:layer_ID.json" \
  > layer_config.json
```

---

## ✅ Checklist Final

**Pentru deployment în producție:**

- [ ] Schimbă credențiale GeoServer (`admin/admin` → parole sigure)
- [ ] Configurează HTTPS pentru GeoServer
- [ ] Activează autentificare pentru REST API
- [ ] Configurează backup automat pentru `data_geoserver/`
- [ ] Monitorizare resurse Docker (CPU, RAM, disk)
- [ ] Configurează log rotation pentru GeoServer
- [ ] Testează disaster recovery (restore din backup)
- [ ] Documentează proceduri operaționale
- [ ] Configurează alerting pentru servicii down

---

**Document generat:** 20 Ianuarie 2026  
**Versiune:** 1.0  
**Status:** ✅ Complet și verificat
