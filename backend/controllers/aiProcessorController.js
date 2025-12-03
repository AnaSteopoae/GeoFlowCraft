const aiProcessorService = require('../services/aiProcessorService');
const { handleError } = require('../utils/controllerUtils');

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
