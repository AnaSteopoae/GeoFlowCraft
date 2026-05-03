<template>
    <PrimeDialog v-model:visible="modelProcessingSearchResultsDialog.visible" 
    :header="isCDStepMode ? cdStepHeader : 'Search results'" :closable="false">
        <div class="mb-4">
            <div v-if="areaItems?.length > 0 && compatibleAreaItems.length === 0" class="mb-3 p-3 bg-yellow-500/20 border border-yellow-500 rounded-lg">
                <div class="flex items-center gap-2">
                    <i class="pi pi-exclamation-triangle text-yellow-400"></i>
                    <div class="text-sm">
                        <strong>No compatible images found!</strong><br/>
                        The selected AI model requires Sentinel-2 images, but only other satellite data was found.
                        Try searching for a different area or time period.
                    </div>
                    <!-- CD Step indicator -->
            <div v-if="isCDStepMode" class="mb-3 p-3 rounded-lg" 
                 :style="{ 
                     background: cdFlowStep === 'select_t1' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                     border: cdFlowStep === 'select_t1' ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid rgba(34, 197, 94, 0.3)'
                 }">
                <div class="flex items-center gap-2 text-sm">
                    <span class="inline-block w-6 h-6 rounded-full text-center text-sm leading-6 font-bold" 
                          :style="{ 
                              background: cdFlowStep === 'select_t1' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)',
                              color: cdFlowStep === 'select_t1' ? '#fca5a5' : '#86efac'
                          }">
                        {{ cdFlowStep === 'select_t1' ? '1' : '2' }}
                    </span>
                    <span style="color: #e2e8f0;">
                        {{ cdFlowStep === 'select_t1' 
                            ? 'Select ONE scene for the BEFORE period (T1)' 
                            : 'Select ONE scene for the AFTER period (T2)' }}
                    </span>
                </div>
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
                There is no data.
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

        <!-- Name input dialog -->
        <PrimeDialog 
            v-model:visible="showNameDialog" 
            modal 
            header="Name your result"
            :style="{ width: '25rem' }"
        >
            <div class="flex flex-col gap-3 my-2">
                <div class="text-sm text-gray-400">
                    Choose a name for this processing result:
                </div>
                <InputText 
                    v-model="resultName" 
                    placeholder="e.g. Brașov urban area Feb 2026"
                    class="w-full"
                    @keyup.enter="confirmProcessing"
                />
                <div class="text-xs text-gray-500">
                    This name will appear in the map layers and View Results.
                </div>
            </div>
            <template #footer>
                <div class="flex justify-between w-full">
                    <PrimeButton label="Cancel" icon="pi pi-times" severity="secondary" @click="showNameDialog = false" />
                    <PrimeButton 
                        label="Start processing" 
                        icon="pi pi-play" 
                        severity="success"
                        :disabled="!resultName || resultName.trim().length === 0"
                        @click="confirmProcessing" 
                    />
                </div>
            </template>
        </PrimeDialog>
    </PrimeDialog>
</template>

<script>
import { mapState } from 'pinia';
import useDialogStore from "@/stores/dialog";
import useCopernicusStore from "@/stores/copernicus";
import useMapStore from "@/stores/map";
import useAIAgentStore from "@/stores/aiAgent";
import AppProcessingResultsDialog from "@/components/dialogs/AppProcessingResultsDialog.vue";
import InputText from 'primevue/inputtext';

import moment from 'moment';
import { transformExtent } from 'ol/proj';

export default {
    name: "AppModelProcessingSearchResultsDialog",
    components: {
        AppProcessingResultsDialog,
        InputText
    },
    data() {
        return {
            showResultsDialog: false,
            selectedProductId: null,
            showNameDialog: false,
            resultName: '',
            pendingProcessItems: null,
            pendingProcessType: null
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
                    (item.id.startsWith('S2A_MSIL2A_') || item.id.startsWith('S2B_MSIL2A_') || item.id.startsWith('S2C_MSIL2A_'))
                );
            }
            
            if (selectedAgent.inputFormat === 'sentinel2-s1-stack') {
                return this.areaItems.filter(item => 
                    item.id.startsWith('S2A_MSIL2A_') || item.id.startsWith('S2B_MSIL2A_') || item.id.startsWith('S2C_MSIL2A_') ||
                    item.id.startsWith('S2A_MSIL1C_') || item.id.startsWith('S2B_MSIL1C_') || item.id.startsWith('S2C_MSIL1C_')
                );
            }

            if (selectedAgent.inputFormat === 'sr-temporal-pair') {
                return this.areaItems.filter(item => 
                    item.id.startsWith('S2A_MSIL2A_') || item.id.startsWith('S2B_MSIL2A_') || item.id.startsWith('S2C_MSIL2A_') ||
                    item.id.startsWith('S2A_MSIL1C_') || item.id.startsWith('S2B_MSIL1C_') || item.id.startsWith('S2C_MSIL1C_')
                );
            }
            
            return this.areaItems;
        },
        cdFlowStep() {
            return useDialogStore().cdFlowStep;
        },

        isCDStepMode() {
            return this.cdFlowStep === 'select_t1' || this.cdFlowStep === 'select_t2';
        },

        cdStepHeader() {
            if (this.cdFlowStep === 'select_t1') return 'Select scene for T1 (older date)';
            if (this.cdFlowStep === 'select_t2') return 'Select scene for T2 (newer date)';
            return 'Search results';
        },
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

        /**
         * Process button handler.
         * Validates selection, checks S1 availability, then shows name dialog.
         */
        async process() {
            const selectedItems = this.compatibleAreaItems.filter(item => item.selected);
            const aiAgentStore = useAIAgentStore();
            const dialogStore = useDialogStore();

            // ── CD Step Mode: selectare T1 sau T2 ──
            if (this.isCDStepMode) {
                if (selectedItems.length !== 1) {
                    this.$toast.add({ 
                        severity: "warn", summary: "WARNING", 
                        detail: "Please select exactly 1 scene!", life: 3000
                    });
                    return;
                }

                if (this.cdFlowStep === 'select_t1') {
                    // Salvează T1, caută T2
                    dialogStore.cdSelectedSceneT1 = selectedItems[0];
                    this.close();
                    
                    this.$toast.add({ 
                        severity: "success", summary: "T1 Selected", 
                        detail: `T1: ${selectedItems[0].id.substring(0, 40)}`, life: 3000
                    });

                    // Căutare pentru T2
                    this.$toast.add({ 
                        severity: "info", summary: "Searching T2", 
                        detail: "Searching satellite images for the second period...", life: 3000
                    });

                    const copernicusStore = useCopernicusStore();
                    const searchResponse = await copernicusStore.search(
                        this.modelProcessingSearchRequestDialog.requestInfo.geoJson,
                        dialogStore.cdDatesT2[0], dialogStore.cdDatesT2[1]
                    );

                    if (searchResponse.status == "success" && searchResponse.items?.length > 0) {
                        dialogStore.cdFlowStep = 'select_t2';
                        dialogStore.showModelProcessingSearchResultsDialog();
                    } else {
                        this.$toast.add({ 
                            severity: "warn", summary: "WARNING", 
                            detail: "No data found for T2 period!", life: 3000
                        });
                        dialogStore.resetCDFlow();
                    }
                    return;
                }

                if (this.cdFlowStep === 'select_t2') {
                    // Salvează T2, continuă cu procesare
                    dialogStore.cdSelectedSceneT2 = selectedItems[0];
                    
                    this.$toast.add({ 
                        severity: "success", summary: "T2 Selected", 
                        detail: `T2: ${selectedItems[0].id.substring(0, 40)}`, life: 3000
                    });

                    // Generează nume implicit
                    const t1 = dialogStore.cdSelectedSceneT1;
                    const t2 = dialogStore.cdSelectedSceneT2;
                    const t1Tile = t1.id.match(/T\d{2}[A-Z]{3}/)?.[0] || '';
                    const t1Date = t1.id.match(/(\d{8})T/)?.[1] || '';
                    const t2Date = t2.id.match(/(\d{8})T/)?.[1] || '';
                    const taskLabel = aiAgentStore.selectedAgent === 'cd-processor' ? 'CD-SR' : 'CD-CHM';
                    
                    this.resultName = `${taskLabel} ${t1Tile} ${t1Date}-${t2Date}`.trim();
                    this.pendingProcessItems = [t1, t2];
                    this.pendingProcessType = 'cd';
                    this.showNameDialog = true;
                    return;
                }
            }
            
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

             // Mix mode: selectare 1 scenă nouă, apoi alege din rezultate existente
            const dialogStore2 = useDialogStore();
            if (dialogStore2.selectedTaskInfo?.cdSource === 'mix') {
                if (selectedItems.length !== 1) {
                    this.$toast.add({ 
                        severity: "warn", summary: "WARNING", 
                        detail: "Please select exactly 1 scene for mix mode!", life: 3000
                    });
                    return;
                }

                dialogStore2.cdSelectedSceneNew = selectedItems[0];
                this.close();

                this.$toast.add({ 
                    severity: "info", summary: "Mix mode", 
                    detail: "Now select an existing result to compare with.", life: 5000
                });

                dialogStore2.existingResultsDialogVisible = true;
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
            }

            // Verificare S1 pentru SR și CD-SR
            if (aiAgentStore.selectedAgent === 'sr-processor' || aiAgentStore.selectedAgent === 'cd-processor') {
                const bbox = this.getBboxFromSearchArea();
                
                for (const item of selectedItems) {
                    const dateMatch = item.id.match(/(\d{8})T/);
                    const targetDate = dateMatch 
                        ? `${dateMatch[1].substring(0,4)}-${dateMatch[1].substring(4,6)}-${dateMatch[1].substring(6,8)}`
                        : item.datetime.substring(0, 10);

                    this.$toast.add({ 
                        severity: "info", 
                        summary: "Checking SAR data", 
                        detail: `Verifying S1 availability for ${targetDate}...`, 
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
                            selectedItems.forEach(i => i.selected = false);
                            return;
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
            }

            // Generează nume implicit
            const item = selectedItems[0];
            const dateMatch = item.id.match(/(\d{8})T/);
            const dateStr = dateMatch 
                ? `${dateMatch[1].substring(0,4)}-${dateMatch[1].substring(4,6)}-${dateMatch[1].substring(6,8)}`
                : '';
            const tileMatch = item.id.match(/T\d{2}[A-Z]{3}/);
            const tileId = tileMatch ? tileMatch[0] : '';
            
            const taskLabels = {
                'sr-processor': 'SR',
                'ch-processor': 'CHM',
                'cd-processor': 'CD-SR',
                'cd-chm-processor': 'CD-CHM'
            };
            const taskLabel = taskLabels[aiAgentStore.selectedAgent] || 'Result';
            
            this.resultName = `${taskLabel} ${tileId} ${dateStr}`.trim();
            this.pendingProcessItems = selectedItems;
            this.pendingProcessType = aiAgentStore.selectedAgent === 'cd-processor' ? 'cd' : 'single';
            this.showNameDialog = true;
        },

        /**
         * Called after user confirms the result name.
         * Starts the actual processing pipeline.
         */
        async confirmProcessing() {
            this.showNameDialog = false;
            
            const aiAgentStore = useAIAgentStore();
            const dialogStore = useDialogStore();
            aiAgentStore.resultName = this.resultName.trim();
            
            if (this.pendingProcessType === 'cd') {
                await this.processChangeDetection(this.pendingProcessItems);
                dialogStore.resetCDFlow();  // Resetează starea CD
            } else {
                this.$toast.add({ 
                    severity: "info", 
                    summary: "Processing", 
                    detail: `Starting "${this.resultName}"...`, 
                    life: 5000
                });

                try {
                    this.close();

                    for (const item of this.pendingProcessItems) {
                        await this.processImage(item, aiAgentStore.selectedAgent);
                    }

                    this.$toast.add({ 
                        severity: "success", 
                        summary: "SUCCESS", 
                        detail: `"${this.resultName}" processed successfully!`, 
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
            }
        },

        async processImage(item, agentId) {
            try {
                console.log(`Processing image ${item.id} with agent ${agentId}`);

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

                this.$toast.add({ 
                    severity: "info", 
                    summary: "Processing", 
                    detail: `Processing image ${item.id} with AI...`, 
                    life: 3000
                });

                const aiAgentStore = useAIAgentStore();
                let result;

                if (agentId === 'sr-processor') {
                    const dateMatch = item.id.match(/(\d{8})T/);
                    const targetDate = dateMatch 
                        ? `${dateMatch[1].substring(0,4)}-${dateMatch[1].substring(4,6)}-${dateMatch[1].substring(6,8)}`
                        : item.datetime.substring(0, 10);

                    const s2Path = downloadResult.files 
                        ? downloadResult.files[0] 
                        : `${item.id}/${item.id}.zip`;

                    const bbox = this.getBboxFromSearchArea();
                    
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
                        mode: aiAgentStore.selectedSRMode,
                        resultName: aiAgentStore.resultName || this.resultName
                    });

                } else {
                    result = await aiAgentStore.processWithSelectedAgent({
                        image_filenames: [`${item.id}/${item.id}.zip`],
                        resultName: aiAgentStore.resultName || this.resultName
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

        async processChangeDetection(selectedItems) {
            try {
                this.close();

                const sorted = [...selectedItems].sort((a, b) => 
                    new Date(a.datetime) - new Date(b.datetime)
                );
                
                const itemT1 = sorted[0];
                const itemT2 = sorted[1];
                
                this.$toast.add({ 
                    severity: "info", 
                    summary: "Change Detection", 
                    detail: `Step 1/3: Downloading 2 scenes...`, 
                    life: 10000
                });

                const bbox = this.getBboxFromSearchArea();
                const aiAgentStore = useAIAgentStore();
                const copernicusStore = useCopernicusStore();

                const extractDate = (item) => {
                    const match = item.id.match(/(\d{8})T/);
                    return match 
                        ? `${match[1].substring(0,4)}-${match[1].substring(4,6)}-${match[1].substring(6,8)}`
                        : item.datetime.substring(0, 10);
                };

                const dl1 = await copernicusStore.downloadImages([itemT1.stac_item]);
                const dl2 = await copernicusStore.downloadImages([itemT2.stac_item]);
                
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

                const result = await aiAgentStore.processWithSelectedAgent({
                    scene_t1: { s2_path: s2PathT1, bbox: bbox, target_date: extractDate(itemT1) },
                    scene_t2: { s2_path: s2PathT2, bbox: bbox, target_date: extractDate(itemT2) },
                    mode: 'fidelity',
                    threshold_method: 'otsu',
                    resultName: aiAgentStore.resultName || this.resultName
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
            const parts = id.split('_');
            if (parts.length >= 6) {
                const level = parts[1];
                const tile = parts[5];
                return `${tile} (${level})`;
            }
            return id.substring(0, 30);
        }
    }
}
</script>

<style lang="scss" scoped>
</style>