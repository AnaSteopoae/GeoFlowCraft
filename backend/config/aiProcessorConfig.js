module.exports = {
    aiAgents: {
        'ch-processor': {
            name: 'Canopy Height Processor',
            description: 'Model pentru estimarea înălțimii canopiei folosind imagini Sentinel-2',
            url: 'http://localhost:5556',
            endpoints: {
                predict: '/predict/',
                health: '/health'
            },
            inputFormat: 'sentinel2-safe',
            outputFormat: 'geotiff'
        },
                'sr-processor': {
            name: 'Super Resolution Processor',
            description: 'Super-rezoluție Sentinel-2 (10m → 2.5m) cu fuziune SAR-optică. '
                       + 'Moduri: fidelity (PSNR maxim), balanced, sharp (margini ascuțite).',
            url: 'http://localhost:5557',
            endpoints: {
                predict: '/predict/',
                health: '/health',
                modes: '/modes'
            },
            inputFormat: 'sentinel2-s1-stack',
            outputFormat: 'geotiff',
            // Serviciul Copernicus — pentru descărcarea S1
            copernicusUrl: 'http://localhost:8000',
            // Moduri disponibile (populat dinamic via /modes)
            defaultMode: 'balanced'
        }
        // Template pentru viitori agenți
        // 'model-2': {
        //     name: 'Model Name 2',
        //     description: 'Descriere model 2',
        //     url: process.env.AI_MODEL_2_URL || 'http://localhost:5556',
        //     endpoints: {
        //         predict: '/predict/'
        //     },
        //     inputFormat: 'format-specific',
        //     outputFormat: 'geotiff'
        // }
    },
    
    // Timeout pentru requesturi către servicii AI (în ms)
    // Procesarea pe CPU poate dura 15-30 minute pentru imagini mari
    requestTimeout: 1800000, // 30 minute (1800000 ms)
    
    // Directory pentru date temporare
    tempDataDir: process.env.TEMP_DATA_DIR || './uploads/ai-temp',
    
    // Directory pentru rezultate
    resultsDir: process.env.RESULTS_DIR || './uploads/ai-results'
};