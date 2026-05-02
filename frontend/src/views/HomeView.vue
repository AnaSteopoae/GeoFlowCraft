<template>

  <div id="map" class="relative h-full">
    <div class="absolute z-[100] right-1 top-1 p-1 bg-gray-800 w-[250px] border-2 border-gray-300 rounded-md flex flex-col gap-1">
      <!-- List of datasets -->
      <AppDataSetList class="border-b-2 border-gray-300" />
      <!-- List of visible datalayers -->
      <AppDataLayerList />
      <AppNavBar @open-existing-results="onOpenExistingResults" />
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
    <PrimeToast />
  </div>

</template>

<script>

import useMapStore from "@/stores/map";
import useDialogStore from "@/stores/dialog";
import useDataSetStore from "@/stores/dataSet";
import useDataLayerStore from "@/stores/dataLayer";

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

export default {
  name: "HomeView",
  components: { 
    AppConfirmDialog,
    AppDataSetList,
    AppDataSetCreateDialog, AppDataSetDetailsDialog,
    AppDataLayerList,
    AppDataLayersDialog, AppDataLayerCreateDialog,
    AppModelProcessingSearchRequestDialog, AppModelProcessingSearchResultsDialog,
    AppExistingResultsDialog

  },
  data() {
    return {
      pendingModelProcessingFeature: null,
      showExistingResults: false,
      existingResultsType: 'sr',
      existingResultsMax: 2
    }
  },
  mounted() {
    const mapStore = useMapStore();
    mapStore.initialize();
  },
  computed: {},
  methods: {
    onOpenExistingResults({ type, max }) {
    this.existingResultsType = type;
    this.existingResultsMax = max;
    this.showExistingResults = true;
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
      
      // Handle cancellation based on event type
      if (event === "CONFIRM_MODEL_PROCESSING_AREA") {
        this.cancelModelProcessing();
      }
      
      dialogStore.hideConfirmDialog();
    },
    activateDrawModeForModelProcessing() {
      const mapStore = useMapStore();
      mapStore.enableDrawInteraction("Polygon", this.confirmDrawnAreaForModelProcessing, true);
    },
    confirmDrawnAreaForModelProcessing(drawnFeature) {
      try {
        const mapStore = useMapStore();
        mapStore.disableDrawInteration();
        mapStore.addDrawLayer(drawnFeature);
        
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
    onExistingResultsSelected(selection) {
    console.log('Selected existing results:', selection);
    // TODO: procesează CD cu rezultatele selectate
    // selection.type === 'pair' → selection.t1, selection.t2
    // selection.type === 'single' → selection.result
    }
  }
}
</script>

<style lang="scss" scoped>

</style>