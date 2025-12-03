<template>
    <PrimeDialog v-model:visible="modelProcessingSearchRequestDialog.visible" modal header="Search available data for the selected area" :closable="false">
        <div class="my-2 mb-6 flex flex-col gap-4">
            <!-- AI Model Selection -->
            <div class="flex flex-col gap-1">
                <div class="w-full pl-3 text-start text-gray-400">Select AI Model</div>
                <PrimeSelect 
                    v-model="selectedAIModel" 
                    :options="aiAgentStore.availableAgents" 
                    optionLabel="name" 
                    optionValue="id"
                    placeholder="Choose an AI model"
                    :disabled="isLoading || aiAgentStore.isLoading"
                    fluid
                >
                    <template #option="slotProps">
                        <div class="flex flex-col">
                            <div class="font-semibold">{{ slotProps.option.name }}</div>
                            <div class="text-xs text-gray-400">{{ slotProps.option.description }}</div>
                        </div>
                    </template>
                </PrimeSelect>
                <!-- Agent Info -->
                <div v-if="selectedAgentInfo" class="pl-3 text-xs text-gray-400 mt-1">
                    <div><strong>Input:</strong> {{ selectedAgentInfo.inputFormat }}</div>
                    <div><strong>Output:</strong> {{ selectedAgentInfo.outputFormat }}</div>
                </div>
            </div>

            <!-- Date range input -->
            <div class="flex flex-col gap-1">
                <div class="w-full pl-3 text-start text-gray-400">Select the time interval</div>
                <PrimeDatePicker 
                    v-model="modelProcessingSearchRequestDialog.requestInfo.selectedDates" :disabled="isLoading" 
                    selectionMode="range" showIcon fluid 
                />
            </div>
        </div>
        <div class="flex justify-between items-center">
            <PrimeButton label="Close" icon="pi pi-times" severity="danger" 
                @click="close" :disabled="isLoading"
            />
            <div>
                <i v-show="isLoading || aiAgentStore.isLoading" class="pi pi-spin pi-spinner text-yellow-300" style="font-size: 2rem"></i>
            </div>
            <PrimeButton label="Confirm" icon="pi pi-check" severity="success" 
                @click="confirm" :disabled="isLoading || !selectedAIModel"
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

export default {
    name: "AppModelProcessingSearchRequestDialog",
    components: { },
    data() {
        return { 
            isLoading: false,
            selectedAIModel: null
        }
    },
    computed: {
        ...mapState(useDialogStore, ["modelProcessingSearchRequestDialog"]),
        
        aiAgentStore() {
            return useAIAgentStore();
        },
        
        selectedAgentInfo() {
            if (!this.selectedAIModel) return null;
            return this.aiAgentStore.availableAgents.find(agent => agent.id === this.selectedAIModel);
        }
    },
    async mounted() {
        // Încarcă agenții AI când se deschide dialogul
        await this.aiAgentStore.loadAvailableAgents();
        
        // Setează primul agent ca selectat by default
        if (this.aiAgentStore.availableAgents.length > 0) {
            this.selectedAIModel = this.aiAgentStore.availableAgents[0].id;
        }
    },
    methods: {
        close() {
            const dialogStore = useDialogStore();
            dialogStore.hideModelProcessingSearchRequestDialog();
        },
        async confirm() { 
            this.isLoading = true;

            // Validare
            if (!this.selectedAIModel) {
                this.$toast.add({ 
                    severity: "warn", 
                    summary: "WARNING", 
                    detail: "Please select an AI model!", 
                    life: 3000
                });
                this.isLoading = false;
                return;
            }

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

            // Salvează modelul selectat în store pentru a-l folosi mai târziu
            this.aiAgentStore.setSelectedAgent(this.selectedAIModel);

            // Send search request
            const copernicusStore = useCopernicusStore();
            let searchResponse = await copernicusStore.search(
                this.modelProcessingSearchRequestDialog.requestInfo.geoJson,
                this.modelProcessingSearchRequestDialog.requestInfo.selectedDates[0],
                this.modelProcessingSearchRequestDialog.requestInfo.selectedDates[1]
            );
            
            // Display available data
            if(searchResponse.status == "success") {
                if(searchResponse.items?.length > 0) {
                    const dialogStore = useDialogStore();
                    // Display results dialog
                    dialogStore.showModelProcessingSearchResultsDialog();
                    // Hide search dialog
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