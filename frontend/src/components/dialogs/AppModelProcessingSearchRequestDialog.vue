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

            <!-- Date range input -->
            <div class="flex flex-col gap-1">
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
                    <span v-if="isCDTask">Select the period covering both T1 and T2 dates</span>
                    <span v-else>Satellite images from this period will be searched</span>
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
                @click="confirm" :disabled="isLoading"
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
    components: { },
    data() {
        return { 
            isLoading: false
        }
    },
    computed: {
        ...mapState(useDialogStore, ["modelProcessingSearchRequestDialog"]),
        
        aiAgentStore() {
            return useAIAgentStore();
        },

        selectedAgent() {
            return this.aiAgentStore.selectedAgent;
        },

        isCDTask() {
            return this.selectedAgent === 'cd-processor' || this.selectedAgent === 'cd-chm-processor';
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
            const descs = {
                'sr-processor': `Mode: ${this.aiAgentStore.selectedSRMode || 'sharp'}`,
                'ch-processor': 'Global CHM Model — requires L2A scenes',
                'cd-processor': 'CVA on 2 super-resolved scenes (fidelity mode)',
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
        }
    },
    methods: {
        goBack() {
            const dialogStore = useDialogStore();
            // Resetează datele din calendar
            dialogStore.modelProcessingSearchRequestDialog.requestInfo.selectedDates = null;
            
            dialogStore.hideModelProcessingSearchRequestDialog();
            
            // Șterge zona desenată
            const mapStore = useMapStore();
            mapStore.removeDrawLayer();
            
            // Redeschide task selector
            dialogStore.showTaskSelector();
        },
        close() {
            const dialogStore = useDialogStore();
            dialogStore.hideModelProcessingSearchRequestDialog();
        },
        onDateSelect() {
            const dates = this.modelProcessingSearchRequestDialog.requestInfo.selectedDates;
            // Când ambele date sunt selectate, închide calendarul
            if (dates && dates.length === 2 && dates[0] && dates[1]) {
                this.$nextTick(() => {
                    if (this.$refs.datePicker) {
                        this.$refs.datePicker.overlayVisible = false;
                    }
                });
            }
        },
        async confirm() { 
            this.isLoading = true;

            if (!this.modelProcessingSearchRequestDialog.requestInfo.selectedDates || 
                this.modelProcessingSearchRequestDialog.requestInfo.selectedDates.length < 2) {
                this.$toast.add({ 
                    severity: "warn", 
                    summary: "WARNING", 
                    detail: "Please select a valid date range!", 
                    life: 3000
                });
                this.isLoading = false;
                return;
            }

            const copernicusStore = useCopernicusStore();
            let searchResponse = await copernicusStore.search(
                this.modelProcessingSearchRequestDialog.requestInfo.geoJson,
                this.modelProcessingSearchRequestDialog.requestInfo.selectedDates[0],
                this.modelProcessingSearchRequestDialog.requestInfo.selectedDates[1]
            );
            
            if(searchResponse.status == "success") {
                if(searchResponse.items?.length > 0) {
                    const dialogStore = useDialogStore();
                    dialogStore.showModelProcessingSearchResultsDialog();
                    this.close();
                } else {
                    this.$toast.add({ 
                        severity: "warn", 
                        summary: "WARNING", 
                        detail: `There is no data for the selected area and time interval!`, 
                        life: 3000
                    });
                }
            } else {
                this.$toast.add({ 
                    severity: "error", 
                    summary: "ERROR", 
                    detail: `Something went wrong!`, 
                    life: 3000
                });
            }

            this.isLoading = false;
        }
    }
}
</script>

<style lang="scss" scoped>
</style>