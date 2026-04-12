const aiProcessorService = require('../services/aiProcessorService');
const { handleError } = require('../utils/controllerUtils');
const fs = require('fs');
const path = require('path');

/**
 * Obține lista agenților AI disponibili
 */
exports.getAvailableAgents = async (req, res) => {
    try {
        const agents = aiProcessorService.getAvailableAgents();
        res.status(200).json({
            success: true,
            count: agents.length,
            agents: agents
        });
    } catch (error) {
        handleError(res, error);
    }
};

/**
 * Verifică starea de sănătate a unui agent
 */
exports.checkAgentHealth = async (req, res) => {
    try {
        const { agentId } = req.params;
        const health = await aiProcessorService.checkAgentHealth(agentId);
        res.status(200).json({
            success: true,
            agentId: agentId,
            health: health
        });
    } catch (error) {
        handleError(res, error);
    }
};

/**
 * Procesează date cu un agent specific
 */
exports.processWithAgent = async (req, res) => {
    try {
        const { agentId } = req.params;
        const inputData = req.body;
        
        console.log(`Processing cu agent: ${agentId}`);
        console.log(`Input data:`, inputData);
        
        const result = await aiProcessorService.processWithAgent(agentId, inputData);
        
        res.status(200).json(result);
    } catch (error) {
        handleError(res, error);
    }
};

/**
 * Procesează o zonă selectată de utilizator
 */
exports.processSelectedArea = async (req, res) => {
    try {
        const { agentId } = req.params;
        const { areaData } = req.body;
        
        if (!areaData) {
            return res.status(400).json({
                success: false,
                message: 'areaData este obligatoriu'
            });
        }
        
        console.log(`Processing area cu agent: ${agentId}`);
        
        const result = await aiProcessorService.processSelectedArea(agentId, areaData);
        
        res.status(200).json(result);
    } catch (error) {
        handleError(res, error);
    }
};

/**
 * Obține rezultatele procesării pentru un produs specific
 */
exports.getProcessingResults = async (req, res) => {
    try {
        const { productId } = req.params;
        
        const results = await aiProcessorService.getProcessingResults(productId);
        res.status(200).json(results);
    } catch (error) {
        handleError(res, error);
    }
};

/**
 * Obține toate rezultatele procesării disponibile
 */
exports.getAllProcessingResults = async (req, res) => {
    try {
        const results = await aiProcessorService.getAllProcessingResults();
        res.status(200).json(results);
    } catch (error) {
        handleError(res, error);
    }
};

/**
 * Descarcă un fișier GeoTIFF rezultat
 */
exports.downloadResult = async (req, res) => {
    try {
        const { filename } = req.params;
        const outputDir = path.join(__dirname, '../../service.ai-ch-processor/output');
        const filePath = path.join(outputDir, filename);
        
        // Verifică dacă fișierul există
        if (!fs.existsSync(filePath)) {
            return res.status(404).json({
                success: false,
                message: 'File not found'
            });
        }
        
        // Verifică că este un fișier .tif
        if (!filename.endsWith('.tif')) {
            return res.status(400).json({
                success: false,
                message: 'Invalid file type'
            });
        }
        
        // Setează headerele pentru download
        res.setHeader('Content-Type', 'image/tiff');
        res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
        
        // Trimite fișierul
        const fileStream = fs.createReadStream(filePath);
        fileStream.pipe(res);
        
    } catch (error) {
        handleError(res, error);
    }
};

/**
 * Procesează imagini Sentinel-2 (pentru compatibilitate cu agentul actual)
 */
exports.processSentinel2Images = async (req, res) => {
    try {
        const { image_filenames } = req.body;
        
        if (!image_filenames || !Array.isArray(image_filenames)) {
            return res.status(400).json({
                success: false,
                message: 'image_filenames trebuie să fie un array'
            });
        }
        
        console.log(`Processing Sentinel-2 images:`, image_filenames);
        
        const result = await aiProcessorService.processSentinel2Images(image_filenames);
        
        res.status(200).json(result);
    } catch (error) {
        handleError(res, error);
    }
};

/**
 * Obține modurile SR disponibile (fidelity, balanced, sharp + slider alpha)
 * Frontend-ul apelează acest endpoint pentru a popula selectorul de mod
 */
exports.getSRModes = async (req, res) => {
    try {
        const modes = await aiProcessorService.getSRModes();
        res.status(200).json({
            success: true,
            modes: modes
        });
    } catch (error) {
        handleError(res, error);
    }
};