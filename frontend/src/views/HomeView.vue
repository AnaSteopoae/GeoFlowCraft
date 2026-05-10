<template>

  <div id="map" class="relative h-full">
    <div class="absolute z-[100] right-1 top-1 p-1 bg-gray-800 w-[250px] border-2 border-gray-300 rounded-md flex flex-col gap-1">
      <!-- List of datasets -->
      <AppDataSetList class="border-b-2 border-gray-300" />
      <!-- List of visible datalayers -->
      <AppDataLayerList />
    </div>
    <!-- Dialogs -->
    <AppConfirmDialog @confirm-yes="onConfirmYes" @confirm-no="onConfirmNo" />
    <AppDataSetCreateDialog @created-data-set="onDataSetCreated" />
    <AppDataSetDetailsDialog />
    <AppDataLayersDialog />
    <AppDataLayerCreateDialog @created-data-layer="onDataLayerCreated"/>
    <AppModelProcessingSearchRequestDialog />
    <AppModelProcessingSearchResultsDialog />
    <AppExistingResultsDialog 
    v-model="showExistingResults"
    :maxSelections="existingResultsMax"
    :resultType="existingResultsType"
    @results-selected="onExistingResultsSelected"
    />
    <AppProcessingProgressDialog 
        v-model="progressVisible"
        :currentStep="progressData.step"
        :steps="progressData.steps"
        :currentStepLabel="progressData.label"
        :currentStepDetail="progressData.detail"
    />
     <!-- CD Name dialog for existing results -->
    <PrimeDialog 
        v-model:visible="showCDNameDialog" 
        modal 
        header="Name your result"
        :style="{ width: '25rem' }"
    >
        <div class="flex flex-col gap-3 my-2">
            <div class="text-sm text-gray-400">
                Choose a name for this Change Detection result:
            </div>
            <PrimeInputText 
                v-model="cdResultName" 
                placeholder="e.g. CD Brașov Feb-Apr 2026"
                class="w-full"
                @keyup.enter="startCDFromExisting"
            />
        </div>
        <template #footer>
            <div class="flex justify-between w-full">
                <PrimeButton label="Cancel" icon="pi pi-times" severity="secondary" @click="cancelCDNaming" />
                <PrimeButton 
                    label="Start processing" 
                    icon="pi pi-play" 
                    severity="success"
                    :disabled="!cdResultName || cdResultName.trim().length === 0"
                    @click="startCDFromExisting" 
                />
            </div>
        </template>
    </PrimeDialog>
    <PrimeToast />
  </div>

</template>

<script>

import useMapStore from "@/stores/map";
import useDialogStore from "@/stores/dialog";
import useDataSetStore from "@/stores/dataSet";
import useDataLayerStore from "@/stores/dataLayer";
import useAIAgentStore from "@/stores/aiAgent";
import useCopernicusStore from "@/stores/copernicus";

import AppConfirmDialog from "@/components/dialogs/AppConfirmDialog.vue";
import AppDataSetList from "../components/AppDataSetList.vue";
import AppDataSetCreateDialog from "../components/dialogs/AppDataSetCreateDialog.vue";
import AppDataSetDetailsDialog from "@/components/dialogs/AppDataSetDetailsDialog.vue";
import AppDataLayersDialog from "@/components/dialogs/AppDataLayersDialog.vue";
import AppDataLayerList from "@/components/AppDataLayerList.vue";
import AppDataLayerCreateDialog from "@/components/dialogs/AppDataLayerCreateDialog.vue";
import AppModelProcessingSearchRequestDialog from "@/components/dialogs/AppModelProcessingSearchRequestDialog.vue";
import AppModelProcessingSearchResultsDialog from "@/components/dialogs/AppModelProcessingSearchResultsDialog.vue";
import AppExistingResultsDialog from '@/components/dialogs/AppExistingResultsDialog.vue';
import AppProcessingProgressDialog from "@/components/dialogs/AppProcessingProgressDialog.vue";

export default {
  name: "HomeView",
  components: { 
    AppConfirmDialog,
    AppDataSetList,
    AppDataSetCreateDialog, AppDataSetDetailsDialog,
    AppDataLayerList,
    AppDataLayersDialog, AppDataLayerCreateDialog,
    AppModelProcessingSearchRequestDialog, AppModelProcessingSearchResultsDialog,
    AppExistingResultsDialog, AppProcessingProgressDialog

  },
  data() {
    return {
      pendingModelProcessingFeature: null,
      // showExistingResults: false,
      // existingResultsType: 'sr',
      // existingResultsMax: 2
      showCDNameDialog: false,
      cdResultName: '',
      pendingCDSelection: null
    }
  },
  mounted() {
    const mapStore = useMapStore();
    mapStore.initialize();
  },
  computed: {
    showExistingResults: {
        get() { return useDialogStore().existingResultsDialogVisible; },
        set(val) { useDialogStore().existingResultsDialogVisible = val; }
    },
    existingResultsType() {
        const taskInfo = useDialogStore().selectedTaskInfo;
        if (!taskInfo) return 'sr';
        return (taskInfo.task === 'cd-chm-processor') ? 'chm' : 'sr';
    },
    existingResultsMax() {
        const taskInfo = useDialogStore().selectedTaskInfo;
        if (!taskInfo) return 2;
        return taskInfo.cdSource === 'mix' ? 1 : 2;
    },
    progressVisible: {
        get() { return useDialogStore().processingProgress.visible; },
        set(val) { if (!val) useDialogStore().hideProcessingProgress(); }
    },
    progressData() {
        return useDialogStore().processingProgress;
    }
  },
  methods: {
    onOpenExistingResults({ type, max }) {
    this.existingResultsType = type;
    this.existingResultsMax = max;
    this.showExistingResults = true;
  },
    cancelCDNaming() {
        this.showCDNameDialog = false;
        const mapStore = useMapStore();
        mapStore.removeDrawLayer();
        const dialogStore = useDialogStore();
        dialogStore.resetAllProcessingState();
    },
    onDataSetCreated() {
      this.$toast.add({ severity: "success", summary: "Success", detail: "The dataset has been successfully created!", life: 3000 });
    },
    onDataLayerCreated() {
      this.$toast.add({ severity: "success", summary: "Success", detail: "The datalayer has been successfully created!", life: 3000 });
    },
    async onConfirmYes() {
      const dialogStore = useDialogStore();
      try {        
        dialogStore.confirmDialogIsLoading = true;
        
        const event = dialogStore.confirmDialogInfo.event;
        switch (event) {
          case "DELETE_SELECTED_DATASET": // TODO: Create an enum of events
            const dataSetStore = useDataSetStore();
            const deleteResult = await dataSetStore.deleteDataSet();

            if(deleteResult?.success) {
              this.$toast.add({ severity: "success", summary: "Success", detail: "The dataset has been successfully deleted!", life: 3000 });
              dialogStore.hideDataSetDetailsDialog();
            } else {
              this.$toast.add({ severity: "error", summary: "Error", detail: deleteResult.message ?? "Something went wrong!" , life: 3000 });
            }
            break;
          case "DELETE_SELECTED_DATALAYER": // TODO: Create an enum of events
            const dataLayerStore = useDataLayerStore();  
            const mapStore = useMapStore();
            await mapStore.hideLayer(dataLayerStore.selectedDataLayer.id);
            const response = await dataLayerStore.deleteDataLayer(dataLayerStore.selectedDataLayer.id);
            if(response?.success) {
                this.$toast.add({ severity: "success", summary: "Success", detail: "The datalayer has been successfully deleted!", life: 3000 });
            } else {
                this.$toast.add({ severity: "error", summary: "Failed deleting datalayer!", detail: `Something went wrong on the backend side: ${response.error}`, life: 3000 });
            }
            break;
          case "MODEL_PROCESSING_ACTIVATE_DRAW_MODE": // TODO: Create an enum of events
            this.activateDrawModeForModelProcessing();
            break;
          case "CONFIRM_MODEL_PROCESSING_AREA":
            this.proceedWithModelProcessing();
            break;
          default:
            console.error("Unknown event!")
            break;
        }
      } catch (error) {
        console.log(error);
        this.$toast.add({ severity: "error", summary: "Error", detail: error.message ?? "Something went wrong!" , life: 3000 });
      } finally {
        dialogStore.confirmDialogIsLoading = false;
      }
      dialogStore.hideConfirmDialog();
    },
    onConfirmNo() {
     const dialogStore = useDialogStore();
      const event = dialogStore.confirmDialogInfo.event;
      
      if (event === "CONFIRM_MODEL_PROCESSING_AREA") {
        // Șterge zona desenată și reactivează draw mode
        const mapStore = useMapStore();
        mapStore.removeDrawLayer();
        this.pendingModelProcessingFeature = null;
        dialogStore.hideConfirmDialog();
        // Reactivează draw mode
        mapStore.enableDrawInteraction("Polygon", this.confirmDrawnAreaForModelProcessing, false);
        return;
      }
      
      dialogStore.hideConfirmDialog();
    },
    activateDrawModeForModelProcessing() {
      const mapStore = useMapStore();
      mapStore.enableDrawInteraction("Polygon", this.confirmDrawnAreaForModelProcessing, false);
    },
    confirmDrawnAreaForModelProcessing(drawnFeature) {
      try {
        const mapStore = useMapStore();
        mapStore.disableDrawInteration();
        mapStore.addDrawLayer(drawnFeature);
        
        // Verificare dimensiune zonă
        const geoJson = mapStore.getGeoJsonFromFeature(drawnFeature, "EPSG:4326");
        let coords;
        if (geoJson.type === 'Polygon') coords = geoJson.coordinates[0];
        else if (geoJson.type === 'FeatureCollection') coords = geoJson.features[0]?.geometry?.coordinates[0];
        
        if (coords) {
            const lons = coords.map(c => c[0]);
            const lats = coords.map(c => c[1]);
            const widthKm = (Math.max(...lons) - Math.min(...lons)) * 111 * Math.cos(lats[0] * Math.PI / 180);
            const heightKm = (Math.max(...lats) - Math.min(...lats)) * 111;
            const areaKm2 = widthKm * heightKm;
            
            if (areaKm2 < 1) {
                this.$toast.add({ 
                    severity: "warn", summary: "Area too small", 
                    detail: `Selected area (~${areaKm2.toFixed(2)} km²) is very small. Results may not be meaningful. Minimum recommended: 1 km².`,
                    life: 5000
                });
            }
            
            if (areaKm2 > 400) {
                this.$toast.add({ 
                    severity: "error", summary: "Area too large", 
                    detail: `Selected area (~${areaKm2.toFixed(0)} km²) is too large. Maximum: ~400 km² (20×20 km). Please select a smaller area.`,
                    life: 8000
                });
                mapStore.removeDrawLayer();
                this.pendingModelProcessingFeature = null;
                // Reactivează draw mode
                mapStore.enableDrawInteraction("Polygon", this.confirmDrawnAreaForModelProcessing, false);
                return;
            }
        }

        this.pendingModelProcessingFeature = drawnFeature;
        
        const dialogStore = useDialogStore();
        dialogStore.showConfirmDialog({
          title: "Confirm Area Selection",
          message: "Do you want to proceed with this area for model processing?",
          event: "CONFIRM_MODEL_PROCESSING_AREA"
        });
      } catch (error) {
        this.$toast.add({ severity: "error", summary: "ERROR", detail: error , life: 3000 });
      }
    },
    proceedWithModelProcessing() {
      const mapStore = useMapStore();
      const dialogStore = useDialogStore();
      
      if (!this.pendingModelProcessingFeature) {
        this.$toast.add({ severity: "error", summary: "Error", detail: "No area selected!", life: 3000 });
        return;
      }
      
      const geoJson = mapStore.getGeoJsonFromFeature(this.pendingModelProcessingFeature, "EPSG:4326");
      
      dialogStore.showModelProcessingSearchRequestDialog({
        geoJson: geoJson
      });
      
      // Keep the drawn layer visible for now
    },
    cancelModelProcessing() {
      const mapStore = useMapStore();
      mapStore.removeDrawLayer();
      this.pendingModelProcessingFeature = null;
    },
    async onExistingResultsSelected(selection) {
        const dialogStore = useDialogStore();
        const taskInfo = dialogStore.selectedTaskInfo;

        if (selection.type === 'pair') {
            const taskLabel = taskInfo.task === 'cd-processor' ? 'CD-SR' : 'CD-CHM';
            this.cdResultName = `${taskLabel} existing ${Date.now().toString(36)}`;
            this.pendingCDSelection = selection;
            this.showCDNameDialog = true;

        } else if (selection.type === 'single') {
             // CD "mix" — o scenă din rezultate existente + o scenă nouă
            const newScene = dialogStore.cdSelectedSceneNew;

            if (!newScene) {
                // Fallback: dacă nu e scena nouă salvată, activează draw mode
                dialogStore.cdSelectedSceneExisting = selection.result;
                dialogStore.showConfirmDialog({
                    title: "Draw area for the new scene",
                    message: "Now draw the area on the map for the new scene.",
                    noButtonText: "Cancel",
                    yesButtonText: "Continue",
                    event: "MODEL_PROCESSING_ACTIVATE_DRAW_MODE"
                });
                return;
            }

             // Verificare overlap: rezultat existent vs zona desenată
            try {
                const copernicusStore = useCopernicusStore();
                const existingBbox = await copernicusStore.getGeotiffBbox(selection.result.path);
                const drawnBbox = dialogStore.modelProcessingSearchRequestDialog.requestInfo?.geoJson;
                
                if (existingBbox.bbox && drawnBbox) {
                    let drawnCoords;
                    if (drawnBbox.type === 'Polygon') drawnCoords = drawnBbox.coordinates[0];
                    else if (drawnBbox.type === 'FeatureCollection') drawnCoords = drawnBbox.features[0]?.geometry?.coordinates[0];
                    
                    if (drawnCoords) {
                        const lons = drawnCoords.map(c => c[0]);
                        const lats = drawnCoords.map(c => c[1]);
                        const drawnExtent = [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
                        const eb = existingBbox.bbox;
                        
                        // Verifică suprapunere
                        const overlaps = !(
                            eb[2] < drawnExtent[0] || 
                            eb[0] > drawnExtent[2] || 
                            eb[3] < drawnExtent[1] || 
                            eb[1] > drawnExtent[3]
                        );
                        
                        if (!overlaps) {
                            this.$toast.add({
                                severity: "error", summary: "Geographic mismatch",
                                detail: "The existing result and the new scene are not from the same geographic region. Please select a result from the same area.",
                                life: 8000
                            });
                            dialogStore.existingResultsDialogVisible = true;
                            return;
                        }
                    }
                }
            } catch (err) {
                console.warn('Overlap check failed:', err);
            }

            // Ambele scene sunt selectate — deschide name dialog
            const taskLabel = taskInfo.task === 'cd-processor' ? 'CD-SR' : 'CD-CHM';
            this.cdResultName = `${taskLabel} mix ${Date.now().toString(36)}`;
            this.pendingCDSelection = {
                type: 'mix',
                existingResult: selection.result,
                newScene: newScene
            };
            this.showCDNameDialog = true;
        }
    },

    async startCDFromExisting() {
        this.showCDNameDialog = false;
        const dialogStore = useDialogStore();
        const aiAgentStore = useAIAgentStore();
        const copernicusStore = useCopernicusStore();
        const selection = this.pendingCDSelection;
        const taskInfo = dialogStore.selectedTaskInfo;
        const isCHM = taskInfo?.task === 'cd-chm-processor';

        aiAgentStore.setSelectedAgent(taskInfo.task);
        aiAgentStore.resultName = this.cdResultName.trim();

        // Curăță harta
        const mapStore = useMapStore();
        mapStore.removeDrawLayer();

        // Progress dialog
        if (selection.type === 'pair') {
            dialogStore.showProcessingProgress([
                isCHM ? 'Running ΔCHM analysis' : 'Running CVA analysis',
                'Publishing to map',
                'Complete'
            ]);
        } else {
            dialogStore.showProcessingProgress([
                'Downloading new scene',
                isCHM ? 'Running ΔCHM analysis' : 'SR + Change Detection',
                'Publishing to map',
                'Complete'
            ]);
        }

        try {
            let result;

            if (selection.type === 'pair') {
                dialogStore.updateProcessingProgress(0, 'Analyzing changes...');

                const requestData = {
                    sr_t1_path: selection.t1.path,
                    sr_t2_path: selection.t2.path,
                    resultName: this.cdResultName.trim()
                };

                if (!isCHM) {
                    requestData.mode = 'fidelity';
                    requestData.threshold_method = 'otsu';
                }

                result = await aiAgentStore.processWithSelectedAgent(requestData);

                dialogStore.updateProcessingProgress(1, 'Publishing layers...');

            } else if (selection.type === 'mix') {
                dialogStore.updateProcessingProgress(0, 'Downloading new scene...');

                const existingPath = selection.existingResult.path;
                const newItem = selection.newScene;

                const dl = await copernicusStore.downloadImages([newItem.stac_item]);

                let downloadCompleted = false;
                let downloadResult = null;
                for (let i = 0; i < 60; i++) {
                    await new Promise(r => setTimeout(r, 5000));
                    const status = await copernicusStore.checkDownloadStatus(dl.task_id);
                    if (status.status === 'completed') { downloadResult = status; downloadCompleted = true; break; }
                    if (status.status === 'failed') throw new Error('Download failed');
                }
                if (!downloadCompleted) throw new Error('Download timeout');

                const s2Path = downloadResult.files ? downloadResult.files[0] : `${newItem.id}/${newItem.id}.zip`;

                const dateMatch = newItem.id.match(/(\d{8})T/);
                const targetDate = dateMatch
                    ? `${dateMatch[1].substring(0,4)}-${dateMatch[1].substring(4,6)}-${dateMatch[1].substring(6,8)}`
                    : newItem.datetime?.substring(0, 10);

                const geoJson = dialogStore.modelProcessingSearchRequestDialog.requestInfo?.geoJson;
                let bbox = null;
                if (geoJson) {
                    let coords;
                    if (geoJson.type === 'Polygon') coords = geoJson.coordinates[0];
                    else if (geoJson.type === 'FeatureCollection') coords = geoJson.features[0]?.geometry?.coordinates[0];
                    if (coords) {
                        const lons = coords.map(c => c[0]);
                        const lats = coords.map(c => c[1]);
                        bbox = [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
                    }
                }

                dialogStore.updateProcessingProgress(1, 'Processing SR + Change Detection...');

                result = await aiAgentStore.processWithSelectedAgent({
                    sr_t1_path: existingPath,
                    scene_t2: { s2_path: s2Path, bbox: bbox, target_date: targetDate },
                    mode: 'fidelity',
                    threshold_method: 'otsu',
                    resultName: this.cdResultName.trim()
                });

                dialogStore.updateProcessingProgress(2, 'Publishing layers...');
            }

            dialogStore.updateProcessingProgress(selection.type === 'pair' ? 2 : 3, 'Complete!');
            dialogStore.hideProcessingProgress();

            const stats = result.data.statistics;
            this.$toast.add({
                severity: "success", summary: "Change Detection Complete",
                detail: `Changes: ${stats?.changed_area_ha || stats?.deforestation_area_ha || '?'} ha`,
                life: 10000
            });

            dialogStore.resetCDFlow();
            dialogStore.resetAllProcessingState();

        } catch (error) {
            dialogStore.hideProcessingProgress();
            this.$toast.add({
                severity: "error", summary: "ERROR",
                detail: `CD failed: ${error.message}`, life: 5000
            });
        }
    },
  }
}
</script>

<style lang="scss" scoped>

</style>