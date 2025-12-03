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
    requestTimeout: 300000, // 5 minute
    
    // Directory pentru date temporare
    tempDataDir: process.env.TEMP_DATA_DIR || './uploads/ai-temp',
    
    // Directory pentru rezultate
    resultsDir: process.env.RESULTS_DIR || './uploads/ai-results'
};