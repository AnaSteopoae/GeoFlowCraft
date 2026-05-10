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
            copernicusUrl: 'http://localhost:8000',
            defaultMode: 'balanced'
        },

        'cd-processor': {
            name: 'Change Detection (SR)',
            description: 'Detecția schimbărilor în serii temporale. '
                       + 'Selectează 2 scene din perioade diferite → aplică SR pe ambele → CVA + ΔNDVI.',
            url: 'http://localhost:8000',
            endpoints: {
                predict: '/change-detection',
                health: '/'
            },
            inputFormat: 'sr-temporal-pair',
            outputFormat: 'geotiff',
            copernicusUrl: 'http://localhost:8000'
        },

        'cd-chm-processor': {
        name: 'Deforestation Detection (ΔCHM)',
        description: 'Detect forest canopy changes using CHM comparison',
        url: 'http://localhost:8000',  // Același serviciu Copernicus
        copernicusUrl: 'http://localhost:8000',
        endpoints: {
            predict: '/change-detection/chm',
            health: '/health'
        },
        inputFormat: 'chm-temporal-pair',
        outputFormat: 'geotiff-archive'
    }
    },

    // Timeout pentru requesturi către servicii AI (în ms)
    requestTimeout: 1800000, // 30 minute

    // Directory pentru date temporare
    tempDataDir: process.env.TEMP_DATA_DIR || './uploads/ai-temp',

    // Directory pentru rezultate
    resultsDir: process.env.RESULTS_DIR || './uploads/ai-results'
};