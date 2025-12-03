<template>
    <PrimeDialog v-model:visible="modelProcessingSearchResultsDialog.visible" header="Search results" :closable="false">
        <!-- List of the search results -->
        <div class="mb-4">
            <!-- Warning message if no compatible images -->
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
                    <div class="w-[50px]"></div>
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
                        <div class="w-[50px] flex items-center">
                            <PrimeButton 
                                v-if="item.visible"
                                @click="hideAreaItemFromMap(item)"
                                icon="pi pi-eye" 
                                variant="text" rounded 
                                severity="success"
                                v-tooltip.bottom="'Hide area item from map'"
                            />
                            <PrimeButton 
                                v-else
                                @click="showAreaItemOnMap(item)"
                                icon="pi pi-eye-slash"
                                variant="text" rounded 
                                severity="danger"
                                v-tooltip.bottom="'Show area item on map'"
                            />
                        </div>
                    </div>
                </div>
            </div>
            <div v-else>
                There is not data.
            </div>
        </div>
        <!-- Buttons -->
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
    </PrimeDialog>
</template>

<script>
import { mapState } from 'pinia';
import useDialogStore from "@/stores/dialog";
import useCopernicusStore from "@/stores/copernicus";
import useMapStore from "@/stores/map";
import useAIAgentStore from "@/stores/aiAgent";

import moment from 'moment';
import { transformExtent } from 'ol/proj';

export default {
    name: "AppModelProcessingSearchResultsDialog",
    components: {},
    data() {
        return {}
    },
    computed: {
        ...mapState(useDialogStore, ["modelProcessingSearchResultsDialog"]),
        ...mapState(useCopernicusStore, ["areaItems"]),
        
        // Filtrează doar imaginile compatibile cu modelul AI selectat
        compatibleAreaItems() {
            const aiAgentStore = useAIAgentStore();
            const selectedAgent = aiAgentStore.getSelectedAgent;
            
            if (!selectedAgent) {
                return this.areaItems;
            }
            
            // Filtrează în funcție de inputFormat al agentului
            if (selectedAgent.inputFormat === 'sentinel2-safe') {
                // Filtrează doar imagini Sentinel-2 Level-2A (conțin SCL band)
                // Format: S2A_MSIL2A_... sau S2B_MSIL2A_...
                return this.areaItems.filter(item => 
                    (item.id.startsWith('S2A_MSIL2A_') || item.id.startsWith('S2B_MSIL2A_'))
                );
            }
            
            return this.areaItems;
        }
    },
    methods: {
        showAreaItemOnMap(item) {
            // item.bbox is a bounding box: [minX, minY, maxX, maxY]
            // bbox coordinates are in EPSG:4326 (WGS84 longitude/latitude)
            // OpenLayers' default 
            const bboxWebMercator = transformExtent(item.bbox, 'EPSG:4326', 'EPSG:3857')
            const polygonCoordinates = [
                [bboxWebMercator[0], bboxWebMercator[1]], // bottom-left (minX, minY)
                [bboxWebMercator[2], bboxWebMercator[1]], // bottom-right (maxX, minY)
                [bboxWebMercator[2], bboxWebMercator[3]], // top-right (maxX, maxY)
                [bboxWebMercator[0], bboxWebMercator[3]], // top-left (minX, maxY)
                [bboxWebMercator[0], bboxWebMercator[1]] // close the polygon
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

            // Verifică dacă un model AI este selectat
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
                // Închide dialogul
                this.close();

                // Pentru fiecare imagine selectată, procesează
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

                // Pas 1: Descarcă imaginea prin serviciul Copernicus
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

                // Pas 2: Așteaptă finalizarea descărcării (polling cu timeout)
                let downloadCompleted = false;
                let attempts = 0;
                const maxAttempts = 60; // 5 minute (5 sec/attempt)

                while (!downloadCompleted && attempts < maxAttempts) {
                    await new Promise(resolve => setTimeout(resolve, 5000)); // Așteaptă 5 secunde
                    
                    const statusResponse = await copernicusStore.checkDownloadStatus(taskId);
                    console.log('Download status:', statusResponse.status);

                    if (statusResponse.status === 'completed') {
                        downloadCompleted = true;
                        
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

                // Pas 3: Procesează cu AI
                this.$toast.add({ 
                    severity: "info", 
                    summary: "Processing", 
                    detail: `Processing image ${item.id} with AI...`, 
                    life: 3000
                });

                const aiAgentStore = useAIAgentStore();
                
                // Trimite numele directorului și ZIP-ul va fi găsit automat
                // Format: product_id/product_id.zip
                const result = await aiAgentStore.processWithSelectedAgent({
                    image_filenames: [`${item.id}/${item.id}.zip`]
                });

                console.log('AI Processing result:', result);

                return result;

            } catch (error) {
                console.error(`Error processing image ${item.id}:`, error);
                throw error;
            }
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