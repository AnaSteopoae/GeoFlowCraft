const axios = require('axios');
const fs = require('fs');
const path = require('path');
const FormData = require('form-data');
const aiConfig = require('../config/aiProcessorConfig');
const { autoPublishResult } = require('./autoPublishService');
const archiver = require('archiver');

class AIProcessorService {
    
    /**
     * Obține lista tuturor agenților AI disponibili
     */
    getAvailableAgents() {
        return Object.keys(aiConfig.aiAgents).map(agentId => ({
            id: agentId,
            name: aiConfig.aiAgents[agentId].name,
            description: aiConfig.aiAgents[agentId].description,
            inputFormat: aiConfig.aiAgents[agentId].inputFormat,
            outputFormat: aiConfig.aiAgents[agentId].outputFormat
        }));
    }
    
    /**
     * Verifică dacă un agent AI este disponibil
     */
    async checkAgentHealth(agentId) {
        const agent = aiConfig.aiAgents[agentId];
        if (!agent) {
            throw new Error(`Agent ${agentId} nu există`);
        }
        
        try {
            const response = await axios.get(`${agent.url}${agent.endpoints.health}`, {
                timeout: 5000
            });
            return { 
                available: true, 
                status: response.status,
                data: response.data 
            };
        } catch (error) {
            return { 
                available: false, 
                error: error.message 
            };
        }
    }
    
    /**
     * Procesează date folosind un agent AI specific
     * Rută principală — deleghează către metode specifice per agent
     */
    async processWithAgent(agentId, inputData) {
        const agent = aiConfig.aiAgents[agentId];
        
        if (!agent) {
            throw new Error(`Agent ${agentId} nu există`);
        }
        
        // SR are un flow special: descarcă S1, co-registrează, stack, apoi predict
        if (agentId === 'sr-processor') {
            return await this.processWithSR(inputData);
        }
        
        // Change Detection: aplică SR pe 2 scene, apoi compară
        if (agentId === 'cd-processor') {
            return await this.processWithCD(inputData);
        }
        
        // Flow generic (CHM și viitori agenți)
        try {
            const url = `${agent.url}${agent.endpoints.predict}`;
            
            console.log(`Trimit request către ${url} cu data:`, inputData);
            
            const response = await axios.post(url, inputData, {
                headers: {
                    'Content-Type': 'application/json'
                },
                timeout: aiConfig.requestTimeout
            });
            
            const result = {
                success: true,
                agentId: agentId,
                agentName: agent.name,
                data: response.data
            };

            // Publicare automată CHM
            if (agentId === 'ch-processor' && response.data?.output_path) {
                const publishResult = await autoPublishResult({
                    filePath: response.data.output_path,
                    name: `CHM ${new Date().toISOString().substring(0, 10)}`,
                    type: 'chm',
                    description: 'Canopy Height Model'
                });
                if (publishResult.success) {
                    console.log(`[CHM] Publicat pe hartă: ${publishResult.layerName}`);
                }
            }

            return result;
            
        } catch (error) {
            console.error(`Eroare la procesarea cu agent ${agentId}:`, error.message);
            throw new Error(`Procesarea a eșuat: ${error.message}`);
        }
    }

    // ──────────────────────────────────────────────
    // Super Resolution — flow specific
    // ──────────────────────────────────────────────

    /**
     * Flow complet SR:
     * 0. Preprocesare S2 .SAFE → GeoTIFF 4 benzi (B02, B03, B04, B08)
     * 1. Descarcă S1 procesat via Sentinel Hub (serviciul Copernicus)
     * 2. Așteaptă co-registration (background task în Copernicus)
     * 3. Combină S2 + S1 → GeoTIFF 6 benzi (stack)
     * 4. Trimite la serviciul SR /predict/
     * 5. Returnează GeoTIFF super-rezolvat
     * 
     * inputData:
     *   - s2_path: calea .SAFE.zip sau directorul .SAFE (sau GeoTIFF deja procesat)
     *   - bbox: [min_lon, min_lat, max_lon, max_lat]
     *   - target_date: "2023-07-10"
     *   - mode: "fidelity" | "balanced" | "sharp" (default: "balanced")
     *   - alpha: 0.0-1.0 (opțional, suprascrie mode)
     */
    async processWithSR(inputData) {
        const agent = aiConfig.aiAgents['sr-processor'];
        const copernicusUrl = agent.copernicusUrl;
        
        let { s2_path, bbox, target_date, mode = 'balanced', alpha } = inputData;
        
        if (!s2_path || !bbox || !target_date) {
            throw new Error('s2_path, bbox și target_date sunt obligatorii pentru SR');
        }

        console.log(`[SR] Start: s2=${s2_path}, date=${target_date}, mode=${mode}`);

        // ── Pas 0: Preprocesare S2 (.SAFE → GeoTIFF 4 benzi) ──
        // Dacă s2_path e un .zip sau .SAFE, trebuie extras benzile
        if (s2_path.endsWith('.zip') || s2_path.endsWith('.SAFE')) {
            console.log('[SR] Pas 0: Preprocesare S2 .SAFE → GeoTIFF 4 benzi (cropat la bbox)...');
            
            const preprocessResponse = await axios.post(`${copernicusUrl}/preprocess/s2`, {
                safe_path: s2_path,
                bbox: bbox
            }, { timeout: 300000 }); // 5 min timeout (dezarhivare + citire benzi)

            s2_path = preprocessResponse.data.geotiff_path;
            console.log(`[SR] S2 preprocesat: ${s2_path}`);
        }

        // ── Pas 1: Descarcă S1 procesat ──
        console.log('[SR] Pas 1: Descărcare S1 via Sentinel Hub...');
        
        const s1Response = await axios.post(`${copernicusUrl}/download/s1`, {
            bbox: bbox,
            target_date: target_date,
            s2_path: s2_path,
            days_tolerance: 6,
            resolution: 10
        }, { timeout: 120000 });

        const s1TaskId = s1Response.data.task_id;
        console.log(`[SR] S1 task lansat: ${s1TaskId}`);

        // ── Pas 2: Polling status S1 ──
        console.log('[SR] Pas 2: Aștept co-registration S1...');
        
        const s1Result = await this.pollS1Status(copernicusUrl, s1TaskId);
        const s1CoregPath = s1Result.s1_coreg_path;
        
        console.log(`[SR] S1 co-registrat: ${s1CoregPath}`);

        // ── Pas 3: Stack S2 + S1 ──
        console.log('[SR] Pas 3: Combinare S2 + S1 → 6 benzi...');
        
        const stackResponse = await axios.post(`${copernicusUrl}/stack/s2-s1`, {
            s2_path: s2_path,
            s1_path: s1CoregPath
        }, { timeout: 30000 });

        const stackedPath = stackResponse.data.stacked_path;
        console.log(`[SR] Stack complet: ${stackedPath}`);

        // ── Pas 4: Trimite la serviciul SR ──
        console.log(`[SR] Pas 4: Inferență SR (mode=${mode})...`);
        
        const srResult = await this.sendToSRService(stackedPath, mode, alpha);
        
        console.log(`[SR] Complet! Output: ${srResult.outputPath}`);

         // Publicare automată pe hartă
        const dateStr = target_date || new Date().toISOString().substring(0, 10);
        const resultName = inputData.resultName || `SR ${mode} ${dateStr} ${Date.now().toString(36)}`;
        const publishResult = await autoPublishResult({
            filePath: srResult.outputPath,
            name: resultName,
            type: 'sr',
            description: `Super-rezoluție ${mode} (α=${srResult.alpha}) din ${dateStr}`
        });
        if (publishResult.success) {
            console.log(`[SR] Publicat pe hartă: ${publishResult.layerName}`);
        }

        return {
            success: true,
            agentId: 'sr-processor',
            agentName: agent.name,
            data: {
                sr_output: srResult.outputPath,
                mode: mode,
                alpha: srResult.alpha,
                processing_time: srResult.processingTime,
                input_size: srResult.inputSize,
                output_size: srResult.outputSize
            }
        };
    }

    /**
     * Polling status S1 — așteaptă până S1 e descărcat și co-registrat
     */
    async pollS1Status(copernicusUrl, taskId, maxWaitMs = 180000) {
        const startTime = Date.now();
        const pollInterval = 2000; // 2 secunde

        while (Date.now() - startTime < maxWaitMs) {
            const statusResponse = await axios.get(
                `${copernicusUrl}/status/s1/${taskId}`,
                { timeout: 30000 }
            );
            
            const status = statusResponse.data;

            if (status.status === 'completed') {
                return status;
            }
            
            if (status.status === 'failed') {
                throw new Error(`S1 download eșuat: ${status.error}`);
            }

            console.log(`[SR] S1 status: ${status.progress}`);
            
            // Așteaptă înainte de următorul poll
            await new Promise(resolve => setTimeout(resolve, pollInterval));
        }

        throw new Error(`S1 download timeout după ${maxWaitMs / 1000}s`);
    }

    /**
     * Trimite GeoTIFF-ul stacked la serviciul SR via multipart/form-data
     */
    async sendToSRService(stackedPath, mode, alpha) {
        const agent = aiConfig.aiAgents['sr-processor'];
        const url = `${agent.url}${agent.endpoints.predict}`;

        // Construiește query params
        const params = { mode: mode };
        if (alpha !== undefined && alpha !== null) {
            params.alpha = alpha;
        }

        // Trimite fișierul ca multipart/form-data
        const form = new FormData();
        form.append('file', fs.createReadStream(stackedPath), {
            filename: path.basename(stackedPath),
            contentType: 'image/tiff'
        });

        console.log(`[SR] POST ${url}?mode=${mode}`);

        const response = await axios.post(url, form, {
            params: params,
            headers: {
                ...form.getHeaders()
            },
            responseType: 'arraybuffer', // primim GeoTIFF înapoi
            timeout: aiConfig.requestTimeout,
            maxContentLength: Infinity,
            maxBodyLength: Infinity
        });

        // Salvează output-ul
        const outputDir = path.join(__dirname, '../../service.ai-sr-processor/output');
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }

        const outputFilename = `sr_${mode}_${path.basename(stackedPath)}`;
        const outputPath = path.join(outputDir, outputFilename);
        fs.writeFileSync(outputPath, response.data);

        // Extrage metadate din headers
        const processingTime = response.headers['x-processing-time'] || 'unknown';
        const srAlpha = response.headers['x-sr-alpha'] || mode;

        return {
            outputPath: outputPath,
            alpha: srAlpha,
            processingTime: processingTime,
            inputSize: `stacked 6 bands`,
            outputSize: `${response.data.length} bytes`
        };
    }

    // ──────────────────────────────────────────────
    // Change Detection — flow specific
    // ──────────────────────────────────────────────

    /**
     * Flow complet Change Detection:
     * 1. Aplică SR pe scena T1 (dacă nu e deja SR)
     * 2. Aplică SR pe scena T2 (dacă nu e deja SR)
     * 3. Apelează endpoint-ul /change-detection cu cele două SR outputs
     * 4. Returnează rezultatele (magnitudine, ΔNDVI, mască, statistici)
     *
     * inputData:
     *   - scene_t1: { s2_path, bbox, target_date } — scena mai veche
     *   - scene_t2: { s2_path, bbox, target_date } — scena mai recentă
     *   - mode: "fidelity" | "balanced" | "sharp" (default: "balanced")
     *   - threshold_method: "otsu" | "percentile" (default: "otsu")
     *
     * SAU (dacă SR e deja aplicat):
     *   - sr_t1_path: calea GeoTIFF SR T1
     *   - sr_t2_path: calea GeoTIFF SR T2
     *   - threshold_method: "otsu" | "percentile"
     */
    async processWithCD(inputData) {
        const agent = aiConfig.aiAgents['cd-processor'];
        const copernicusUrl = agent.copernicusUrl;

        let { sr_t1_path, sr_t2_path, scene_t1, scene_t2, 
            mode = 'fidelity', threshold_method = 'otsu' } = inputData;

        console.log(`[CD] Start change detection`);

        // ── Dacă primim scene raw, aplică SR pe ambele ──
        if (!sr_t1_path && scene_t1) {
            console.log('[CD] Pas 1: Aplicare SR pe scena T1...');
            const srResult1 = await this.processWithSR({
                ...scene_t1,
                mode: mode
            });
            sr_t1_path = srResult1.data.sr_output;
            console.log(`[CD] SR T1 complet: ${sr_t1_path}`);
        }

        if (!sr_t2_path && scene_t2) {
            console.log('[CD] Pas 2: Aplicare SR pe scena T2...');
            const srResult2 = await this.processWithSR({
                ...scene_t2,
                mode: mode
            });
            sr_t2_path = srResult2.data.sr_output;
            console.log(`[CD] SR T2 complet: ${sr_t2_path}`);
        }

        if (!sr_t1_path || !sr_t2_path) {
            throw new Error('sr_t1_path și sr_t2_path sunt obligatorii (sau scene_t1 + scene_t2)');
        }

        // ── Apelează change detection ──
        console.log(`[CD] Pas 3: CVA + ΔNDVI (metoda: ${threshold_method})...`);

        const cdResponse = await axios.post(`${copernicusUrl}/change-detection`, {
            sr_t1_path: sr_t1_path,
            sr_t2_path: sr_t2_path,
            threshold_method: threshold_method
        }, { timeout: 120000 });

        const result = cdResponse.data.results;
        console.log(`[CD] Complet! Schimbări: ${result.statistics.changed_area_ha} ha (${result.statistics.change_percentage}%)`);

        // Creează arhivă ZIP cu toate rezultatele
        const resultsDir = path.dirname(result.magnitude_path);
        const userResultName = inputData.resultName || `cd_sr_${new Date().toISOString().substring(0, 10)}`;
        const archiveName = userResultName.replace(/[^a-zA-Z0-9_\-]/g, '_');
        let archivePath = null;
        try {
            archivePath = await this._createResultsArchive(resultsDir, archiveName);
        } catch (archiveErr) {
            console.warn(`[CD] Nu am putut crea arhiva: ${archiveErr.message}`);
        }

        return {
            success: true,
            agentId: 'cd-processor',
            agentName: agent.name,
            data: {
                magnitude_path: result.magnitude_path,
                delta_ndvi_path: result.delta_ndvi_path,
                change_mask_path: result.change_mask_path,
                ndvi_t1_path: result.ndvi_t1_path,
                ndvi_t2_path: result.ndvi_t2_path,
                archive_path: archivePath,
                statistics: result.statistics
            }
        };
    }

    /**
     * Obține modurile SR disponibile
     */
    async getSRModes() {
        const agent = aiConfig.aiAgents['sr-processor'];
        try {
            const response = await axios.get(
                `${agent.url}${agent.endpoints.modes}`,
                { timeout: 5000 }
            );
            return response.data;
        } catch (error) {
            console.error('Eroare la obținerea modurilor SR:', error.message);
            throw new Error(`Nu pot obține modurile SR: ${error.message}`);
        }
    }
    
    /**
     * Procesează imagini Sentinel-2 pentru canopy height
     */
    async processSentinel2Images(imageFilenames) {
        return await this.processWithAgent('ch-processor', {
            image_filenames: imageFilenames
        });
    }
    

    async _createResultsArchive(resultsDir, archiveName) {
        return new Promise((resolve, reject) => {
            const outputPath = path.join(path.dirname(resultsDir), `${archiveName}.zip`);
            const output = fs.createWriteStream(outputPath);
            const archive = archiver('zip', { zlib: { level: 6 } });

            output.on('close', () => {
                const sizeMB = (archive.pointer() / 1024 / 1024).toFixed(1);
                console.log(`[CD] Arhivă creată: ${outputPath} (${sizeMB} MB)`);
                resolve(outputPath);
            });

            archive.on('error', (err) => reject(err));
            archive.pipe(output);

            // Adaugă toate fișierele .tif din director
            const files = fs.readdirSync(resultsDir).filter(f => f.endsWith('.tif'));
            for (const file of files) {
                archive.file(path.join(resultsDir, file), { name: file });
            }

            archive.finalize();
        });
    }


    /**
     * Listează rezultatele procesării pentru un produs specific
     */
     _getOutputDirs() {
        return [
            {
                dir: path.join(__dirname, '../../service.ai-ch-processor/output'),
                service: 'chm',
                typeDetector: (filename) => {
                    if (filename.includes('predictions')) return 'Canopy Height';
                    if (filename.includes('std')) return 'Uncertainty (Std Dev)';
                    return 'CHM Output';
                }
            },
            {
                dir: path.join(__dirname, '../../service.ai-sr-processor/output'),
                service: 'sr',
                typeDetector: (filename) => {
                    if (filename.includes('_rgb')) return null;  // Skip RGB files
                    if (filename.includes('sr_fidelity')) return 'SR Fidelity';
                    if (filename.includes('sr_balanced')) return 'SR Balanced';
                    if (filename.includes('sr_sharp')) return 'SR Sharp';
                    return 'SR Output';
                }
            },
            {
                dir: path.join(__dirname, '../../service.ai-sr-processor/output/change_detection_results'),
                service: 'cd-sr',
                typeDetector: (filename) => {
                    if (filename.endsWith('.zip')) return 'CD Results Archive';
                    if (filename.includes('cva_magnitude')) return 'CVA Magnitude';
                    if (filename.includes('delta_ndvi')) return 'Delta NDVI';
                    if (filename.includes('change_mask')) return 'Change Mask';
                    if (filename.includes('ndvi_t1')) return 'NDVI T1';
                    if (filename.includes('ndvi_t2')) return 'NDVI T2';
                    return 'CD-SR Output';
                }
            },
            {
                dir: path.join(__dirname, '../../shared-data/chm_change_results'),
                service: 'cd-chm',
                typeDetector: (filename) => {
                    if (filename.endsWith('.zip')) return 'CD Results Archive';
                    if (filename.includes('delta_chm')) return 'Delta CHM';
                    if (filename.includes('deforestation')) return 'Deforestation Mask';
                    if (filename.includes('regrowth')) return 'Regrowth Mask';
                    if (filename.includes('classification')) return 'Change Classification';
                    return 'CD-CHM Output';
                }
            }
        ];
    }

    async getProcessingResults(productId) {
        const outputDirs = this._getOutputDirs();
        const results = [];

        for (const { dir, service, typeDetector } of outputDirs) {
            if (!fs.existsSync(dir)) continue;

            try {
                const files = fs.readdirSync(dir);
                const productFiles = files.filter(file =>
                    (file.endsWith('.tif') || file.endsWith('.zip')) && file.includes(productId)
                );

                for (const filename of productFiles) {
                    const type = typeDetector(filename);
                    if (!type) continue;  // Skip files rejected by typeDetector (e.g. RGB)
                    const filePath = path.join(dir, filename);
                    const stats = fs.statSync(filePath);
                    results.push({
                        filename: filename,
                        path: filePath,
                        size: stats.size,
                        type: type,
                        service: service,
                        createdAt: stats.birthtime,
                        modifiedAt: stats.mtime
                    });
                }
            } catch (error) {
                console.warn(`Error scanning ${dir}: ${error.message}`);
            }
        }

        return {
            success: true,
            productId: productId,
            count: results.length,
            results: results
        };
    }

    async getAllProcessingResults() {
        const outputDirs = this._getOutputDirs();
        const groupedResults = {};

        for (const { dir, service, typeDetector } of outputDirs) {
            if (!fs.existsSync(dir)) continue;

            try {
                const files = fs.readdirSync(dir);
                const tifFiles = files.filter(file => file.endsWith('.tif') || file.endsWith('.zip'));

                for (const filename of tifFiles) {
                    const type = typeDetector(filename);
                    if (!type) continue;  // Skip files rejected by typeDetector (e.g. RGB
                    let productId = null;

                    const s2Match = filename.match(/(S2[AB]_MSIL[12][AC]_\d+T\d+_[^_]+_[^_]+_[^_]+_[^.]+)/);
                    if (s2Match) {
                        productId = s2Match[1];
                    } else if (service === 'cd-sr' || service === 'cd-chm') {
                        productId = `change_detection_${service}`;
                    } else {
                        productId = 'other';
                    }

                    if (!groupedResults[productId]) {
                        groupedResults[productId] = [];
                    }

                    const filePath = path.join(dir, filename);
                    const stats = fs.statSync(filePath);

                    groupedResults[productId].push({
                        filename: filename,
                        path: filePath,
                        size: stats.size,
                        type: type,
                        service: service,
                        createdAt: stats.birthtime,
                        modifiedAt: stats.mtime
                    });
                }
            } catch (error) {
                console.warn(`Error scanning ${dir}: ${error.message}`);
            }
        }

        return {
            success: true,
            count: Object.keys(groupedResults).length,
            results: groupedResults
        };
    }

      findResultFile(filename) {
        const outputDirs = this._getOutputDirs();
        for (const { dir } of outputDirs) {
            // Caută în directorul specificat
            const filePath = path.join(dir, filename);
            if (fs.existsSync(filePath)) {
                return filePath;
            }
            // Caută și un nivel deasupra (pentru arhive ZIP)
            const parentPath = path.join(path.dirname(dir), filename);
            if (fs.existsSync(parentPath)) {
                return parentPath;
            }
        }
        return null;
    }
    
    /**
     * Procesează o zonă selectată de utilizator cu modelul ales
     */
    async processSelectedArea(agentId, areaData) {
        const inputData = await this.prepareInputData(agentId, areaData);
        return await this.processWithAgent(agentId, inputData);
    }
    
    /**
     * Pregătește datele de input pentru un agent specific
     */
    async prepareInputData(agentId, areaData) {
        const agent = aiConfig.aiAgents[agentId];
        
        switch (agent.inputFormat) {
            case 'sentinel2-safe':
                return {
                    image_filenames: areaData.imageFiles || []
                };
            
            case 'sentinel2-s1-stack':
                // SR are nevoie de bbox, data și calea S2
                return {
                    s2_path: areaData.s2_path,
                    bbox: areaData.bbox,
                    target_date: areaData.target_date,
                    mode: areaData.mode || 'balanced',
                    alpha: areaData.alpha
                };

            case 'sr-temporal-pair':
                // Change Detection: două scene + parametri
                return {
                    scene_t1: areaData.scene_t1,
                    scene_t2: areaData.scene_t2,
                    sr_t1_path: areaData.sr_t1_path,
                    sr_t2_path: areaData.sr_t2_path,
                    mode: areaData.mode || 'balanced',
                    threshold_method: areaData.threshold_method || 'otsu'
                };

            default:
                return areaData;
        }
    }
    
    /**
     * Asigură-te că directoarele pentru date temporare și rezultate există
     */
    ensureDirectories() {
        const dirs = [aiConfig.tempDataDir, aiConfig.resultsDir];
        dirs.forEach(dir => {
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
        });
    }
}

module.exports = new AIProcessorService();