<template>
    <PrimeDialog v-model:visible="modelProcessingSearchRequestDialog.visible" modal header="Select time period" :closable="false">
        <div class="my-2 mb-6 flex flex-col gap-4">
            <!-- Selected task info -->
            <div class="flex items-center gap-3 p-3 rounded-lg" style="background: rgba(20, 184, 166, 0.1); border: 1px solid rgba(20, 184, 166, 0.3);">
                <i :class="taskIcon" style="font-size: 1.5rem; color: rgb(20 184 166);"></i>
                <div>
                    <div class="font-semibold text-sm" style="color: #f1f5f9;">{{ taskLabel }}</div>
                    <div class="text-xs" style="color: #94a3b8;">{{ taskDescription }}</div>
                </div>
            </div>

            <!-- SINGLE CALENDAR: SR, CHM, CD mix (scena nouă) -->
            <div v-if="!isCDNewMode" class="flex flex-col gap-1">
                <div class="w-full pl-3 text-start text-gray-400">Select the time interval</div>
                <PrimeDatePicker 
                    ref="datePicker"
                    v-model="modelProcessingSearchRequestDialog.requestInfo.selectedDates" 
                    :disabled="isLoading" 
                    selectionMode="range" 
                    showIcon 
                    fluid
                    @date-select="onDateSelect"
                />
                <div class="pl-3 text-xs text-gray-500 mt-1">
                    Satellite images from this period will be searched
                </div>
            </div>

            <!-- DUAL CALENDARS: CD new (T1 + T2) -->
            <div v-if="isCDNewMode" class="flex flex-col gap-4">
                <div class="flex flex-col gap-1">
                    <div class="w-full pl-3 text-start text-gray-400 flex items-center gap-2">
                        <span class="inline-block w-5 h-5 rounded-full text-center text-xs leading-5 font-bold" 
                              style="background: rgba(239, 68, 68, 0.3); color: #fca5a5;">1</span>
                        Scene T1 — older date (before change)
                    </div>
                    <PrimeDatePicker 
                        ref="datePickerT1"
                        v-model="datesT1" 
                        :disabled="isLoading" 
                        selectionMode="range" 
                        showIcon 
                        fluid
                        placeholder="Select T1 period"
                        @date-select="onDateSelectT1"
                    />
                </div>

                <div class="flex flex-col gap-1">
                    <div class="w-full pl-3 text-start text-gray-400 flex items-center gap-2">
                        <span class="inline-block w-5 h-5 rounded-full text-center text-xs leading-5 font-bold" 
                              style="background: rgba(34, 197, 94, 0.3); color: #86efac;">2</span>
                        Scene T2 — newer date (after change)
                    </div>
                    <PrimeDatePicker 
                        ref="datePickerT2"
                        v-model="datesT2" 
                        :disabled="isLoading" 
                        selectionMode="range" 
                        showIcon 
                        fluid
                        placeholder="Select T2 period"
                        @date-select="onDateSelectT2"
                    />
                </div>

                <div v-if="datesT1 && datesT2 && datesT1[1] && datesT2[0]" class="pl-3 text-xs" 
                     :style="{ color: isT2AfterT1 ? '#86efac' : '#fca5a5' }">
                    <i :class="isT2AfterT1 ? 'pi pi-check-circle' : 'pi pi-exclamation-triangle'"></i>
                    {{ isT2AfterT1 
                        ? `Gap between T1 and T2: ${daysBetween} days` 
                        : 'T2 must be after T1!' }}
                </div>
            </div>
        </div>

        <div class="flex justify-between items-center">
            <PrimeButton label="Back" icon="pi pi-arrow-left" severity="secondary" 
                @click="goBack" :disabled="isLoading"
            />
            <div>
                <i v-show="isLoading" class="pi pi-spin pi-spinner text-yellow-300" style="font-size: 2rem"></i>
            </div>
            <PrimeButton label="Search" icon="pi pi-search" severity="success" 
                @click="confirm" :disabled="isLoading || !canSearch"
            />
        </div>
        <PrimeToast />
    </PrimeDialog>
</template>

<script>
import { mapState } from "pinia";
import useDialogStore from "@/stores/dialog";
import useCopernicusStore from "@/stores/copernicus";
import useAIAgentStore from "@/stores/aiAgent";
import useMapStore from "@/stores/map";

export default {
    name: "AppModelProcessingSearchRequestDialog",
    data() {
        return { 
            isLoading: false,
            datesT1: null,
            datesT2: null
        }
    },
    computed: {
        ...mapState(useDialogStore, ["modelProcessingSearchRequestDialog"]),
        
        aiAgentStore() {
            return useAIAgentStore();
        },

        dialogStore() {
            return useDialogStore();
        },

        selectedAgent() {
            return this.aiAgentStore.selectedAgent;
        },

        taskInfo() {
            return this.dialogStore.selectedTaskInfo;
        },

        isCDNewMode() {
            return this.taskInfo 
                && (this.taskInfo.task === 'cd-processor' || this.taskInfo.task === 'cd-chm-processor')
                && this.taskInfo.cdSource === 'new';
        },

        isCDMixMode() {
            return this.taskInfo 
                && (this.taskInfo.task === 'cd-processor' || this.taskInfo.task === 'cd-chm-processor')
                && this.taskInfo.cdSource === 'mix';
        },

        taskLabel() {
            const labels = {
                'sr-processor': 'Super Resolution',
                'ch-processor': 'Canopy Height',
                'cd-processor': 'Change Detection (Urban)',
                'cd-chm-processor': 'Deforestation Detection'
            };
            return labels[this.selectedAgent] || 'Processing';
        },

        taskDescription() {
            if (this.isCDNewMode) {
                return 'Select date ranges for both T1 (before) and T2 (after) scenes';
            }
            if (this.isCDMixMode) {
                return 'Select date range for the new scene (the other will be chosen from existing results)';
            }
            const descs = {
                'sr-processor': `Mode: ${this.aiAgentStore.selectedSRMode || 'sharp'}`,
                'ch-processor': 'Global CHM Model — requires L2A scenes',
                'cd-processor': 'CVA on 2 super-resolved scenes',
                'cd-chm-processor': 'ΔCHM on 2 canopy height maps'
            };
            return descs[this.selectedAgent] || '';
        },

        taskIcon() {
            const icons = {
                'sr-processor': 'pi pi-image',
                'ch-processor': 'pi pi-sun',
                'cd-processor': 'pi pi-arrows-h',
                'cd-chm-processor': 'pi pi-chart-line'
            };
            return icons[this.selectedAgent] || 'pi pi-cog';
        },

        isT2AfterT1() {
            if (!this.datesT1?.[1] || !this.datesT2?.[0]) return true;
            return new Date(this.datesT2[0]) > new Date(this.datesT1[1]);
        },

        daysBetween() {
            if (!this.datesT1?.[1] || !this.datesT2?.[0]) return 0;
            const diff = new Date(this.datesT2[0]) - new Date(this.datesT1[1]);
            return Math.round(diff / (1000 * 60 * 60 * 24));
        },

        canSearch() {
            if (this.isCDNewMode) {
                return this.datesT1?.[0] && this.datesT1?.[1] 
                    && this.datesT2?.[0] && this.datesT2?.[1]
                    && this.isT2AfterT1;
            }
            const dates = this.modelProcessingSearchRequestDialog.requestInfo.selectedDates;
            return dates && dates.length >= 2 && dates[0] && dates[1];
        }
    },
    methods: {
        onDateSelect() {
            const dates = this.modelProcessingSearchRequestDialog.requestInfo.selectedDates;
            if (dates && dates.length === 2 && dates[0] && dates[1]) {
                this.$nextTick(() => {
                    if (this.$refs.datePicker) {
                        this.$refs.datePicker.overlayVisible = false;
                    }
                });
            }
        },

        onDateSelectT1() {
            if (this.datesT1 && this.datesT1.length === 2 && this.datesT1[0] && this.datesT1[1]) {
                this.$nextTick(() => {
                    if (this.$refs.datePickerT1) {
                        this.$refs.datePickerT1.overlayVisible = false;
                    }
                });
            }
        },

        onDateSelectT2() {
            if (this.datesT2 && this.datesT2.length === 2 && this.datesT2[0] && this.datesT2[1]) {
                this.$nextTick(() => {
                    if (this.$refs.datePickerT2) {
                        this.$refs.datePickerT2.overlayVisible = false;
                    }
                });
            }
        },

        goBack() {
            const dialogStore = useDialogStore();
            dialogStore.modelProcessingSearchRequestDialog.requestInfo.selectedDates = null;
            this.datesT1 = null;
            this.datesT2 = null;
            dialogStore.hideModelProcessingSearchRequestDialog();
            const mapStore = useMapStore();
            mapStore.removeDrawLayer();
            dialogStore.showTaskSelector();
        },

        close() {
            const dialogStore = useDialogStore();
            dialogStore.hideModelProcessingSearchRequestDialog();
        },

        async confirm() { 
            this.isLoading = true;

            if (this.isCDNewMode) {
                await this.searchForCD();
            } else {
                await this.searchSingle();
            }

            this.isLoading = false;
        },

        async searchSingle() {
            const dates = this.modelProcessingSearchRequestDialog.requestInfo.selectedDates;
            if (!dates || dates.length < 2) {
                this.$toast.add({ 
                    severity: "warn", summary: "WARNING", 
                    detail: "Please select a valid date range!", life: 3000
                });
                return;
            }

            const copernicusStore = useCopernicusStore();
            let searchResponse = await copernicusStore.search(
                this.modelProcessingSearchRequestDialog.requestInfo.geoJson,
                dates[0], dates[1]
            );
            
            if (searchResponse.status == "success" && searchResponse.items?.length > 0) {
                const dialogStore = useDialogStore();
                dialogStore.showModelProcessingSearchResultsDialog();
                this.close();
            } else if (searchResponse.status == "success") {
                this.$toast.add({ 
                    severity: "warn", summary: "WARNING", 
                    detail: "There is no data for the selected area and time interval!", life: 3000
                });
            } else {
                this.$toast.add({ 
                    severity: "error", summary: "ERROR", 
                    detail: "Something went wrong!", life: 3000
                });
            }
        },

        async searchForCD() {
            if (!this.datesT1?.[0] || !this.datesT1?.[1] || !this.datesT2?.[0] || !this.datesT2?.[1]) {
                this.$toast.add({ 
                    severity: "warn", summary: "WARNING", 
                    detail: "Please select both T1 and T2 date ranges!", life: 3000
                });
                return;
            }

            if (!this.isT2AfterT1) {
                this.$toast.add({ 
                    severity: "warn", summary: "WARNING", 
                    detail: "T2 must be after T1!", life: 3000
                });
                return;
            }

            // Salvează perioadele în store
            const dialogStore = useDialogStore();
            dialogStore.cdDatesT1 = this.datesT1;
            dialogStore.cdDatesT2 = this.datesT2;

            // Pas 1: Căutare pentru T1
            this.$toast.add({ 
                severity: "info", summary: "Searching T1", 
                detail: "Searching satellite images for the first period...", life: 3000
            });

            const copernicusStore = useCopernicusStore();
            let searchResponse = await copernicusStore.search(
                this.modelProcessingSearchRequestDialog.requestInfo.geoJson,
                this.datesT1[0], this.datesT1[1]
            );

            if (searchResponse.status == "success" && searchResponse.items?.length > 0) {
                dialogStore.cdFlowStep = 'select_t1';
                dialogStore.showModelProcessingSearchResultsDialog();
                this.close();
            } else if (searchResponse.status == "success") {
                this.$toast.add({ 
                    severity: "warn", summary: "WARNING", 
                    detail: "No data found for T1 period!", life: 3000
                });
            } else {
                this.$toast.add({ 
                    severity: "error", summary: "ERROR", 
                    detail: "Search failed!", life: 3000
                });
            }
        },
    }
}
</script>

<style lang="scss" scoped>
</style>