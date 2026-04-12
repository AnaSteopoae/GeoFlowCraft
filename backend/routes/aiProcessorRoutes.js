const express = require('express');
const router = express.Router();
const aiProcessorController = require('../controllers/aiProcessorController');

// Obține lista tuturor agenților AI disponibili
router.get('/agents', aiProcessorController.getAvailableAgents);

// Verifică disponibilitatea unui agent
router.get('/agents/:agentId/health', aiProcessorController.checkAgentHealth);

// Obține modurile SR disponibile (fidelity, balanced, sharp + alpha slider)
router.get('/agents/sr-processor/modes', aiProcessorController.getSRModes);

// Procesează date cu un agent specific
router.post('/agents/:agentId/process', aiProcessorController.processWithAgent);

// Procesează o zonă selectată de utilizator
router.post('/agents/:agentId/process-area', aiProcessorController.processSelectedArea);

// Endpoint special pentru procesare Sentinel-2 (backward compatibility)
router.post('/sentinel2/process', aiProcessorController.processSentinel2Images);

// Obține rezultatele procesării pentru un produs specific
router.get('/results/:productId', aiProcessorController.getProcessingResults);

// Obține toate rezultatele disponibile
router.get('/results', aiProcessorController.getAllProcessingResults);

// Descarcă un fișier rezultat
router.get('/download/:filename', aiProcessorController.downloadResult);

module.exports = router;