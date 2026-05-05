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
        cdFlowStep: null,         // 'select_t1' | 'select_t2' | null
        cdSelectedSceneT1: null,  // scena selectată pentru T1
        cdSelectedSceneT2: null,  // scena selectată pentru T2
        cdDatesT1: null,          // perioadă T1
        cdDatesT2: null,          // perioadă T2
        cdSelectedSceneNew: null,
        processingProgress: {
            visible: false,
            step: 0,
            steps: [],
            label: '',
            detail: ''
        },
        cdSelectedSceneExisting: null,
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
        setSelectedTaskInfo(taskInfo) {
            this.selectedTaskInfo = taskInfo;
        },
        showExistingResultsDialog() {
            this.existingResultsDialogVisible = true;
        },
        hideExistingResultsDialog() {
            this.existingResultsDialogVisible = false;
        },
        resetCDFlow() {
            this.cdFlowStep = null;
            this.cdSelectedSceneT1 = null;
            this.cdSelectedSceneT2 = null;
            this.cdDatesT1 = null;
            this.cdDatesT2 = null;
            this.cdSelectedSceneExisting = null;
            this.cdSelectedSceneNew = null;
        },
        showProcessingProgress(steps) {
            this.processingProgress = {
                visible: true,
                step: 0,
                steps: steps,
                label: steps[0] || 'Processing...',
                detail: ''
            };
        },
        updateProcessingProgress(step, detail = '') {
            this.processingProgress.step = step;
            this.processingProgress.label = this.processingProgress.steps[step] || 'Processing...';
            this.processingProgress.detail = detail;
        },
        hideProcessingProgress() {
            this.processingProgress.visible = false;
        },
    }
})