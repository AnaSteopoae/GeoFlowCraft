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
                        <div class="w-[200px] flex items-center overflow-hidden">{{ item.id }}</div>
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
            
            if (selectedItems.length === 0) {
                this.$toast.add({ 
                    severity: "warn", 
                    summary: "WARNING", 
                    detail: "Please select at least one compatible image!", 
                    life: 3000
                });
                return;
            }

            const aiAgentStore = useAIAgentStore();
            if (!aiAgentStore.selectedAgent) {
                this.$toast.add({ 
                    severity: "error", 
                    summary: "ERROR", 
                    detail: "No AI model selected!", 
                    life: 3000
                });
                return;
            }

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
        }
    }
}
</script>

<style lang="scss" scoped>

</style>