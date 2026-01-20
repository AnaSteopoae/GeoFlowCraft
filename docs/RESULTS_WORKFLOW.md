# Workflow pentru Vizualizarea Rezultatelor AI - Canopy Height

## Prezentare Generală

Acest document explică cum funcționează flow-ul complet pentru procesarea imaginilor Sentinel-2 și vizualizarea rezultatelor generate de agentul AI de Canopy Height.

## Arhitectura Soluției

```
┌─────────────────────────────────────────────────────────────────┐
│                        FLOW COMPLET                              │
└─────────────────────────────────────────────────────────────────┘

1. User selectează zonă pe hartă
   └─> Caută imagini Sentinel-2 disponibile
   
2. User selectează imagini L2A compatibile
   └─> Click "Process"
   
3. Download + Processing
   ├─> Download imagini prin Copernicus Service
   ├─> Procesare cu AI Service (ch-processor)
   └─> Generare GeoTIFF files
   
4. Salvare rezultate în aiAgent store
   └─> Afișare notificare success
   
5. Vizualizare rezultate
   ├─> Click "View Results" (toate rezultatele)
   └─> Click icon rezultate pe fiecare imagine procesată
   
6. Download GeoTIFF
   └─> Download individual sau "Download All"
```

## Componente Noi Adăugate

### 1. Backend - Endpoint-uri pentru Rezultate

#### **GET /api/ai/results/:productId**
Returnează rezultatele procesării pentru un produs specific.

**Request:**
```bash
GET http://localhost:5555/api/ai/results/S2B_MSIL2A_20240619T092549_N0510_R136_T34TER_20240619T110657
```

**Response:**
```json
{
  "success": true,
  "productId": "S2B_MSIL2A_20240619T092549_N0510_R136_T34TER_20240619T110657",
  "count": 2,
  "results": [
    {
      "filename": "S2B_MSIL2A_20240619T092549_N0510_R136_T34TER_20240619T110657_predictions.tif",
      "path": "/path/to/output/..._predictions.tif",
      "size": 45678901,
      "type": "predictions",
      "createdAt": "2024-01-19T10:30:00.000Z",
      "modifiedAt": "2024-01-19T10:30:00.000Z"
    },
    {
      "filename": "S2B_MSIL2A_20240619T092549_N0510_R136_T34TER_20240619T110657_std.tif",
      "path": "/path/to/output/..._std.tif",
      "size": 45678901,
      "type": "std",
      "createdAt": "2024-01-19T10:30:00.000Z",
      "modifiedAt": "2024-01-19T10:30:00.000Z"
    }
  ]
}
```

#### **GET /api/ai/results**
Returnează toate rezultatele disponibile, grupate pe productId.

**Response:**
```json
{
  "success": true,
  "count": 2,
  "results": {
    "S2B_MSIL2A_20240619T092549...": [
      { "filename": "..._predictions.tif", ... },
      { "filename": "..._std.tif", ... }
    ],
    "S2A_MSIL2A_20240618T093041...": [
      { "filename": "..._predictions.tif", ... },
      { "filename": "..._std.tif", ... }
    ]
  }
}
```

#### **GET /api/ai/download/:filename**
Descarcă un fișier GeoTIFF rezultat.

**Request:**
```bash
GET http://localhost:5555/api/ai/download/S2B_MSIL2A_20240619T092549_N0510_R136_T34TER_20240619T110657_predictions.tif
```

**Response:**
```
Content-Type: image/tiff
Content-Disposition: attachment; filename="..._predictions.tif"

[Binary GeoTIFF data]
```

### 2. Frontend - aiAgent Store (Extensii)

#### **State**
```javascript
state: () => ({
    availableAgents: [],
    selectedAgent: null,
    isLoading: false,
    error: null,
    processingResults: {}, // { productId: { results: [], timestamp: Date } }
    lastProcessedProduct: null
})
```

#### **Noi Actions**

**loadProcessingResults(productId)**
```javascript
// Încarcă rezultatele pentru un produs specific
await aiAgentStore.loadProcessingResults('S2B_MSIL2A_...');
```

**loadAllProcessingResults()**
```javascript
// Încarcă toate rezultatele disponibile
await aiAgentStore.loadAllProcessingResults();
```

**getDownloadUrl(filename)**
```javascript
// Generează URL pentru download
const url = aiAgentStore.getDownloadUrl('product_predictions.tif');
```

**clearResultsForProduct(productId)**
```javascript
// Șterge rezultatele din cache
aiAgentStore.clearResultsForProduct('S2B_MSIL2A_...');
```

#### **Noi Getters**

**getResultsForProduct(productId)**
```javascript
// Returnează rezultatele pentru un produs
const results = aiAgentStore.getResultsForProduct('S2B_MSIL2A_...');
```

**hasLastResults**
```javascript
// Verifică dacă există rezultate pentru ultimul produs
if (aiAgentStore.hasLastResults) {
    // ...
}
```

### 3. Frontend - Componente Noi

#### **AppProcessingResultsDialog.vue**

Dialog modern pentru vizualizarea rezultatelor procesării AI.

**Features:**
- ✅ Tabel cu toate rezultatele (DataTable PrimeVue)
- ✅ Filtrare automată după tip (Predictions / Std Dev)
- ✅ Download individual pentru fiecare fișier
- ✅ "Download All" pentru toate fișierele
- ✅ Formatare automată dimensiune fișiere (KB, MB, GB)
- ✅ Afișare dată/oră modificare
- ✅ Tag-uri colorate pentru tipul de rezultat
- ✅ Loading state cu ProgressSpinner
- ✅ Suport pentru vizualizare toate rezultatele sau per produs

**Props:**
```vue
<AppProcessingResultsDialog 
    v-model="showDialog"
    :productId="selectedProductId"
/>
```

- `modelValue`: Boolean - controlează vizibilitatea dialogului
- `productId`: String (optional) - ID-ul produsului pentru rezultate specifice
  - Dacă `productId` este `null` → afișează toate rezultatele
  - Dacă `productId` este specificat → afișează doar rezultatele pentru acel produs

**Usage în AppModelProcessingSearchResultsDialog.vue:**

1. **Import component:**
```javascript
import AppProcessingResultsDialog from "@/components/dialogs/AppProcessingResultsDialog.vue";
```

2. **Adaugă în template:**
```vue
<AppProcessingResultsDialog 
    v-model="showResultsDialog"
    :productId="selectedProductId"
/>
```

3. **Metode pentru deschidere:**
```javascript
// Toate rezultatele
showAllResults() {
    this.selectedProductId = null;
    this.showResultsDialog = true;
}

// Rezultate pentru un produs specific
showResultsForProduct(productId) {
    this.selectedProductId = productId;
    this.showResultsDialog = true;
}
```

### 4. Frontend - Modificări în AppModelProcessingSearchResultsDialog.vue

#### **Noi Butoane în UI**

**Buton "View Results" (global):**
```vue
<PrimeButton 
    label="View Results" 
    icon="pi pi-list" 
    severity="info" 
    outlined
    @click="showAllResults"
    v-tooltip.bottom="'View all processing results'"
/>
```

**Buton rezultate per imagine (în tabel):**
```vue
<PrimeButton 
    v-if="hasResultsForProduct(item.id)"
    @click="showResultsForProduct(item.id)"
    icon="pi pi-chart-bar" 
    variant="text" rounded 
    severity="info"
    size="small"
    v-tooltip.bottom="'View processing results'"
/>
```

#### **Funcția hasResultsForProduct()**
```javascript
hasResultsForProduct(productId) {
    const aiAgentStore = useAIAgentStore();
    return aiAgentStore.processingResults[productId] !== undefined;
}
```

Afișează iconița de rezultate doar dacă există rezultate disponibile pentru acea imagine.

#### **Modificare processImage()**
```javascript
async processImage(item, agentId) {
    // ... existing code ...
    
    const result = await aiAgentStore.processWithSelectedAgent({
        image_filenames: [`${item.id}/${item.id}.zip`]
    });
    
    // ✨ NOU: Încarcă automat rezultatele după procesare
    await aiAgentStore.loadProcessingResults(item.id);
    
    this.$toast.add({ 
        severity: "success", 
        summary: "Processing Complete", 
        detail: `Image ${item.id} processed successfully!`, 
        life: 5000
    });
}
```

## Flow Complet de Utilizare

### Pas 1: Căutare Imagini

1. User deschide aplicația
2. Selectează o zonă pe hartă (draw rectangle/polygon)
3. Alege AI model: "Canopy Height Processor"
4. Selectează interval de date
5. Click "Search"

### Pas 2: Selecție și Procesare

1. Dialogul afișează rezultatele căutării
2. **Doar imagini L2A compatibile** sunt afișate
3. User selectează una sau mai multe imagini
4. Click "Process"

### Pas 3: Download și AI Processing

**Flow automat:**
```
[Frontend] → Inițiază download
           ↓
[Copernicus Service] → Descarcă imaginea
           ↓
[shared-data/] → Salvează și extrage ZIP
           ↓
[Frontend] → Polling status download
           ↓
[Backend] → Trimite request la AI Service
           ↓
[AI Service] → Procesează imagine
           ├─> Generează predictions.tif
           └─> Generează std.tif
           ↓
[service.ai-ch-processor/output/] → Salvează rezultate
           ↓
[Frontend] → Încarcă rezultate în store
           ↓
[Toast] → "Processing Complete!"
```

### Pas 4: Vizualizare Rezultate

**Opțiune A - Toate rezultatele:**
1. Click "View Results" în search results dialog
2. Se deschide AppProcessingResultsDialog
3. Afișează toate fișierele .tif generate
4. Tabel cu coloane: Product ID, Type, Filename, Size, Modified, Actions

**Opțiune B - Rezultate per imagine:**
1. Click pe iconița 📊 (chart-bar) lângă imagine procesată
2. Se deschide AppProcessingResultsDialog
3. Afișează doar rezultatele pentru acea imagine
4. Tabel cu coloane: Type, Filename, Size, Modified, Actions

### Pas 5: Download GeoTIFF

**Download individual:**
1. Click pe 📥 în coloana Actions
2. Browser descarcă automat fișierul .tif

**DownloadAll:**
1. Click "Download All" în footer
2. Toate fișierele sunt descărcate secvențial (staggered 500ms)

## Structura Fișierelor Generate

```
service.ai-ch-processor/output/
├── S2B_MSIL2A_20240619T092549_N0510_R136_T34TER_20240619T110657_predictions.tif
│   └── Canopy Height Map (valorile înălțimii copacilor)
├── S2B_MSIL2A_20240619T092549_N0510_R136_T34TER_20240619T110657_std.tif
│   └── Standard Deviation (incertitudinea predicției)
├── S2A_MSIL2A_20240618T093041_N0510_R093_T35TML_20240618T120345_predictions.tif
└── S2A_MSIL2A_20240618T093041_N0510_R093_T35TML_20240618T120345_std.tif
```

**Naming Convention:**
```
{PRODUCT_ID}_{TYPE}.tif

PRODUCT_ID: ID complet Sentinel-2
TYPE: predictions sau std
```

## Tipuri de Fișiere Rezultate

### 1. Predictions (Canopy Height)
- **Filename:** `*_predictions.tif`
- **Content:** Harta înălțimii copacilor
- **Format:** GeoTIFF cu georeferențiere
- **Values:** Înălțime în metri (0-50m typical)
- **Tag:** Verde (success)

### 2. Standard Deviation (Uncertainty)
- **Filename:** `*_std.tif`
- **Content:** Incertitudinea predicției
- **Format:** GeoTIFF cu georeferențiere
- **Values:** Deviație standard
- **Tag:** Albastru (info)

## API Calls - Exemple Complete

### Procesare Imagine

```javascript
// 1. Procesare
const result = await aiAgentStore.processWithSelectedAgent({
    image_filenames: ['S2B_MSIL2A_.../S2B_MSIL2A_....zip']
});

// 2. Încărcare rezultate
await aiAgentStore.loadProcessingResults('S2B_MSIL2A_...');

// 3. Verificare rezultate
const hasResults = aiAgentStore.hasResultsForProduct('S2B_MSIL2A_...');

// 4. Obținere rezultate
const results = aiAgentStore.getResultsForProduct('S2B_MSIL2A_...');
```

### Vizualizare și Download

```javascript
// Deschide dialog cu toate rezultatele
this.selectedProductId = null;
this.showResultsDialog = true;

// Deschide dialog pentru un produs specific
this.selectedProductId = 'S2B_MSIL2A_...';
this.showResultsDialog = true;

// Download fișier
const downloadUrl = aiAgentStore.getDownloadUrl('product_predictions.tif');
// URL: http://localhost:5555/api/ai/download/product_predictions.tif
```

## Cache Management

### Store Cache
```javascript
processingResults: {
    'S2B_MSIL2A_...': {
        results: [...],
        timestamp: Date,
        count: 2
    }
}
```

### Clear Cache
```javascript
// Clear pentru un produs
aiAgentStore.clearResultsForProduct('S2B_MSIL2A_...');

// Cache-ul se refreshuiește automat la:
// - loadProcessingResults()
// - loadAllProcessingResults()
```

## Error Handling

### No Results Found
```javascript
if (response.success && response.results.length === 0) {
    toast.add({
        severity: 'warn',
        summary: 'No Results',
        detail: 'No processing results found for this product.'
    });
}
```

### API Errors
```javascript
try {
    await aiAgentStore.loadProcessingResults(productId);
} catch (error) {
    toast.add({
        severity: 'error',
        summary: 'Error',
        detail: 'Failed to load processing results.'
    });
}
```

### Download Errors
```javascript
// Backend verifică:
// 1. Fișierul există
if (!fs.existsSync(filePath)) {
    return res.status(404).json({
        success: false,
        message: 'File not found'
    });
}

// 2. Este .tif valid
if (!filename.endsWith('.tif')) {
    return res.status(400).json({
        success: false,
        message: 'Invalid file type'
    });
}
```

## Future Enhancements

### 1. Map Visualization (În Dezvoltare)
```javascript
viewOnMap() {
    // TODO: Implement
    // - Încarcă GeoTIFF pe hartă OpenLayers
    // - Color scale pentru înălțime
    // - Interactive legend
}
```

### 2. Results History
- Salvare rezultate în database
- Históric procesări
- Filtrare după dată/zonă

### 3. Batch Operations
- Procesare multiplă paralelă
- Queue management
- Progress tracking global

### 4. Advanced Analytics
- Statistici (min/max/mean height)
- Export CSV cu metadate
- Comparison între produse

## Troubleshooting

### Problema: Nu apar rezultate după procesare

**Verificare:**
```bash
# 1. Verifică dacă fișierele au fost generate
ls -la service.ai-ch-processor/output/

# 2. Verifică logs AI service
docker logs <ai-container-name>

# 3. Verifică console frontend
# Caută: "AI Processing result:"
```

**Soluție:**
- Reîncearcă procesarea
- Verifică că AI service rulează: `curl http://localhost:5556/health`

### Problema: Download nu funcționează

**Verificare:**
```bash
# Test endpoint direct
curl -v http://localhost:5555/api/ai/download/filename.tif
```

**Soluție:**
- Verifică permisiuni fișiere în `output/`
- Verifică că backend are acces la directorul output

### Problema: Iconița rezultate nu apare

**Cauză:** `hasResultsForProduct()` returnează `false`

**Soluție:**
```javascript
// Forțează reload rezultate
await aiAgentStore.loadProcessingResults(productId);
```

## Sumary - Quick Reference

| Acțiune | Endpoint | Metodă |
|---------|----------|--------|
| Listare rezultate produs | `/api/ai/results/:productId` | GET |
| Listare toate rezultatele | `/api/ai/results` | GET |
| Download GeoTIFF | `/api/ai/download/:filename` | GET |

| Store Action | Descriere |
|--------------|-----------|
| `loadProcessingResults(productId)` | Încarcă rezultate pentru un produs |
| `loadAllProcessingResults()` | Încarcă toate rezultatele |
| `getDownloadUrl(filename)` | Generează URL download |
| `clearResultsForProduct(productId)` | Șterge din cache |

| UI Component | Scope |
|--------------|-------|
| `AppProcessingResultsDialog` | Dialog vizualizare rezultate |
| Buton "View Results" | Toate rezultatele |
| Icon 📊 per imagine | Rezultate specifice produs |

---

**Autor:** GitHub Copilot  
**Data:** 19 Ianuarie 2026  
**Versiune:** 1.0
