const axios = require('axios');
const fs = require('fs');
const path = require('path');
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
     */
    async processWithAgent(agentId, inputData) {
        const agent = aiConfig.aiAgents[agentId];
        
        if (!agent) {
            throw new Error(`Agent ${agentId} nu există`);
        }
        
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
            
            // Grupează rezultatele după productId
            const groupedResults = {};
            
            tifFiles.forEach(filename => {
                // Extract product ID (format: S2X_MSIL2A_...)
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
        // areaData poate conține:
        // - coordinates: coordonatele zonei selectate
        // - dataLayerId: ID-ul layer-ului de date
        // - imageFiles: fișierele de imagine
        // - parameters: parametri specifici modelului
        
        const inputData = await this.prepareInputData(agentId, areaData);
        return await this.processWithAgent(agentId, inputData);
    }
    
    /**
     * Pregătește datele de input pentru un agent specific
     */
    async prepareInputData(agentId, areaData) {
        const agent = aiConfig.aiAgents[agentId];
        
        // Logică diferită în funcție de formatul de input al agentului
        switch (agent.inputFormat) {
            case 'sentinel2-safe':
                // Pregătește imagini Sentinel-2
                return {
                    image_filenames: areaData.imageFiles || []
                };
            
            // Adaugă alte formate când implementezi alți agenți
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
