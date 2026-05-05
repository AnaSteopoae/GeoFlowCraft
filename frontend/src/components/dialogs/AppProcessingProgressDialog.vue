<template>
    <PrimeDialog 
        v-model:visible="visible" 
        modal 
        :closable="false"
        header="Processing in progress"
        :style="{ width: '30rem' }"
    >
        <div class="flex flex-col gap-4 py-2">
            <!-- Current step -->
            <div class="flex items-center gap-3">
                <i class="pi pi-spin pi-spinner text-teal-400" style="font-size: 1.5rem;"></i>
                <div>
                    <div class="font-semibold text-sm" style="color: #f1f5f9;">{{ currentStepLabel }}</div>
                    <div class="text-xs" style="color: #94a3b8;">{{ currentStepDetail }}</div>
                </div>
            </div>

            <!-- Progress bar -->
            <div class="w-full bg-gray-700 rounded-full h-2">
                <div class="h-2 rounded-full transition-all duration-500"
                     :style="{ width: progressPercent + '%', background: 'rgb(20 184 166)' }">
                </div>
            </div>

            <!-- Steps list -->
            <div class="flex flex-col gap-1">
                <div v-for="(step, index) in steps" :key="index"
                     class="flex items-center gap-2 text-xs py-1"
                     :style="{ color: getStepColor(index) }">
                    <i :class="getStepIcon(index)" style="font-size: 0.75rem; width: 16px;"></i>
                    <span>{{ step }}</span>
                </div>
            </div>

            <!-- Elapsed time -->
            <div class="text-xs text-gray-500 text-right">
                Elapsed: {{ elapsedFormatted }}
            </div>
        </div>
    </PrimeDialog>
</template>

<script>
export default {
    name: "AppProcessingProgressDialog",
    props: {
        modelValue: {
            type: Boolean,
            default: false
        },
        currentStep: {
            type: Number,
            default: 0
        },
        steps: {
            type: Array,
            default: () => []
        },
        currentStepLabel: {
            type: String,
            default: 'Processing...'
        },
        currentStepDetail: {
            type: String,
            default: ''
        }
    },
    emits: ['update:modelValue'],
    data() {
        return {
            startTime: Date.now(),
            elapsed: 0,
            timer: null
        }
    },
    computed: {
        visible: {
            get() { return this.modelValue; },
            set(val) { this.$emit('update:modelValue', val); }
        },
        progressPercent() {
            if (this.steps.length === 0) return 0;
            return Math.round(((this.currentStep + 1) / this.steps.length) * 100);
        },
        elapsedFormatted() {
            const s = Math.floor(this.elapsed / 1000);
            const m = Math.floor(s / 60);
            const sec = s % 60;
            return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
        }
    },
    watch: {
        modelValue(val) {
            if (val) {
                this.startTime = Date.now();
                this.elapsed = 0;
                this.timer = setInterval(() => {
                    this.elapsed = Date.now() - this.startTime;
                }, 1000);
            } else {
                clearInterval(this.timer);
            }
        }
    },
    beforeUnmount() {
        clearInterval(this.timer);
    },
    methods: {
        getStepIcon(index) {
            if (index < this.currentStep) return 'pi pi-check-circle text-green-400';
            if (index === this.currentStep) return 'pi pi-spin pi-spinner text-teal-400';
            return 'pi pi-circle text-gray-600';
        },
        getStepColor(index) {
            if (index < this.currentStep) return '#86efac';
            if (index === this.currentStep) return '#5eead4';
            return '#4b5563';
        }
    }
}
</script>