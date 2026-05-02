import { defineStore } from "pinia";

export default defineStore('dialog', {
    state: () => ({
        dataSetCreateDialogVisible: false,
        dataSetDetailsDialogVisible: false,
        dataLayersDialogVisible: false,
        dataLayerCreateDialogVisible: false,
        modelProcessingSearchRequestDialog: {
            visible: false,
            isLoading: false,
            requestInfo: {
                selectedModel: null,
                selectedDates: null,
                geoJson: null
            }
        },
        modelProcessingSearchResultsDialog: {
            visible: false
        },
        confirmDialogVisible: false,
        confirmDialogInfo: null,
        confirmDialogIsLoading: false,
        taskSelectorVisible: false,
        selectedTaskInfo: null,  // { task, cdSource, srMode }
        existingResultsDialogVisible: false,
    }),
    actions: {
        // DataSetCreateDialog
        showDataSetCreateDialog() {
            this.dataSetCreateDialogVisible = true;
        },
        hideDataSetCreateDialog() {
            this.dataSetCreateDialogVisible = false;
        },
        // DataSetDetailsDialog
        showDataSetDetailsDialog() {
            this.dataSetDetailsDialogVisible = true;
        },
        hideDataSetDetailsDialog() {
            this.dataSetDetailsDialogVisible = false;
        },
        // DataLayersDialog
        showDataLayersDialog() {
            this.dataLayersDialogVisible = true;
        },
        hideDataLayersDialog() {
            this.dataLayersDialogVisible = false;
        },
        // DataLayerCreateDialog
        showDataLayerCreateCatalog() {
            this.dataLayerCreateDialogVisible = true;
        },
        hideDataLayerCreateCatalog() {
            this.dataLayerCreateDialogVisible = false;
        },
        // ModelProcessingSearchRequestDialog
        showModelProcessingSearchRequestDialog(requestInfo) {
            if(!(requestInfo?.geoJson)) {
                throw "Missing 'geoJSON' for creating the model processing request!"
            }

            this.modelProcessingSearchRequestDialog.requestInfo.geoJson = requestInfo.geoJson;
            this.modelProcessingSearchRequestDialog.visible = true;
        },
        hideModelProcessingSearchRequestDialog() {
            this.modelProcessingSearchRequestDialog.visible = false;
        },
        // ModelProcessingSearchResultsDialog
        showModelProcessingSearchResultsDialog() {
            this.modelProcessingSearchResultsDialog.visible = true;
        },
        hideModelProcessingSearchResultsDialog() {
            this.modelProcessingSearchResultsDialog.visible = false;
        },
        // ConfirmDialog
        showConfirmDialog(confirmInfo) {
            this.confirmDialogInfo = confirmInfo;
            this.confirmDialogVisible = true;
        },
        hideConfirmDialog() {
            this.confirmDialogVisible = false;
            this.confirmDialogInfo = null;
        },
        showTaskSelector() {
            this.taskSelectorVisible = true;
        },
        hideTaskSelector() {
            this.taskSelectorVisible = false;
        },
        showTaskSelector() {
            this.taskSelectorVisible = true;
        },
        hideTaskSelector() {
            this.taskSelectorVisible = false;
        },
        setSelectedTaskInfo(taskInfo) {
            this.selectedTaskInfo = taskInfo;
        },
        showExistingResultsDialog() {
            this.existingResultsDialogVisible = true;
        },
        hideExistingResultsDialog() {
            this.existingResultsDialogVisible = false;
        },
    }
})