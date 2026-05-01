<template>
    <PrimeDialog 
        v-model:visible="visible" 
        modal 
        header="Choose processing task"
        :style="{ width: '55rem' }"
        :breakpoints="{ '1199px': '80vw', '575px': '95vw' }"
    >
        <div class="task-cards">
            <!-- Super Resolution -->
            <div 
                class="task-card" 
                :class="{ selected: selectedTask === 'sr-processor' }"
                @click="selectTask('sr-processor')"
            >
                <div class="task-icon">
                    <i class="pi pi-image" style="font-size: 2rem; color: rgb(20 184 166);"></i>
                </div>
                <div class="task-title">Super Resolution</div>
                <div class="task-subtitle">Enhance satellite imagery from 10m to 2.5m using SAR-optical fusion</div>
                <div class="task-badge">1 scene</div>
            </div>

            <!-- Canopy Height -->
            <div 
                class="task-card"
                :class="{ selected: selectedTask === 'ch-processor' }"
                @click="selectTask('ch-processor')"
            >
                <div class="task-icon">
                    <i class="pi pi-sun" style="font-size: 2rem; color: rgb(132 204 22);"></i>
                </div>
                <div class="task-title">Canopy Height</div>
                <div class="task-subtitle">Estimate vegetation canopy height using the Global CHM model</div>
                <div class="task-badge">1 scene (L2A)</div>
            </div>

            <!-- Change Detection SR -->
            <div 
                class="task-card"
                :class="{ selected: selectedTask === 'cd-processor' }"
                @click="selectTask('cd-processor')"
            >
                <div class="task-icon">
                    <i class="pi pi-arrows-h" style="font-size: 2rem; color: rgb(239 68 68);"></i>
                </div>
                <div class="task-title">Change Detection (Urban)</div>
                <div class="task-subtitle">Detect urban and land-use changes using CVA on super-resolved imagery</div>
                <div class="task-badge">2 scenes</div>
            </div>

            <!-- Change Detection CHM -->
            <div 
                class="task-card"
                :class="{ selected: selectedTask === 'cd-chm-processor' }"
                @click="selectTask('cd-chm-processor')"
            >
                <div class="task-icon">
                    <i class="pi pi-chart-line" style="font-size: 2rem; color: rgb(34 197 94);"></i>
                </div>
                <div class="task-title">Deforestation Detection</div>
                <div class="task-subtitle">Monitor forest canopy changes using ΔCHM analysis on two time periods</div>
                <div class="task-badge">2 CHM scenes</div>
            </div>
        </div>

        <!-- SR Mode selector -->
        <div v-if="selectedTask === 'sr-processor'" class="options-section">
            <div class="options-title">Super Resolution mode</div>
            <div class="sr-mode-options">
                <div 
                    v-for="mode in srModes" :key="mode.id"
                    class="sr-mode-option"
                    :class="{ selected: selectedSRMode === mode.id }"
                    @click="selectedSRMode = mode.id"
                >
                    <div class="mode-name">{{ mode.name }}</div>
                    <div class="mode-desc">{{ mode.shortDesc }}</div>
                </div>
            </div>
        </div>

        <!-- CD Source selector (visible for CD-SR and CD-CHM) -->
        <div v-if="isCDSelected" class="options-section">
            <div class="options-title">Choose data source</div>
            <div class="cd-source-options">
                <div 
                    class="cd-source-option"
                    :class="{ selected: cdSource === 'new' }"
                    @click="cdSource = 'new'"
                >
                    <i class="pi pi-plus-circle"></i>
                    <div>
                        <div class="option-title">New scenes</div>
                        <div class="option-desc">Draw area and select dates for both T1 and T2</div>
                    </div>
                </div>
                <div 
                    class="cd-source-option"
                    :class="{ selected: cdSource === 'existing' }"
                    @click="cdSource = 'existing'"
                >
                    <i class="pi pi-database"></i>
                    <div>
                        <div class="option-title">From existing results</div>
                        <div class="option-desc">Select 2 previously processed {{ selectedTask === 'cd-processor' ? 'SR' : 'CHM' }} results</div>
                    </div>
                </div>
                <div 
                    class="cd-source-option"
                    :class="{ selected: cdSource === 'mix' }"
                    @click="cdSource = 'mix'"
                >
                    <i class="pi pi-sync"></i>
                    <div>
                        <div class="option-title">Mix</div>
                        <div class="option-desc">One from existing results + one new scene</div>
                    </div>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="flex justify-between w-full">
                <PrimeButton label="Cancel" icon="pi pi-times" severity="danger" @click="close" />
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
import useDialogStore from "@/stores/dialog";
import useAIAgentStore from "@/stores/aiAgent";

export default {
    name: "AppTaskSelectorDialog",
    props: {
        modelValue: {
            type: Boolean,
            default: false
        }
    },
    emits: ['update:modelValue', 'task-selected'],
    data() {
        return {
            selectedTask: null,
            cdSource: 'new',
            selectedSRMode: 'sharp'
        }
    },
    computed: {
        visible: {
            get() { return this.modelValue; },
            set(val) { this.$emit('update:modelValue', val); }
        },
        isCDSelected() {
            return this.selectedTask === 'cd-processor' || this.selectedTask === 'cd-chm-processor';
        },
        canContinue() {
            if (!this.selectedTask) return false;
            if (this.isCDSelected && !this.cdSource) return false;
            return true;
        },
        srModes() {
            return [
                { id: 'sharp', name: 'Sharp', shortDesc: 'Sharpest edges — for visual inspection' },
                { id: 'balanced', name: 'Balanced', shortDesc: 'Best visual + fidelity balance' },
                { id: 'fidelity', name: 'Fidelity', shortDesc: 'Maximum spectral accuracy — for analysis' }
            ];
        }
    },
    methods: {
        selectTask(task) {
            this.selectedTask = task;
            if (!this.isCDSelected) {
                this.cdSource = 'new';
            }
        },
        close() {
            this.visible = false;
            this.selectedTask = null;
            this.cdSource = 'new';
        },
        onContinue() {
            const aiAgentStore = useAIAgentStore();
            
            // Setează agentul selectat
            if (this.selectedTask === 'sr-processor') {
                aiAgentStore.setSelectedAgent('sr-processor');
                aiAgentStore.setSRMode(this.selectedSRMode);
            } else if (this.selectedTask === 'ch-processor') {
                aiAgentStore.setSelectedAgent('ch-processor');
            } else if (this.selectedTask === 'cd-processor') {
                aiAgentStore.setSelectedAgent('cd-processor');
                aiAgentStore.setSRMode('fidelity');
            } else if (this.selectedTask === 'cd-chm-processor') {
                aiAgentStore.setSelectedAgent('cd-chm-processor');
            }

            this.$emit('task-selected', {
                task: this.selectedTask,
                cdSource: this.cdSource,
                srMode: this.selectedSRMode
            });

            this.visible = false;
        }
    }
}
</script>

<style lang="scss" scoped>
.task-cards {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.task-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 1.25rem 1rem;
    border: 2px solid transparent;
    border-radius: 12px;
    background: var(--p-surface-800, #1e293b);
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
        border-color: rgba(255, 255, 255, 0.2);
        background: var(--p-surface-700, #334155);
    }

    &.selected {
        border-color: rgb(20 184 166);
        background: rgba(20, 184, 166, 0.1);
    }

    .task-icon {
        margin-bottom: 0.75rem;
    }

    .task-title {
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 0.5rem;
        color: #f1f5f9;
    }

    .task-subtitle {
        font-size: 0.8rem;
        color: #94a3b8;
        line-height: 1.4;
        margin-bottom: 0.75rem;
    }

    .task-badge {
        font-size: 0.7rem;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.1);
        color: #cbd5e1;
    }
}

.options-section {
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    padding-top: 1rem;
    margin-bottom: 1rem;

    .options-title {
        font-weight: 500;
        color: #94a3b8;
        margin-bottom: 0.75rem;
        padding-left: 0.25rem;
    }
}

.sr-mode-options {
    display: flex;
    gap: 0.5rem;
}

.sr-mode-option {
    flex: 1;
    padding: 0.75rem;
    border: 1.5px solid transparent;
    border-radius: 8px;
    background: var(--p-surface-800, #1e293b);
    cursor: pointer;
    text-align: center;
    transition: all 0.2s;

    &:hover {
        border-color: rgba(255, 255, 255, 0.15);
    }

    &.selected {
        border-color: rgb(20 184 166);
        background: rgba(20, 184, 166, 0.08);
    }

    .mode-name {
        font-weight: 500;
        font-size: 0.9rem;
        color: #e2e8f0;
    }

    .mode-desc {
        font-size: 0.7rem;
        color: #64748b;
        margin-top: 0.25rem;
    }
}

.cd-source-options {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.cd-source-option {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border: 1.5px solid transparent;
    border-radius: 8px;
    background: var(--p-surface-800, #1e293b);
    cursor: pointer;
    transition: all 0.2s;

    i {
        font-size: 1.25rem;
        color: #64748b;
    }

    &:hover {
        border-color: rgba(255, 255, 255, 0.15);
    }

    &.selected {
        border-color: rgb(20 184 166);
        background: rgba(20, 184, 166, 0.08);

        i { color: rgb(20 184 166); }
    }

    .option-title {
        font-weight: 500;
        font-size: 0.9rem;
        color: #e2e8f0;
    }

    .option-desc {
        font-size: 0.75rem;
        color: #64748b;
    }
}
</style>