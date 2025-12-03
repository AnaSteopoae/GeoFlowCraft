const express = require('express');
const router = express.Router();
const aiProcessorController = require('../controllers/aiProcessorController');

// Obține lista tuturor agenților AI disponibili
router.get('/agents', aiProcessorController.getAvailableAgents);

// Verifică disponibilitatea unui agent
router.get('/agents/:agentId/health', aiProcessorController.checkAgentHealth);

// Procesează date cu un agent specific
router.post('/agents/:agentId/process', aiProcessorController.processWithAgent);

// Procesează o zonă selectată de utilizator
router.post('/agents/:agentId/process-area', aiProcessorController.processSelectedArea);

// Endpoint special pentru procesare Sentinel-2 (backward compatibility)
router.post('/sentinel2/process', aiProcessorController.processSentinel2Images);

module.exports = router;
