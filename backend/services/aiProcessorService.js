const axios = require('axios');
const fs = require('fs');
const path = require('path');
const FormData = require('form-data');
const aiConfig = require('../config/aiProcessorConfig');

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
            
            return {
                success: true,
                agentId: agentId,
                agentName: agent.name,
                data: response.data
            };
            
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
                { timeout: 10000 }
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
    
    /**
     * Listează rezultatele procesării pentru un produs specific
     */
    async getProcessingResults(productId) {
        const outputDir = path.join(__dirname, '../../service.ai-ch-processor/output');
        
        if (!fs.existsSync(outputDir)) {
            return {
                success: false,
                message: 'Output directory not found',
                results: []
            };
        }
        
        try {
            const files = fs.readdirSync(outputDir);
            const productFiles = files.filter(file => 
                file.startsWith(productId) && file.endsWith('.tif')
            );
            
            const results = productFiles.map(filename => {
                const filePath = path.join(outputDir, filename);
                const stats = fs.statSync(filePath);
                
                return {
                    filename: filename,
                    path: filePath,
                    size: stats.size,
                    type: filename.includes('predictions') ? 'predictions' : 'std',
                    createdAt: stats.birthtime,
                    modifiedAt: stats.mtime
                };
            });
            
            return {
                success: true,
                productId: productId,
                count: results.length,
                results: results
            };
        } catch (error) {
            throw new Error(`Failed to list results: ${error.message}`);
        }
    }
    
    /**
     * Listează toate rezultatele disponibile
     */
    async getAllProcessingResults() {
        const outputDir = path.join(__dirname, '../../service.ai-ch-processor/output');
        
        if (!fs.existsSync(outputDir)) {
            return {
                success: false,
                message: 'Output directory not found',
                results: []
            };
        }
        
        try {
            const files = fs.readdirSync(outputDir);
            const tifFiles = files.filter(file => file.endsWith('.tif'));
            
            const groupedResults = {};
            
            tifFiles.forEach(filename => {
                const match = filename.match(/^(S2[AB]_MSIL[12][AC]_\d+T\d+_[^_]+_[^_]+_[^_]+_[^_]+)/);
                if (match) {
                    const productId = match[1];
                    
                    if (!groupedResults[productId]) {
                        groupedResults[productId] = [];
                    }
                    
                    const filePath = path.join(outputDir, filename);
                    const stats = fs.statSync(filePath);
                    
                    groupedResults[productId].push({
                        filename: filename,
                        path: filePath,
                        size: stats.size,
                        type: filename.includes('predictions') ? 'predictions' : 'std',
                        createdAt: stats.birthtime,
                        modifiedAt: stats.mtime
                    });
                }
            });
            
            return {
                success: true,
                count: Object.keys(groupedResults).length,
                results: groupedResults
            };
        } catch (error) {
            throw new Error(`Failed to list all results: ${error.message}`);
        }
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