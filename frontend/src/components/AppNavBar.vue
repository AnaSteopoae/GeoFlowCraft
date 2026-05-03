<template>
    <div class="bg-gray-800">
        <!-- Processing Results Dialog -->
        <AppProcessingResultsDialog 
            v-model="showProcessingResultsDialog"
            :productId="null"
        />
        
        <nav class="min-w-[200px] flex flex-row items-center gap-2 p-2 shadow-lg shadow-green-500/50">

            <!-- Logo -->
            <div class="flex flex-row items-center justify-center gap-2">
                <!-- Image -->
                <img alt="GeoFlowCraft logo" class="logo" src="@/assets/planet_icon_512x512.png" width="50"
                    height="50" />
                <!-- Title -->
                <RouterLink to="/"><span class="font-bold text-2xl text-teal-400">GeoFlowCraft</span></RouterLink>
            </div>
            <!-- Nav links -->
            <div class="flex h-full border border-gray-700">
                <nav class="flex flex-row items-center justify-center">
                    <RouterLink to="/">Home</RouterLink>
                    <RouterLink to="/about">About</RouterLink>
                </nav>
            </div>
            <PrimeButton label="Model processing" icon="pi pi-microchip" 
                @click="showDrawConfirmDialog"
            />
            <PrimeButton 
                label="View Results" 
                icon="pi pi-chart-bar" 
                severity="info" 
                outlined
                @click="showResultsDialog"
            />
            <AppTaskSelectorDialog 
                v-model="taskSelectorVisible" 
                @task-selected="onTaskSelected" 
            />
        </nav>
    </div>
</template>

<script>
import { RouterLink } from 'vue-router'
import useDialogStore from "@/stores/dialog";
import AppProcessingResultsDialog from "@/components/dialogs/AppProcessingResultsDialog.vue";
import AppTaskSelectorDialog from "@/components/dialogs/AppTaskSelectorDialog.vue";
import { useDialog } from 'primevue';

export default {
    name: "AppNavBar",
    components: {
        RouterLink,
        AppProcessingResultsDialog,
        AppTaskSelectorDialog
    },
    data() {
        return {
            showProcessingResultsDialog: false
        }
    },
    computed: {
        taskSelectorVisible: {
            get() { return useDialogStore().taskSelectorVisible; },
            set(val) { 
                const store = useDialogStore();
                if (val) store.showTaskSelector();
                else store.hideTaskSelector();
            }
        }
    },
    methods: {
        showDrawConfirmDialog() {
            const dialogStore = useDialogStore();
            dialogStore.showTaskSelector();
        },
        showResultsDialog() {
            this.showProcessingResultsDialog = true;
        },
        onTaskSelected(taskInfo) {
        // După ce utilizatorul alege task-ul, activează draw mode
            const dialogStore = useDialogStore();
            dialogStore.setSelectedTaskInfo(taskInfo);

            // CD cu "existing" → deschide dialogul de rezultate existente
            if ((taskInfo.task === 'cd-processor' || taskInfo.task === 'cd-chm-processor') 
                && taskInfo.cdSource === 'existing') {
                dialogStore.existingResultsDialogVisible = true;
                return;
            }
            dialogStore.showConfirmDialog({
                title: "Model processing - draw mode activation",
                message: "Draw mode will be activated. Draw a polygon on the map to select the area.",
                noButtonText: "Discard",
                yesButtonText: "Confirm",
                event: "MODEL_PROCESSING_ACTIVATE_DRAW_MODE"
            });
        }
    }
}

</script>

<style lang="scss">
nav a.router-link-exact-active {
  color: rgb(20 184 166);;
}

nav a.router-link-exact-active:hover {
  background-color: transparent;
}

nav a:first-of-type {
  border: 0;
}
</style>