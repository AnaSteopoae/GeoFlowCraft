<template>
    <PrimeDialog 
        v-model:visible="visible" 
        modal 
        :header="dialogHeader"
        :style="{ width: '50rem' }"
        :closable="false"
        :breakpoints="{ '1199px': '75vw', '575px': '90vw' }"
    >
        <div class="existing-results-dialog">
            <!-- Info banner -->
            <div class="flex items-center gap-3 p-3 rounded-lg mb-4" 
                 style="background: rgba(20, 184, 166, 0.1); border: 1px solid rgba(20, 184, 166, 0.3);">
                <i class="pi pi-info-circle" style="font-size: 1.25rem; color: rgb(20 184 166);"></i>
                <div class="text-sm" style="color: #94a3b8;">
                    {{ selectionInstructions }}
                </div>
            </div>

            <!-- Selection status -->
            <div v-if="maxSelections === 2" class="flex gap-4 mb-3">
                <div class="flex items-center gap-2 px-3 py-1 rounded-lg text-sm"
                     :style="{ 
                         background: selectedT1 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255,255,255,0.05)',
                         border: selectedT1 ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid transparent'
                     }">
                    <span class="inline-block w-5 h-5 rounded-full text-center text-xs leading-5 font-bold" 
                          style="background: rgba(239, 68, 68, 0.3); color: #fca5a5;">1</span>
                    T1: {{ selectedT1 ? selectedT1.name : 'Not selected' }}
                </div>
                <div class="flex items-center gap-2 px-3 py-1 rounded-lg text-sm"
                     :style="{ 
                         background: selectedT2 ? 'rgba(34, 197, 94, 0.15)' : 'rgba(255,255,255,0.05)',
                         border: selectedT2 ? '1px solid rgba(34, 197, 94, 0.4)' : '1px solid transparent'
                     }">
                    <span class="inline-block w-5 h-5 rounded-full text-center text-xs leading-5 font-bold" 
                          style="background: rgba(34, 197, 94, 0.3); color: #86efac;">2</span>
                    T2: {{ selectedT2 ? selectedT2.name : 'Not selected' }}
                </div>
            </div>

            <!-- Loading -->
            <div v-if="isLoading" class="flex flex-col items-center p-6 gap-2">
                <i class="pi pi-spin pi-spinner text-teal-400" style="font-size: 2rem;"></i>
                <span class="text-gray-400 text-sm">Loading results...</span>
            </div>

            <!-- Results list -->
            <div v-else-if="filteredResults.length > 0" class="max-h-[300px] overflow-y-auto rounded-lg bg-gray-500/10">
                <div class="flex flex-row gap-1 text-sm text-gray-500 border-b border-gray-600 mb-1 px-3 py-2 font-bold sticky top-0" style="background: #1e293b;">
                    <div class="w-[30px]"></div>
                    <div class="w-[250px]">Name</div>
                    <div class="w-[100px]">Type</div>
                    <div class="w-[100px]">Size</div>
                    <div class="w-[120px]">Date</div>
                </div>
                <div v-for="result in filteredResults" :key="result.filename"
                    class="flex flex-row gap-1 px-3 py-2 hover:bg-gray-600 cursor-pointer items-center"
                    :class="{ 
                        'bg-red-900/20': isSelectedAsT1(result),
                        'bg-green-900/20': isSelectedAsT2(result)
                    }"
                    @click="selectResult(result)"
                >
                    <div class="w-[30px] flex items-center">
                        <span v-if="isSelectedAsT1(result)" 
                              class="inline-block w-5 h-5 rounded-full text-center text-xs leading-5 font-bold"
                              style="background: rgba(239, 68, 68, 0.3); color: #fca5a5;">1</span>
                        <span v-else-if="isSelectedAsT2(result)" 
                              class="inline-block w-5 h-5 rounded-full text-center text-xs leading-5 font-bold"
                              style="background: rgba(34, 197, 94, 0.3); color: #86efac;">2</span>
                         <span v-else-if="maxSelections === 1 && isSelectedAsSingle(result)"
                              class="inline-block w-5 h-5 rounded-full text-center text-xs leading-5 font-bold"
                              style="background: rgba(20, 184, 166, 0.4); color: #5eead4;">✓</span>
                        <span v-else-if="maxSelections === 1"
                              class="w-5 h-5 rounded-full border border-gray-600 inline-block"></span>
                        <span v-else class="w-5 h-5 rounded-full border border-gray-600 inline-block"></span>
                    </div>
                    <div class="w-[250px] text-sm truncate" :title="result.filename">
                        {{ result.filename }}
                    </div>
                    <div class="w-[100px]">
                        <span class="text-xs px-2 py-1 rounded-full" 
                              :style="{ background: getTypeBg(result.type), color: getTypeColor(result.type) }">
                            {{ result.type }}
                        </span>
                    </div>
                    <div class="w-[100px] text-sm text-gray-400">
                        {{ formatSize(result.size) }}
                    </div>
                    <div class="w-[120px] text-sm text-gray-400">
                        {{ formatDate(result.modifiedAt) }}
                    </div>
                </div>
            </div>

            <!-- No results -->
            <div v-else class="flex flex-col items-center p-6 gap-2 text-gray-400">
                <i class="pi pi-inbox" style="font-size: 2.5rem;"></i>
                <p>No {{ resultTypeLabel }} results found.</p>
                <p class="text-xs text-gray-500">Process some images first using the {{ resultTypeLabel }} model.</p>
            </div>
        </div>

        <template #footer>
            <div class="flex justify-between w-full">
                <PrimeButton label="Cancel" icon="pi pi-times" severity="secondary" @click="cancel" />
                <PrimeButton 
                    label="Continue" 
                    icon="pi pi-arrow-right" 
                    severity="success"
                    :disabled="!canContinue"
                    @click="onContinue" 
                />
            </div>
        </template>
    </PrimeDialog>
</template>

<script>
import useAIAgentStore from "@/stores/aiAgent";
import useDialogStore from "@/stores/dialog";
import moment from 'moment';
import useCopernicusStore from "@/stores/copernicus";
import useMapStore from "@/stores/map";

export default {
    name: "AppExistingResultsDialog",
    props: {
        modelValue: {
            type: Boolean,
            default: false
        },
        maxSelections: {
            type: Number,
            default: 2  // 2 for CD "existing", 1 for CD "mix"
        },
        resultType: {
            type: String,
            default: 'sr'  // 'sr' sau 'chm'
        }
    },
    emits: ['update:modelValue', 'results-selected'],
    data() {
        return {
            isLoading: false,
            allResults: [],
            selectedT1: null,
            selectedT2: null,
            selectedSingle: null
        }
    },
    computed: {
        visible: {
            get() { return this.modelValue; },
            set(val) { this.$emit('update:modelValue', val); }
        },

        dialogHeader() {
            if (this.maxSelections === 1) {
                return `Select a ${this.resultTypeLabel} result`;
            }
            return `Select 2 ${this.resultTypeLabel} results for comparison`;
        },

        selectionInstructions() {
            if (this.maxSelections === 1) {
                return `Select one existing ${this.resultTypeLabel} result to use as one of the Change Detection inputs.`;
            }
            return `Select 2 ${this.resultTypeLabel} results. Click once for T1 (older), click again for T2 (newer). Click a selected item to deselect it.`;
        },

        resultTypeLabel() {
            return this.resultType === 'sr' ? 'Super Resolution' : 'Canopy Height';
        },

        filteredResults() {
            const typePrefix = this.resultType === 'sr' ? 'SR' : 'Canopy Height';
            return this.allResults.filter(r => 
                r.type.startsWith(typePrefix) || r.type.startsWith('SR') && this.resultType === 'sr'
                || r.type === 'Canopy Height' && this.resultType === 'chm'
            );
        },

        canContinue() {
            if (this.maxSelections === 1) {
                return this.selectedSingle !== null;
            }
            return this.selectedT1 !== null && this.selectedT2 !== null;
        }
    },
    watch: {
        modelValue(val) {
            if (val) {
                this.loadResults();
                this.selectedT1 = null;
                this.selectedT2 = null;
                this.selectedSingle = null;
            }
        }
    },
    methods: {
        async loadResults() {
            this.isLoading = true;
            try {
                const aiAgentStore = useAIAgentStore();
                const response = await aiAgentStore.loadAllProcessingResults();
                
                if (response.success) {
                    const allResults = [];
                    Object.keys(response.results).forEach(productId => {
                        response.results[productId].forEach(file => {
                            allResults.push({ ...file, productId });
                        });
                    });
                    this.allResults = allResults;
                }
            } catch (error) {
                console.error('Error loading results:', error);
            } finally {
                this.isLoading = false;
            }
        },

        selectResult(result) {
            if (this.maxSelections === 1) {
                this.selectedSingle = this.selectedSingle === result ? null : result;
                return;
            }

            // Dual selection (T1, T2)
            if (this.isSelectedAsT1(result)) {
                this.selectedT1 = null;
            } else if (this.isSelectedAsT2(result)) {
                this.selectedT2 = null;
            } else if (!this.selectedT1) {
                this.selectedT1 = result;
            } else if (!this.selectedT2) {
                this.selectedT2 = result;
            } else {
                // Ambele sunt selectate — înlocuiește T2
                this.selectedT2 = result;
            }
        },

        isSelectedAsT1(result) {
            return this.selectedT1 && this.selectedT1.filename === result.filename;
        },

        isSelectedAsT2(result) {
            return this.selectedT2 && this.selectedT2.filename === result.filename;
        },

        cancel() {
            this.visible = false;
            const mapStore = useMapStore();
            mapStore.removeAllOverlays();
            const dialogStore = useDialogStore();
            dialogStore.resetAllProcessingState();
        },

        async onContinue() {
            if (this.maxSelections === 2 && this.selectedT1 && this.selectedT2) {
                // Verificare overlap
                try {
                    const copernicusStore = useCopernicusStore();
                    const overlap = await copernicusStore.checkOverlap(
                        this.selectedT1.path, 
                        this.selectedT2.path
                    );
                    if (!overlap.overlapping) {
                        this.$toast.add({
                            severity: "error", summary: "Geographic mismatch",
                            detail: "The two selected results are not from the same geographic region.",
                            life: 8000
                        });
                         // Resetează selecția dar rămâne pe dialog
                        this.selectedT1 = null;
                        this.selectedT2 = null;
                        return;  // Nu închide dialogul
                    }
                } catch (err) {
                    console.warn('Overlap check failed:', err);
                }
            }

            if (this.maxSelections === 1) {
                this.$emit('results-selected', {
                    type: 'single',
                    result: this.selectedSingle
                });
            } else {
                this.$emit('results-selected', {
                    type: 'pair',
                    t1: this.selectedT1,
                    t2: this.selectedT2
                });
            }
            this.visible = false;
        },

        formatSize(bytes) {
            if (!bytes) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
        },

        formatDate(date) {
            return date ? moment(date).format('YYYY-MM-DD HH:mm') : '-';
        },

        getTypeBg(type) {
            if (type.includes('SR')) return 'rgba(234, 179, 8, 0.2)';
            if (type.includes('Canopy')) return 'rgba(34, 197, 94, 0.2)';
            return 'rgba(255,255,255,0.1)';
        },

        getTypeColor(type) {
            if (type.includes('SR')) return '#fbbf24';
            if (type.includes('Canopy')) return '#86efac';
            return '#94a3b8';
        },
        isSelectedAsSingle(result) {
            return this.selectedSingle && this.selectedSingle.filename === result.filename;
        },
    }
}
</script>

<style lang="scss" scoped>
.existing-results-dialog {
    min-height: 200px;
}
</style>