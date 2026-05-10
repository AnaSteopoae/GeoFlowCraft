const controllerUtils = require("../utils/controllerUtils");
const dataLayerService = require("../services/dataLayerService");
const dataSetService = require("../services/dataSetService");
const workspaceService = require("../services/geoserver/workspaceService");
const storeService = require("../services/geoserver/storeService");
const layerService = require("../services/geoserver/layerService");
const serverConfig = require("../config/serverConfig");
const geoserverConfig = require("../config/geoserverConfig");
const postgresConfig = require("../config/postgresConfig");

const fs = require("fs");
const Readable = require("stream").Readable;
const { NodeSSH } = require("node-ssh");
const axios = require('axios');
const extractZIP = require('extract-zip');
const path = require('path');
const { Client } = require('pg');
const csv = require('csv-parser');

async function getDataLayers(request, response) {
    try {
        const result = await dataLayerService.getDataLayers();
        response.status(200).json({ success: true, dataLayers: result });
    } catch (error) {
        response.status(200).json(controllerUtils.getInternalError(error));
    }
}

async function getDataLayer(request, response) {
    try {
        const dataLayerId = request.params.id;
        const result = await dataLayerService.getDataLayer(dataLayerId);

        response.status(200).json({ success: true, dataLayer: result });
    } catch (error) {
        response.status(200).json(controllerUtils.getInternalError(error));
    }
}

async function createDataLayer(request, response) {
    let newDataLayerId = null;
    try {
        const file = request.file;
        const requestBodyMetadata = JSON.parse(request.body.metadata);
        if(!file) {
            throw "No file uploaded under the field 'file'."
        }
        let dataLayerName = requestBodyMetadata.name;
        let dataLayerDescription = requestBodyMetadata.description;
        
        console.log(`Saving partial DataLayer ('${dataLayerName}') to database...`);
        newDataLayerId = await dataLayerService.createDataLayer({
            name: dataLayerName,
            description: dataLayerDescription
        });
        if(!newDataLayerId) {
            throw "Something went wrong. Couldn't save new data layer to database.";
        }
        
        let layerContent = requestBodyMetadata.content;
        if(!layerContent || layerContent.length < 1) {
            throw "DataLayer's 'content' should have at least one item";
        }
        
        let layerContentItem = layerContent[0];

        // 1. Extract file extension and content
        let fileExtension = null;
        switch (layerContentItem.format?.toLowerCase()) {
            case "tiff/base64":
                fileExtension = "tiff";
                break;
            case "x-zip-compressed/base64":
                fileExtension = "zip";
                break;
            case "csv/base64":
                fileExtension = "csv";
                break;
            default:
                throw `Unknown file content format: '${layerContentItem.format.toLowerCase()}'`
        }
        
        // 2. Rename file
        const filenameWithoutExtension = `${newDataLayerId}`;
        let filename = `${newDataLayerId}.${fileExtension}`;
        const localFilePath = `${serverConfig.baseUploadPath}/${filename}`;
        console.log(`Renaming the file '${serverConfig.baseUploadPath}/${file.originalname}' to '${localFilePath}'...`);
        fs.renameSync(`${serverConfig.baseUploadPath}/${file.originalname}`, localFilePath)
        
        // 3. Upload to GeoServer / Postgres (PostGIS)
        let geoServerPath = null;
        let layerName = `layer_${newDataLayerId}`;
        switch (fileExtension) {
            case "tiff":
                geoServerPath = `${geoserverConfig.vmBaseRemotePath}/${filename}`;
                console.log(`Uploading file ('${geoServerPath}') to GeoServer's filesystem...`);
                await uploadFileToHost(geoserverConfig.ssh, localFilePath, geoServerPath);
                break;
            case "zip":
                const unzipPath = `${serverConfig.baseUploadPath}/${filenameWithoutExtension}`;
                console.log(`Unziping file ('${localFilePath}') locally to ('${path.resolve(unzipPath)}')...`);
                await extractZIP(localFilePath, { dir: path.resolve(unzipPath) });

                console.log(`Rename files in the directory '${unzipPath}' to have base name as '${filenameWithoutExtension}'`);
                renameAllFilesInDirectory(unzipPath, `layer_${filenameWithoutExtension}`);

                console.log(`Searching for .shp file...`);
                filename = findFirstShpFile(unzipPath);
                if(filename) {
                    console.log(`.shp file detected: '${filename}'`);
                }

                const geoserverDirectoryPath = `${geoserverConfig.vmBaseRemotePath}/${filenameWithoutExtension}`;
                geoServerPath = geoserverDirectoryPath;
                console.log(`Uploading directory ('${geoserverDirectoryPath}') to GeoServer's filesystem...`);
                await uploadDirectoryToHost(geoserverConfig.ssh, unzipPath, geoserverDirectoryPath);
                break;
            case "csv":
                geoServerPath = `${geoserverConfig.vmBaseRemotePath}/${filename}`;
                console.log(`Uploading file ('${geoServerPath}') to GeoServer's filesystem...`);
                await uploadFileToHost(geoserverConfig.ssh, localFilePath, geoServerPath);
                console.log(`Importing .csv to '${layerName}' postgres table...`);
                await importCSVToPostGIS(
                    localFilePath, 
                    layerName,
                    layerContentItem.srs ?? 'EPSG:4326',
                    layerContentItem.latColumn ?? 'lat', layerContentItem.lonColumn ?? 'lon', 
                    layerContentItem.otherColumns
                );
                break;
            default:
                throw `Unknown file extension: '${fileExtension}'`;
        }

        // 4. Create workspace
        const workspaceName = requestBodyMetadata.geoserver?.workspace ?? geoserverConfig.defaultWorkspace;
        let workspace = await workspaceService.getWorkspace(workspaceName);
        if(!workspace) {
            console.log(`Creating GeoServer workspace '${workspaceName}'...`);
            await workspaceService.createWorkspace({
                name: workspaceName
            });
        }

        // 5. Create store
        const storeName = requestBodyMetadata.geoserver?.store?.name ?? `store_${newDataLayerId}`;
        let storeType = requestBodyMetadata.geoserver?.store?.type;
        let storeCreateUrl = null;
        if(!storeType) {
            switch (fileExtension) {
                case "tiff":
                    storeType = "GeoTIFF"
                    break;
                case "zip":
                    storeType = "Shapefile";
                    break;
                case "csv":
                    storeType = "PostGIS";
                    break;
                default:
                    throw `Unknown file extension: '${fileExtension}'`;
            }
        }

        // Declarate ÎNAINTE de switch — folosite în toate branch-urile
        let layerFormat = null;
        let layerSource = null;
        let payload = null;

        switch (storeType) {
            case "GeoTIFF":
                // Binary upload — ocolește sandboxing-ul GeoServer
                console.log(`Creating GeoServer store '${storeName}' via binary upload...`);
                const tiffFilePath = `${serverConfig.baseUploadPath}/${filenameWithoutExtension}.tiff`;
                const tiffData = fs.readFileSync(tiffFilePath);
                await axios.put(
                    `${geoserverConfig.url}/rest/workspaces/${workspaceName}/coveragestores/${storeName}/file.geotiff`,
                    tiffData,
                    {
                        auth: geoserverConfig.auth,
                        headers: { 'Content-Type': 'image/tiff' },
                        maxContentLength: Infinity,
                        maxBodyLength: Infinity
                    }
                );

                // Detectează numărul de benzi și aplică stilul potrivit
                try {
                    const layerDetails = await axios.get(
                        `${geoserverConfig.url}/rest/workspaces/${workspaceName}/coveragestores/${storeName}/coverages/${storeName}.json`,
                        { auth: geoserverConfig.auth }
                    );
                    const numBands = layerDetails.data?.coverage?.dimensions?.coverageDimension?.length || 0;
                    
                    let styleName = 'raster';
                    if (numBands >= 3) {
                        styleName = 'sr_truecolor';
                    } else if (numBands === 1) {
                        styleName = 'canopy_height';
                    }

                    await axios.put(
                        `${geoserverConfig.url}/rest/layers/${workspaceName}:${storeName}`,
                        { layer: { defaultStyle: { name: styleName } } },
                        {
                            auth: geoserverConfig.auth,
                            headers: { 'Content-Type': 'application/json' }
                        }
                    );
                    console.log(`Applied style '${styleName}' (${numBands} bands) to layer ${storeName}`);
                } catch (styleErr) {
                    console.warn(`Could not apply style: ${styleErr.message}`);
                }

                // GeoServer creează automat store + layer la binary upload
                layerName = storeName;
                layerFormat = "image/png";
                layerSource = "wms";

                // Update DB și return direct
                console.log(`Updating database DataLayer ('${dataLayerName}')...`);
                await dataLayerService.updateDataLayer({
                    id: newDataLayerId,
                    name: dataLayerName,
                    description: dataLayerDescription,
                    geoserver: {
                        url: geoserverConfig.url,
                        workspace: { name: workspaceName },
                        store: { name: storeName, type: storeType },
                        layer: {
                            name: layerName,
                            format: { name: layerFormat },
                            source: layerSource,
                            params: null
                        },
                        files: [{ path: geoServerPath || localFilePath }]
                    }
                });

                let createdDataLayer = await dataLayerService.getDataLayer(newDataLayerId);

                let dSetId = requestBodyMetadata.dataSetId;
                if(dSetId) {
                    await dataSetService.addDataLayer(dSetId, newDataLayerId);
                }

                response.status(200).json({ success: true, dataLayer: createdDataLayer });
                return;

            case "Shapefile":
                storeCreateUrl = `${geoserverConfig.url}/rest/workspaces/${workspaceName}/datastores`;
                payload = {
                    dataStore: {
                        name: storeName,
                        connectionParameters: {
                            entry: [
                                { '@key': 'url', $: `file:${geoserverConfig.baseRemotePath}/${filenameWithoutExtension}/${filename}` },
                            ],
                        },
                        type: 'Shapefile',
                        enabled: true
                    }
                }
                break;
            case "PostGIS":
                storeCreateUrl = `${geoserverConfig.url}/rest/workspaces/${workspaceName}/datastores`;
                payload = {
                    dataStore: {
                        name: storeName,
                        type: 'PostGIS',
                        enabled: true,
                        connectionParameters: {
                            entry: [
                                { "@key": "host", "$": postgresConfig.host },
                                { "@key": "port", "$": postgresConfig.port.toString() },
                                { "@key": "database", "$": postgresConfig.database },
                                { "@key": "user", "$": postgresConfig.user },
                                { "@key": "passwd", "$": postgresConfig.password },
                                { "@key": "schema", "$": "public" },
                                { "@key": "Expose primary keys", "$": "true" },
                                { "@key": "Estimated extends", "$": "true" },
                                { "@key": "validate connections", "$": "true" },
                                { "@key": "Loose bbox", "$": "true" },
                                { "@key": "preparedStatements", "$": "false" }
                            ]
                        }
                    }
                };
                break;
            default:
                throw `Unknown store type: '${storeType}'`;
        }

        // Pentru Shapefile și PostGIS — flow-ul vechi cu POST JSON
        console.log(`Creating GeoServer store '${storeName}'...`);
        await axios.post(
            storeCreateUrl, 
            payload, 
            {
                auth: geoserverConfig.auth,
                headers: { 'Content-Type': 'application/json' }
            }
        );

        // 6. Create layer (doar pentru Shapefile și PostGIS — GeoTIFF face return mai sus)
        console.log(`Creating layer '${layerName}'...`)
        switch (storeType) {
            case "Shapefile":
                layerFormat = "image/png"
                layerSource = "wms";
                await layerService.createLayer({
                    workspaceName: workspaceName,
                    store: {
                        name: storeName,
                        type: "datastore"
                    },
                    layer: {
                        name: layerName
                    }
                })
                break;
            case "PostGIS":
                layerFormat = "image/png";
                layerSource = "wms";
                let layerAttributes = [
                    {
                        name: "geom",
                        binding: "org.locationtech.jts.geom.Point",
                        nillable: false
                    },
                    {
                        name: layerContentItem.latColumn ?? 'lat',
                        binding: "java.lang.Double",
                        nillable: true
                    },
                    {
                        name: layerContentItem.lonColumn ?? 'lon',
                        binding: "java.lang.Double",
                        nillable: true
                    }
                ];
                if(layerContentItem.otherColumns?.length > 0) {
                    for (const otherColumn of layerContentItem.otherColumns) {
                        try {                            
                            let binding = null;
                            switch (otherColumn.type) {
                                case "FLOAT":
                                    binding = "java.lang.Double";
                                    break;
                                default:
                                    throw `Unknown attribute type '${otherColumn.type}'`;
                            }
                            layerAttributes.push({
                                name: otherColumn.key,
                                binding: binding,
                                nillable: true
                            });
                        } catch (error) {
                            console.log(error);
                        }
                    }
                }
                await layerService.createLayer({
                    workspaceName,
                    store: {
                        name: storeName,
                        type: "datastore"
                    },
                    layer: {
                        name: layerName,
                        title: layerName
                    },
                    nativeCRS: layerContentItem.srs ?? 'EPSG:4326',
                    srs: layerContentItem.srs ?? 'EPSG:4326',
                    attributes: {
                        attribute: layerAttributes
                    }
                });
                break;
            default:
                throw `Unknown store type: '${storeType}'`;
        }

        // 7. Update DataLayer from the database
        console.log(`Updating database DataLayer ('${dataLayerName}') with missing information...`);
        await dataLayerService.updateDataLayer({
            id: newDataLayerId,
            name: dataLayerName,
            description: dataLayerDescription,
            geoserver: {
                url: geoserverConfig.url,
                workspace: {
                    name: workspaceName
                },
                store: {
                    name: storeName,
                    type: storeType
                },
                layer: {
                    name: layerName,
                    format: {
                        name: layerFormat
                    },
                    source: layerSource,
                    params: null
                },
                files: [
                    {
                        path: geoServerPath
                    }
                ]}
            }
        );

        let newCreatedDataLayer = await dataLayerService.getDataLayer(newDataLayerId);

        // 8. Add dataLayer to dataSet
        let dataSetId = requestBodyMetadata.dataSetId;
        if(dataSetId) {
            console.log(`Adding DataLayer ('${newDataLayerId}') to DataSet ('${dataSetId}')...`);
            await dataSetService.addDataLayer(dataSetId, newDataLayerId)
        }
    
        response.status(200).json({ success: true, dataLayer: newCreatedDataLayer });
    } catch (error) {
        console.log(error);
        response.status(200).json(controllerUtils.getInternalError(error));
        try {
            if(newDataLayerId) {
                console.log("Deleting the partial layer...");
                await dataLayerService.deleteDataLayer({ id: newDataLayerId });
            }
        } catch (error) {
            console.log(error);    
        }
    }
}

async function deleteDataLayer(request, response) {
    try {
        let dataLayerId = request.body.id;
        console.log(dataLayerId);

        let dataSets = await dataSetService.getDataSets({ layerId: dataLayerId });
        console.log(`Removing DataLayer from DataSets...`);

        if(dataSets?.length > 0) {
            for (const dataSet of dataSets) {
                console.log(`Removing DataLayer ${dataLayerId} from DataSet ${dataSet.id}...`);
                await dataSetService.removeDataLayer(dataSet.id, dataLayerId);
            }
        }

        let dataLayer = await dataLayerService.getDataLayer(dataLayerId);

        if(!dataLayer) return;

        try {            
            console.log("Deleting DataLayerFiles...")
            console.log(dataLayer.geoserver?.files);
            if(dataLayer.geoserver?.files?.length > 0) {
                for (const file of dataLayer.geoserver.files) {
                    console.log(`Deleting ${file.path}`)
                    await deleteFileOnHost(geoserverConfig.ssh, file.path);
                }
            }
        } catch (error) {
            console.log(error);
        }

        try {
            console.log(`Deleting DataLayer from GeoServer: ${dataLayer.geoserver?.layer?.name}`);
            await layerService.deleteLayer({
                workspaceName: dataLayer.geoserver.workspace.name,
                layerName: dataLayer.geoserver.layer.name
            });
        } catch (error) {
            console.log(error);
        }

        console.log(`Deleting DataLayer's store from GeoServer: ${dataLayer.geoserver.store.name}`);
        let storeType = null;
        switch(dataLayer.geoserver.store.type){
            case "GeoTIFF":
                storeType = "coverage";
                break;
            case "Shapefile":
            case "PostGIS":
                storeType = "datastore";
                break;
            default:
                throw "Unknown store type!"
        }
        try {
            await storeService.deleteStore(dataLayer.geoserver.workspace.name, dataLayer.geoserver.store.name, storeType);
        } catch (error) {
            console.log(error)
        }

        console.log(`Deleting DataLayer from database: ${dataLayerId}`);
        await dataLayerService.deleteDataLayer({ id: dataLayerId });

        response.status(200).json({ success: true });
    } catch (error) {
        response.status(200).json(controllerUtils.getInternalError(error));
    }
}

async function importCSVToPostGIS(csvFilePath, tableName, srs, latColumn, lonColumn, otherColumns) {
    const client = new Client(postgresConfig);
    await client.connect();

    try {
        let queryCreateTable = `CREATE TABLE ${tableName}`;
        queryCreateTable += `(id SERIAL PRIMARY KEY, geom GEOMETRY(POINT, ${srs.split(":")[1] ?? '4326'})`
        queryCreateTable += `, ${latColumn} FLOAT`
        queryCreateTable += `, ${lonColumn} FLOAT`;

        if(otherColumns?.length > 0) {
            for (const otherColumn of otherColumns) {
                switch(otherColumn.type) {
                    case 'FLOAT':
                        queryCreateTable += `, ${otherColumn.key} FLOAT`
                        break;
                    default:
                        throw `Column type '${otherColumn.type}' not implemented`;
                }
            }
        }

        queryCreateTable += `);`;

        await client.query(queryCreateTable);

        const stream = fs.createReadStream(csvFilePath)
            .pipe((await import('strip-bom-stream')).default())
            .pipe(csv())
            .on('data', async (row) => {
                const lat = row[`${latColumn}`];
                const lon = row[`${lonColumn}`];

                if (!lat || !lon) {
                    console.warn('Skipping row with missing coordinates:', row);
                    return;
                }
                let values = [lat, lon];

                let queryInsertColumns = `INSERT INTO ${tableName} (geom, lat, lon`;
                let queryInsertValues = `VALUES (ST_SetSRID(ST_MakePoint($2, $1), ${srs.split(":")[1] ?? '4326'}), $1, $2`;

                let columnIndex = 3;
                if(otherColumns?.length > 0) {
                    for(const otherColumn of otherColumns) {
                        queryInsertColumns += `, ${otherColumn.key}`
                        queryInsertValues += `, $${columnIndex++}`;
                        values.push(row[`${otherColumn.key}`]);
                    }
                }
                queryInsertColumns += `)`;
                queryInsertValues += `)`;
                queryInsert = `${queryInsertColumns} ${queryInsertValues}`;

                await client.query(queryInsert, values);
            });

        await new Promise((resolve) => stream.on('end', resolve));

        await client.query(`
            CREATE INDEX idx_${tableName}_geom ON ${tableName} USING GIST(geom);
        `);

        return tableName;
    } finally {
        await client.end();
    }
}

async function uploadFileToHost(hostConfig, localFilePath, remoteFilePath) {
    if (hostConfig.host === 'localhost' || hostConfig.host === '127.0.0.1') {
        try {
            const hostPath = remoteFilePath.replace('/opt/geoserver/data_dir', 
                path.join(__dirname, '../data_geoserver'));
            
            const dir = path.dirname(hostPath);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
            
            fs.copyFileSync(localFilePath, hostPath);
            console.log(`File copied locally to: ${hostPath}`);
            return;
        } catch (error) {
            console.error(`Error copying file locally:`, error.message);
            throw error;
        }
    }
    
    const sshClient = new NodeSSH();
    try {
        await sshClient.connect(hostConfig);
        console.log(`Connected to host server '${hostConfig.host}'.`);

        await sshClient.putFile(localFilePath, remoteFilePath);
        console.log(`File uploaded to host server '${hostConfig.host}':`, remoteFilePath);
    } catch (error) {
        console.error(`Error uploading file to host '${hostConfig.host}':`, error.message);
        throw error;
    } finally {
        sshClient.dispose();
    }
}

async function uploadDirectoryToHost(hostConfig, localDirPath, remoteDirPath) {
    if (hostConfig.host === 'localhost' || hostConfig.host === '127.0.0.1') {
        try {
            const hostPath = remoteDirPath.replace('/opt/geoserver/data_dir', 
                path.join(__dirname, '../data_geoserver'));
            
            const parentDir = path.dirname(hostPath);
            if (!fs.existsSync(parentDir)) {
                fs.mkdirSync(parentDir, { recursive: true });
            }
            
            copyDirectoryRecursive(localDirPath, hostPath);
            console.log(`Directory copied locally to: ${hostPath}`);
            return;
        } catch (error) {
            console.error(`Error copying directory locally:`, error.message);
            throw error;
        }
    }
    
    const sshClient = new NodeSSH();
    try {
        await sshClient.connect(hostConfig);
        console.log(`Connected to host server '${hostConfig.host}'.`);

        await sshClient.putDirectory(localDirPath, remoteDirPath, {
            recursive: true,
            concurrency: 5,
        });

        console.log(`Directory uploaded to host server '${hostConfig.host}':`, remoteDirPath);
    } catch (error) {
        console.error(`Error uploading directory to host '${hostConfig.host}':`, error.message);
        throw error;
    } finally {
        sshClient.dispose();
    }
}

function copyDirectoryRecursive(source, destination) {
    if (!fs.existsSync(destination)) {
        fs.mkdirSync(destination, { recursive: true });
    }
    
    const entries = fs.readdirSync(source, { withFileTypes: true });
    
    for (const entry of entries) {
        const srcPath = path.join(source, entry.name);
        const destPath = path.join(destination, entry.name);
        
        if (entry.isDirectory()) {
            copyDirectoryRecursive(srcPath, destPath);
        } else {
            fs.copyFileSync(srcPath, destPath);
        }
    }
}

async function deleteFileOnHost(hostConfig, remoteFilePath) {
    if (hostConfig.host === 'localhost' || hostConfig.host === '127.0.0.1') {
        try {
            const hostPath = remoteFilePath.replace('/opt/geoserver/data_dir', 
                path.join(__dirname, '../data_geoserver'));
            
            if (fs.existsSync(hostPath)) {
                if (fs.lstatSync(hostPath).isDirectory()) {
                    fs.rmSync(hostPath, { recursive: true, force: true });
                } else {
                    fs.unlinkSync(hostPath);
                }
                console.log(`Deleted locally: ${hostPath}`);
            }
            return;
        } catch (error) {
            console.error(`Error deleting file/directory locally:`, error.message);
            throw error;
        }
    }
    
    const sshClient = new NodeSSH();
    try {
        await sshClient.connect(hostConfig);
        console.log(`Connected to host server '${hostConfig.host}'.`);

        console.log(`Deleting file/directory on host '${hostConfig.host}': ${remoteFilePath}`)
        let result = await sshClient.execCommand(`rm -rf "${remoteFilePath}"`);
    } catch (error) {
        console.error(`Error deleting file/directory to host '${hostConfig.host}':`, error.message);
        throw error;
    } finally {
        sshClient.dispose();
    } 
}

function findFirstShpFile(directory) {
    try {
        const files = fs.readdirSync(directory);
        for (const file of files) {
            if (path.extname(file).toLowerCase() === '.shp') {
                return file;
            }
        }
        return null;
    } catch (err) {
        console.error('Error reading directory:', err);
        return null;
    }
}

async function renameFile(oldPath, newName, keepExtension = true) {
    try {
        const dir = path.dirname(oldPath);
        let finalName = newName;
        
        if (keepExtension) {
            const ext = path.extname(oldPath);
            finalName = path.basename(newName, path.extname(newName)) + ext;
        }
        
        const newPath = path.join(dir, finalName);
        await fs.rename(oldPath, newPath);
        return newPath;
    } catch (err) {
        console.error(`Error renaming ${oldPath} to ${newName}:`, err);
        throw err;
    }
}

function renameAllFilesInDirectory(directory, newBaseName) {
    const results = [];
    
    try {
        const files = fs.readdirSync(directory);
        
        let counter = 1;
        const usedExtensions = new Set();
        
        files.forEach(file => {
            const oldPath = path.join(directory, file);
            
            if (fs.statSync(oldPath).isDirectory()) {
                return;
            }
            
            const ext = path.extname(file);
            let finalNewName = newBaseName;
            
            if (usedExtensions.has(ext)) {
                finalNewName = `${newBaseName}_${counter++}`;
            } else {
                usedExtensions.add(ext);
            }
            
            finalNewName += ext;
            
            const newPath = path.join(directory, finalNewName);
            
            try {
                fs.renameSync(oldPath, newPath);
                results.push({
                    oldName: file,
                    newName: finalNewName,
                    success: true
                });
            } catch (err) {
                results.push({
                    oldName: file,
                    newName: finalNewName,
                    success: false,
                    error: err.message
                });
            }
        });
        
        return results;
    } catch (err) {
        console.error(`Error processing directory ${directory}:`, err);
        throw err;
    }
}

module.exports = {
    getDataLayers,
    getDataLayer,
    createDataLayer,
    deleteDataLayer
}