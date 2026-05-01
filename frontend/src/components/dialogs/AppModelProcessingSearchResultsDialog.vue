<template>
    <PrimeDialog v-model:visible="modelProcessingSearchResultsDialog.visible" header="Search results" :closable="false">
        <div class="mb-4">
            <div v-if="areaItems?.length > 0 && compatibleAreaItems.length === 0" class="mb-3 p-3 bg-yellow-500/20 border border-yellow-500 rounded-lg">
                <div class="flex items-center gap-2">
                    <i class="pi pi-exclamation-triangle text-yellow-400"></i>
                    <div class="text-sm">
                        <strong>No compatible images found!</strong><br/>
                        The selected AI model requires Sentinel-2 images, but only other satellite data was found.
                        Try searching for a different area or time period.
                    </div>
                </div>
            </div>
            
            <div v-if="compatibleAreaItems?.length > 0">
                <div class="flex flex-row gap-1 text-lg text-gray-500 border-b border-gray-500 mb-1 px-1">
                    <div class="w-[20px]"></div>
                    <div class="w-[150px] font-bold">Date</div>
                    <div class="w-[150px] font-bold">Cloud cover</div>
                    <div class="w-[200px] font-bold">ID</div>
                    <div class="w-[100px] font-bold">Actions</div>
                </div>
                <div class="max-h-[200px] bg-gray-500/10 overflow-y-auto rounded-lg">
                    <div v-for="(item, index) in compatibleAreaItems"
                        class="flex flex-row gap-1 hover:bg-gray-600 px-1"
                    >
                        <div class="w-[20px] flex items-center">
                            <PrimeCheckbox v-model="item.selected" binary size="small"></PrimeCheckbox>
                        </div>
                        <div class="w-[150px] flex items-center overflow-hidden">
                            {{ moment(item.datetime).format("YYYY-MM-DD HH:mm") }}
                        </div>
                        <div class="w-[150px] flex items-center overflow-hidden">{{ item.stac_item.properties.cloudCover }}</div>
                        <div class="w-[200px] flex items-center overflow-hidden" :title="item.id">
                            {{ extractTileInfo(item.id) }}
                        </div>
                        <div class="w-[100px] flex items-center gap-1">
                            <PrimeButton 
                                v-if="item.visible"
                                @click="hideAreaItemFromMap(item)"
                                icon="pi pi-eye" 
                                variant="text" rounded 
                                severity="success"
                                size="small"
                                v-tooltip.bottom="'Hide area item from map'"
                            />
                            <PrimeButton 
                                v-else
                                @click="showAreaItemOnMap(item)"
                                icon="pi pi-eye-slash"
                                variant="text" rounded 
                                severity="danger"
                                size="small"
                                v-tooltip.bottom="'Show area item on map'"
                            />
                            <PrimeButton 
                                v-if="hasResultsForProduct(item.id)"
                                @click="showResultsForProduct(item.id)"
                                icon="pi pi-chart-bar" 
                                variant="text" rounded 
                                severity="info"
                                size="small"
                                v-tooltip.bottom="'View processing results'"
                            />
                        </div>
                    </div>
                </div>
            </div>
            <div v-else>
                There is not data.
            </div>
        </div>
        <div class="flex justify-between items-center">
            <PrimeButton label="Close" icon="pi pi-times" severity="danger"
                @click="close"
            ></PrimeButton>
            <PrimeButton label="Process" icon="pi pi-microchip" severity="success" 
                @click="process"
                v-tooltip.bottom="(compatibleAreaItems?.filter(areaItem => areaItem.selected == true).length > 0) 
                                    ? 'Process the selected area item(s)' 
                                    : 'Select at least one compatible area item to process'"
                :disabled="!(compatibleAreaItems?.filter(areaItem => areaItem.selected == true).length > 0)"
            ></PrimeButton>
        </div>
        <PrimeToast />
        
        <AppProcessingResultsDialog 
            v-model="showResultsDialog"
            :productId="selectedProductId"
        />
    </PrimeDialog>
</template>

<script>
import { mapState } from 'pinia';
import useDialogStore from "@/stores/dialog";
import useCopernicusStore from "@/stores/copernicus";
import useMapStore from "@/stores/map";
import useAIAgentStore from "@/stores/aiAgent";
import AppProcessingResultsDialog from "@/components/dialogs/AppProcessingResultsDialog.vue";

import moment from 'moment';
import { transformExtent } from 'ol/proj';

export default {
    name: "AppModelProcessingSearchResultsDialog",
    components: {
        AppProcessingResultsDialog
    },
    data() {
        return {
            showResultsDialog: false,
            selectedProductId: null
        }
    },
    computed: {
        ...mapState(useDialogStore, ["modelProcessingSearchRequestDialog", "modelProcessingSearchResultsDialog"]),
        ...mapState(useCopernicusStore, ["areaItems"]),
        
        compatibleAreaItems() {
            const aiAgentStore = useAIAgentStore();
            const selectedAgent = aiAgentStore.getSelectedAgent;
            
            if (!selectedAgent) {
                return this.areaItems;
            }
            
            if (selectedAgent.inputFormat === 'sentinel2-safe') {
                return this.areaItems.filter(item => 
                    (item.id.startsWith('S2A_MSIL2A_') || item.id.startsWith('S2B_MSIL2A_'))
                );
            }
            
            if (selectedAgent.inputFormat === 'sentinel2-s1-stack') {
                return this.areaItems.filter(item => 
                    item.id.startsWith('S2A_MSIL2A_') || item.id.startsWith('S2B_MSIL2A_') ||
                    item.id.startsWith('S2A_MSIL1C_') || item.id.startsWith('S2B_MSIL1C_')
                );
            }

            // Change Detection: same filter as SR (S2 images)
            if (selectedAgent.inputFormat === 'sr-temporal-pair') {
                return this.areaItems.filter(item => 
                    item.id.startsWith('S2A_MSIL2A_') || item.id.startsWith('S2B_MSIL2A_') ||
                    item.id.startsWith('S2A_MSIL1C_') || item.id.startsWith('S2B_MSIL1C_')
                );
            }
            
            return this.areaItems;
        }
    },
    methods: {
        showAreaItemOnMap(item) {
            const bboxWebMercator = transformExtent(item.bbox, 'EPSG:4326', 'EPSG:3857')
            const polygonCoordinates = [
                [bboxWebMercator[0], bboxWebMercator[1]],
                [bboxWebMercator[2], bboxWebMercator[1]],
                [bboxWebMercator[2], bboxWebMercator[3]],
                [bboxWebMercator[0], bboxWebMercator[3]],
                [bboxWebMercator[0], bboxWebMercator[1]]
            ]

            const mapStore = useMapStore();
            mapStore.addVectorLayer(item.id, polygonCoordinates);
            item.visible = true;
        },
        hideAreaItemFromMap(item) {
            const mapStore = useMapStore();
            mapStore.removeVectorLayer(item.id);
            item.visible = false;
        },

        /**
         * Extrage bbox din zona desenată de utilizator pe hartă.
         * Folosit ca fallback când item.bbox e null (OData nu returnează bbox).
         */
        getBboxFromSearchArea() {
            const geoJson = this.modelProcessingSearchRequestDialog.requestInfo?.geoJson;
            
            if (!geoJson) return null;
            
            let coords;
            if (geoJson.type === 'Polygon') {
                coords = geoJson.coordinates[0];
            } else if (geoJson.type === 'MultiPolygon') {
                coords = geoJson.coordinates[0][0];
            } else if (geoJson.type === 'FeatureCollection') {
                const geom = geoJson.features[0]?.geometry;
                if (!geom) return null;
                coords = geom.type === 'Polygon' 
                    ? geom.coordinates[0] 
                    : geom.coordinates[0][0];
            }
            
            if (!coords || coords.length === 0) return null;
            
            const lons = coords.map(c => c[0]);
            const lats = coords.map(c => c[1]);
            return [
                Math.min(...lons),
                Math.min(...lats),
                Math.max(...lons),
                Math.max(...lats)
            ];
        },

        async process() {
            const selectedItems = this.compatibleAreaItems.filter(item => item.selected);
            const aiAgentStore = useAIAgentStore();
            
            if (selectedItems.length === 0) {
                this.$toast.add({ 
                    severity: "warn", 
                    summary: "WARNING", 
                    detail: "Please select at least one compatible image!", 
                    life: 3000
                });
                return;
            }

            if (!aiAgentStore.selectedAgent) {
                this.$toast.add({ 
                    severity: "error", 
                    summary: "ERROR", 
                    detail: "No AI model selected!", 
                    life: 3000
                });
                return;
            }

            // Change Detection necesită exact 2 scene
            if (aiAgentStore.selectedAgent === 'cd-processor') {
                if (selectedItems.length !== 2) {
                    this.$toast.add({ 
                        severity: "warn", 
                        summary: "WARNING", 
                        detail: "Change Detection requires exactly 2 images from different dates!", 
                        life: 5000
                    });
                    return;
                }
                await this.processChangeDetection(selectedItems);
                return;
            }

            // Verificare S1 pentru SR (înainte de descărcare)
            if (aiAgentStore.selectedAgent === 'sr-processor') {
                const item = selectedItems[0];
                const bbox = item.bbox || this.getBboxFromSearchArea();
                const dateMatch = item.id.match(/(\d{8})T/);
                const targetDate = dateMatch 
                    ? `${dateMatch[1].substring(0,4)}-${dateMatch[1].substring(4,6)}-${dateMatch[1].substring(6,8)}`
                    : item.datetime.substring(0, 10);

                this.$toast.add({ 
                    severity: "info", 
                    summary: "Checking SAR data", 
                    detail: "Verifying Sentinel-1 availability...", 
                    life: 5000
                });

                try {
                    const copernicusStore = useCopernicusStore();
                    const s1Check = await copernicusStore.checkS1Availability(bbox, targetDate);
                    
                    if (!s1Check.available) {
                        this.$toast.add({ 
                            severity: "error", 
                            summary: "No SAR data available", 
                            detail: `${s1Check.message}. Please select another scene.`, 
                            life: 8000
                        });
                        // Debifează scena selectată
                        selectedItems.forEach(i => i.selected = false);
                        return; // Rămâne pe dialog
                    }

                    this.$toast.add({ 
                        severity: "success", 
                        summary: "SAR data found", 
                        detail: s1Check.message, 
                        life: 3000
                    });
                } catch (err) {
                    console.warn('S1 check failed, proceeding anyway:', err);
                }
            }

            // Flow normal (SR, CHM)
            this.$toast.add({ 
                severity: "info", 
                summary: "Processing", 
                detail: `Starting download and processing of ${selectedItems.length} image(s)...`, 
                life: 5000
            });

            try {
                this.close();

                for (const item of selectedItems) {
                    await this.processImage(item, aiAgentStore.selectedAgent);
                }

                this.$toast.add({ 
                    severity: "success", 
                    summary: "SUCCESS", 
                    detail: `Successfully processed ${selectedItems.length} image(s)!`, 
                    life: 5000
                });

            } catch (error) {
                console.error('Error processing images:', error);
                this.$toast.add({ 
                    severity: "error", 
                    summary: "ERROR", 
                    detail: `Processing failed: ${error.message}`, 
                    life: 5000
                });
            }
        },

        async processImage(item, agentId) {
            try {
                console.log(`Processing image ${item.id} with agent ${agentId}`);

                // ── Pas 1: Descarcă S2 ──
                this.$toast.add({ 
                    severity: "info", 
                    summary: "Downloading", 
                    detail: `Downloading image ${item.id}...`, 
                    life: 3000
                });

                const copernicusStore = useCopernicusStore();
                const downloadResponse = await copernicusStore.downloadImages([item.stac_item]);
                
                if (!downloadResponse || !downloadResponse.task_id) {
                    throw new Error('Download failed: No task ID received');
                }

                const taskId = downloadResponse.task_id;
                console.log('Download task ID:', taskId);

                // ── Pas 2: Polling descărcare S2 ──
                let downloadCompleted = false;
                let downloadResult = null;
                let attempts = 0;
                const maxAttempts = 60;

                while (!downloadCompleted && attempts < maxAttempts) {
                    await new Promise(resolve => setTimeout(resolve, 5000));
                    
                    const statusResponse = await copernicusStore.checkDownloadStatus(taskId);
                    console.log('Download status:', statusResponse.status);

                    if (statusResponse.status === 'completed') {
                        downloadCompleted = true;
                        downloadResult = statusResponse;
                        
                        this.$toast.add({ 
                            severity: "success", 
                            summary: "Downloaded", 
                            detail: `Image ${item.id} downloaded successfully!`, 
                            life: 3000
                        });
                    } else if (statusResponse.status === 'failed') {
                        throw new Error('Download failed');
                    }
                    
                    attempts++;
                }

                if (!downloadCompleted) {
                    throw new Error('Download timeout - taking too long');
                }

                // ── Pas 3: Procesează cu AI (diferit per agent) ──
                this.$toast.add({ 
                    severity: "info", 
                    summary: "Processing", 
                    detail: `Processing image ${item.id} with AI...`, 
                    life: 3000
                });

                const aiAgentStore = useAIAgentStore();
                let result;

                if (agentId === 'sr-processor') {
                    // ── SR: trimite s2_path, bbox, target_date ──
                    const dateMatch = item.id.match(/(\d{8})T/);
                    const targetDate = dateMatch 
                        ? `${dateMatch[1].substring(0,4)}-${dateMatch[1].substring(4,6)}-${dateMatch[1].substring(6,8)}`
                        : item.datetime.substring(0, 10);

                    const s2Path = downloadResult.files 
                        ? downloadResult.files[0] 
                        : `${item.id}/${item.id}.zip`;

                    // Bbox: din item sau fallback din zona desenată pe hartă
                    const bbox = item.bbox || this.getBboxFromSearchArea();
                    
                    if (!bbox) {
                        throw new Error('Could not determine bounding box for SR processing');
                    }

                    this.$toast.add({ 
                        severity: "info", 
                        summary: "Super Resolution", 
                        detail: `Downloading SAR data and applying SR (mode: ${aiAgentStore.selectedSRMode})...`, 
                        life: 10000
                    });

                    result = await aiAgentStore.processWithSelectedAgent({
                        s2_path: s2Path,
                        bbox: bbox,
                        target_date: targetDate,
                        mode: aiAgentStore.selectedSRMode
                    });

                } else {
                    // ── CHM și alți agenți: format existent ──
                    result = await aiAgentStore.processWithSelectedAgent({
                        image_filenames: [`${item.id}/${item.id}.zip`]
                    });
                }

                console.log('AI Processing result:', result);
                
                await aiAgentStore.loadProcessingResults(item.id);
                
                this.$toast.add({ 
                    severity: "success", 
                    summary: "Processing Complete", 
                    detail: `Image ${item.id} processed successfully!`, 
                    life: 5000
                });

                return result;

            } catch (error) {
                console.error(`Error processing image ${item.id}:`, error);
                throw error;
            }
        },

        /**
         * Change Detection: descarcă 2 scene, aplică SR pe ambele, apoi CVA.
         */
        async processChangeDetection(selectedItems) {
            try {
                this.close();

                // Sortează cronologic — T1 mai vechi, T2 mai recent
                const sorted = [...selectedItems].sort((a, b) => 
                    new Date(a.datetime) - new Date(b.datetime)
                );
                
                const itemT1 = sorted[0];
                const itemT2 = sorted[1];

                // Verificare S1 pentru ambele scene CD-SR
                if (aiAgentStore.selectedAgent === 'cd-processor') {
                    const copernicusStore = useCopernicusStore();
                    
                    for (const item of [itemT1, itemT2]) {
                        const dateMatch = item.id.match(/(\d{8})T/);
                        const targetDate = dateMatch 
                            ? `${dateMatch[1].substring(0,4)}-${dateMatch[1].substring(4,6)}-${dateMatch[1].substring(6,8)}`
                            : item.datetime.substring(0, 10);
                        
                        const s1Check = await copernicusStore.checkS1Availability(bbox, targetDate);
                        
                        if (!s1Check.available) {
                            this.$toast.add({ 
                                severity: "error", 
                                summary: "No SAR data", 
                                detail: `No S1 data for scene ${item.id.substring(0, 30)}... (${targetDate}). Select different dates.`, 
                                life: 8000
                            });
                            return; // Nu închide dialogul
                        }
                    }
                }
                
                this.$toast.add({ 
                    severity: "info", 
                    summary: "Change Detection", 
                    detail: `Step 1/3: Downloading 2 scenes...`, 
                    life: 10000
                });

                const bbox = this.getBboxFromSearchArea();
                const aiAgentStore = useAIAgentStore();
                const copernicusStore = useCopernicusStore();

                // Extrage data din ID-ul scenei
                const extractDate = (item) => {
                    const match = item.id.match(/(\d{8})T/);
                    return match 
                        ? `${match[1].substring(0,4)}-${match[1].substring(4,6)}-${match[1].substring(6,8)}`
                        : item.datetime.substring(0, 10);
                };

                // Descarcă ambele scene S2
                const dl1 = await copernicusStore.downloadImages([itemT1.stac_item]);
                const dl2 = await copernicusStore.downloadImages([itemT2.stac_item]);
                
                // Polling — așteaptă descărcarea ambelor
                const waitDownload = async (taskId, label) => {
                    for (let i = 0; i < 60; i++) {
                        await new Promise(r => setTimeout(r, 5000));
                        const status = await copernicusStore.checkDownloadStatus(taskId);
                        console.log(`Download ${label} status:`, status.status);
                        if (status.status === 'completed') return status;
                        if (status.status === 'failed') throw new Error(`Download ${label} failed`);
                    }
                    throw new Error(`Download ${label} timeout`);
                };

                const result1 = await waitDownload(dl1.task_id, 'T1');
                const result2 = await waitDownload(dl2.task_id, 'T2');

                const s2PathT1 = result1.files ? result1.files[0] : `${itemT1.id}/${itemT1.id}.zip`;
                const s2PathT2 = result2.files ? result2.files[0] : `${itemT2.id}/${itemT2.id}.zip`;

                this.$toast.add({ 
                    severity: "info", 
                    summary: "Change Detection", 
                    detail: `Step 2/3: Applying SR on both scenes + detecting changes...`, 
                    life: 30000
                });

                // Apelează CD cu ambele scene — backend-ul aplică SR + CVA
                const result = await aiAgentStore.processWithSelectedAgent({
                    scene_t1: { s2_path: s2PathT1, bbox: bbox, target_date: extractDate(itemT1) },
                    scene_t2: { s2_path: s2PathT2, bbox: bbox, target_date: extractDate(itemT2) },
                    mode: 'fidelity',
                    threshold_method: 'otsu'
                });

                console.log('Change Detection result:', result);
                
                const stats = result.data.statistics;
                this.$toast.add({ 
                    severity: "success", 
                    summary: "Change Detection Complete", 
                    detail: `Changes: ${stats.changed_area_ha} ha (${stats.change_percentage}%). ` +
                            `Vegetation loss: ${stats.vegetation_loss_ha} ha, gain: ${stats.vegetation_gain_ha} ha`, 
                    life: 15000
                });

            } catch (error) {
                console.error('Change detection error:', error);
                this.$toast.add({ 
                    severity: "error", 
                    summary: "ERROR", 
                    detail: `Change detection failed: ${error.message}`, 
                    life: 5000
                });
            }
        },
        
        showAllResults() {
            this.selectedProductId = null;
            this.showResultsDialog = true;
        },
        
        showResultsForProduct(productId) {
            this.selectedProductId = productId;
            this.showResultsDialog = true;
        },
        
        hasResultsForProduct(productId) {
            const aiAgentStore = useAIAgentStore();
            return aiAgentStore.processingResults[productId] !== undefined;
        },
        
        close() {
            const dialogStore = useDialogStore();
            dialogStore.hideModelProcessingSearchResultsDialog();
        },
        moment(dateString) {
            return moment(dateString);
        },
        extractTileInfo(id) {
            // S2B_MSIL2A_20260324T094029_N0512_R036_T34TDR_20260324T133022.SAFE
            const parts = id.split('_');
            if (parts.length >= 6) {
                const level = parts[1]; // MSIL2A
                const tile = parts[5];  // T34TDR
                return `${tile} (${level})`;
            }
            return id.substring(0, 30);
        }
    }
}
</script>

<style lang="scss" scoped>

</style>