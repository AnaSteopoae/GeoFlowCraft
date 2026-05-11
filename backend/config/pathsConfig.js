const path = require('path');

/**
 * Configurare căi — folosește variabile de environment în Docker,
 * sau căi relative locale pentru development.
 */
module.exports = {
    sharedData: process.env.SHARED_DATA_DIR || path.join(__dirname, '../../shared-data'),
    srOutput: process.env.SR_OUTPUT_DIR || path.join(__dirname, '../../service.ai-sr-processor/output'),
    chmOutput: process.env.CHM_OUTPUT_DIR || path.join(__dirname, '../../service.ai-ch-processor/output'),
    chmChangeResults: process.env.CHM_CHANGE_RESULTS_DIR || path.join(__dirname, '../../shared-data/chm_change_results'),
    cdSrResults: process.env.CD_SR_RESULTS_DIR || path.join(__dirname, '../../service.ai-sr-processor/output/change_detection_results')
};