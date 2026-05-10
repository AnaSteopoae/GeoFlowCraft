const axios = require('axios');
const fs = require('fs');
const path = require('path');
const geoserverConfig = require('../config/geoserverConfig');
const dataLayerService = require('../services/dataLayerService');
const dataSetService = require('../services/dataSetService');

// Dataset IDs pentru rezultate automate
const DATASET_IDS = {
    sr: '69ed25e4467f9d5d728de666',
    chm: '69ed25e4467f9d5d728de667',
    'cd-sr-magnitude': '69ff9ed55bbe19d431d805db',
    'cd-sr-ndvi': '69ff9ed55bbe19d431d805db',
    'cd-chm-delta': '69ff9ed55bbe19d431d805dc',
    'cd-chm-deforestation': '69ff9ed55bbe19d431d805dc'
};

// URL serviciul Copernicus (pentru conversie RGB)
const COPERNICUS_URL = 'http://localhost:8000';

/**
 * Publică automat un rezultat GeoTIFF pe hartă.
 * 
 * Flow SR (4 benzi float32):
 * 1. Convertește la RGB uint8 via serviciul Copernicus (scalare percentile)
 * 2. Upload RGB la GeoServer
 * 3. Creează DataLayer în MongoDB
 * 4. Adaugă la dataset-ul "Super Resolution Results"
 * Originalul float32 rămâne pe disc pentru descărcare.
 * 
 * Flow CHM (1 bandă):
 * 1. Upload direct la GeoServer (stilul canopy_height gestionează vizualizarea)
 * 2. Creează DataLayer + adaugă la "Canopy Height Results"
 */
async function autoPublishResult(options) {
    const { filePath, name, type, description = '' } = options;

    if (!fs.existsSync(filePath)) {
        console.warn(`[AutoPublish] Fișierul nu există: ${filePath}`);
        return { success: false, error: 'File not found' };
    }

    try {
        const workspaceName = geoserverConfig.defaultWorkspace || 'default_workspace';

        // 1. Creează DataLayer parțial în MongoDB
        const dataLayerId = await dataLayerService.createDataLayer({
            name: name,
            description: description
        });

        if (!dataLayerId) {
            throw new Error('Nu am putut crea DataLayer în MongoDB');
        }

        const storeName = `store_${dataLayerId}`;
        console.log(`[AutoPublish] Publicare '${name}' (${type}) → store: ${storeName}`);

        // 2. Determină fișierul de upload
        // SR: convertim la RGB uint8 (pentru vizualizare corectă pe hartă)
        // CHM: uploadăm direct (stilul canopy_height gestionează culorile)
        let uploadFilePath = filePath;

        if (type === 'sr') {
            try {
                console.log(`[AutoPublish] Conversie RGB pentru vizualizare...`);
                const convertResponse = await axios.post(`${COPERNICUS_URL}/convert/rgb`, {
                    input_path: filePath
                }, { timeout: 120000 });

                uploadFilePath = convertResponse.data.rgb_path;
                console.log(`[AutoPublish] RGB generat: ${uploadFilePath}`);
            } catch (convertErr) {
                console.warn(`[AutoPublish] Conversie RGB eșuată: ${convertErr.message}. Upload original.`);
                // Fallback: uploadează originalul dacă conversia eșuează
            }
        }

        // 3. Upload binary la GeoServer
        const tiffData = fs.readFileSync(uploadFilePath);
        await axios.put(
            `${geoserverConfig.url}/rest/workspaces/${workspaceName}/coveragestores/${storeName}/file.geotiff`,
            tiffData,
            {
                auth: geoserverConfig.auth,
                headers: { 'Content-Type': 'image/tiff' },
                maxContentLength: Infinity,
                maxBodyLength: Infinity
            }
        );
        console.log(`[AutoPublish] Upload GeoServer OK`);

        // 4. Aplică stilul potrivit
        let styleName = 'raster';
        try {
            // Mapare stil per tip
            const STYLE_MAP = {
                'chm': 'canopy_height',
                'cd-sr-magnitude': 'cd_magnitude',
                'cd-sr-ndvi': 'cd_delta_ndvi',
                'cd-chm-delta': 'cd_delta_ndvi',        // Divergent: roșu (pierdere) → verde (creștere)
                'cd-chm-deforestation': 'cd_deforestation'
            };

            if (STYLE_MAP[type]) {
                styleName = STYLE_MAP[type];
            } else {
                // Auto-detect: 1 bandă → canopy_height, 3 benzi → raster (RGB)
                const layerDetails = await axios.get(
                    `${geoserverConfig.url}/rest/workspaces/${workspaceName}/coveragestores/${storeName}/coverages/${storeName}.json`,
                    { auth: geoserverConfig.auth }
                );
                const numBands = layerDetails.data?.coverage?.dimensions?.coverageDimension?.length || 0;
                if (numBands === 1) styleName = 'canopy_height';
            }

            if (styleName !== 'raster') {
                await axios.put(
                    `${geoserverConfig.url}/rest/layers/${workspaceName}:${storeName}`,
                    { layer: { defaultStyle: { name: styleName } } },
                    {
                        auth: geoserverConfig.auth,
                        headers: { 'Content-Type': 'application/json' }
                    }
                );
            }
            console.log(`[AutoPublish] Stil aplicat: ${styleName}`);
        } catch (styleErr) {
            console.warn(`[AutoPublish] Nu am putut aplica stilul: ${styleErr.message}`);
        }

        // 5. Actualizează DataLayer în MongoDB
        // Stocăm calea ORIGINALĂ (float32) pentru descărcare, nu RGB-ul
        const layerName = storeName;
        await dataLayerService.updateDataLayer({
            id: dataLayerId,
            name: name,
            description: description,
            geoserver: {
                url: geoserverConfig.url,
                workspace: { name: workspaceName },
                store: { name: storeName, type: 'GeoTIFF' },
                layer: {
                    name: layerName,
                    format: { name: 'image/png' },
                    source: 'wms',
                    params: null
                },
                files: [{ path: filePath }]  // Calea originalului, nu RGB
            }
        });

        // 6. Adaugă la dataset-ul corespunzător
        const dataSetId = DATASET_IDS[type];
        if (dataSetId) {
            await dataSetService.addDataLayer(dataSetId, dataLayerId);
            console.log(`[AutoPublish] Adăugat la dataset '${type}': ${dataLayerId}`);
        }

        console.log(`[AutoPublish] ✓ Publicat: ${name} → ${layerName}`);

        return {
            success: true,
            dataLayerId: dataLayerId,
            layerName: layerName,
            storeName: storeName,
            style: styleName
        };

    } catch (error) {
        console.error(`[AutoPublish] Eroare: ${error.message}`);
        return { success: false, error: error.message };
    }
}

module.exports = { autoPublishResult, DATASET_IDS };