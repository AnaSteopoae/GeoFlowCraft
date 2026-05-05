<template>
    <Dialog 
        v-model:visible="visible" 
        modal 
        :header="dialogTitle"
        :style="{ width: '50rem' }"
        :breakpoints="{ '1199px': '75vw', '575px': '90vw' }"
        @hide="close"
    >
        <div class="processing-results-dialog">
            <!-- Loading state -->
            <div v-if="isLoading" class="loading-container">
                <ProgressSpinner />
                <p>Loading results...</p>
            </div>

            <!-- Results list -->
            <div v-else-if="results && results.length > 0" class="results-list">
                <Message severity="success" :closable="false">
                    <div class="success-message">
                        <i class="pi pi-check-circle"></i>
                        <span>Processing completed successfully! {{ results.length }} file(s) generated.</span>
                    </div>
                </Message>

                <div class="product-info" v-if="productId">
                    <h3>Product: {{ productId }}</h3>
                    <p class="text-muted">Generated on {{ formatDate(timestamp) }}</p>
                </div>

                <DataTable 
                    :value="results" 
                    :paginator="results.length > 10"
                    :rows="10"
                    class="results-table"
                    responsiveLayout="scroll"
                >
                    <Column v-if="!productId" field="productId" header="Product ID" :sortable="true">
                        <template #body="slotProps">
                            <span class="filename">{{ slotProps.data.productId?.substring(0, 40) }}...</span>
                        </template>
                    </Column>

                    <Column field="type" header="Type" :sortable="true">
                        <template #body="slotProps">
                            <Tag 
                                :value="slotProps.data.type" 
                                :severity="getTypeSeverity(slotProps.data.type)"
                            />
                        </template>
                    </Column>

                    <Column field="filename" header="Filename" :sortable="true">
                        <template #body="slotProps">
                            <span class="filename">{{ slotProps.data.filename }}</span>
                        </template>
                    </Column>

                    <Column field="size" header="Size" :sortable="true">
                        <template #body="slotProps">
                            {{ formatFileSize(slotProps.data.size) }}
                        </template>
                    </Column>

                    <Column field="modifiedAt" header="Modified" :sortable="true">
                        <template #body="slotProps">
                            {{ formatDateTime(slotProps.data.modifiedAt) }}
                        </template>
                    </Column>

                    <Column header="Actions">
                        <template #body="slotProps">
                            <Button 
                                icon="pi pi-download" 
                                class="p-button-sm p-button-success"
                                @click="downloadFile(slotProps.data)"
                                v-tooltip.top="'Download GeoTIFF'"
                            />
                        </template>
                    </Column>
                </DataTable>
            </div>

            <!-- No results -->
            <div v-else class="no-results">
                <Message severity="warn" :closable="false">
                    <div class="warning-message">
                        <i class="pi pi-exclamation-triangle"></i>
                        <span>No results found for this product.</span>
                    </div>
                </Message>
                <p class="text-muted">
                    The processing may still be in progress, or the output files were not generated.
                </p>
            </div>
        </div>
    </Dialog>
</template>

<script>
import { ref, computed, watch } from 'vue';
import Dialog from 'primevue/dialog';
import Button from 'primevue/button';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import useAIAgentStore from '@/stores/aiAgent';
import { useToast } from 'primevue/usetoast';
import moment from 'moment';

export default {
    name: 'AppProcessingResultsDialog',
    components: {
        Dialog,
        Button,
        DataTable,
        Column,
        Tag,
        Message,
        ProgressSpinner
    },
    props: {
        modelValue: {
            type: Boolean,
            default: false
        },
        productId: {
            type: String,
            default: null
        }
    },
    emits: ['update:modelValue'],
    setup(props, { emit }) {
        const toast = useToast();
        const aiAgentStore = useAIAgentStore();

        const visible = computed({
            get: () => props.modelValue,
            set: (value) => emit('update:modelValue', value)
        });

        const isLoading = ref(false);
        const results = ref([]);
        const timestamp = ref(null);

        const dialogTitle = computed(() => {
            return props.productId 
                ? `Processing Results - ${props.productId.substring(0, 30)}...`
                : 'Processing Results';
        });

        // Watch for productId changes and load results
        watch(() => props.productId, async (newProductId) => {
            if (newProductId && props.modelValue) {
                await loadResults(newProductId);
            } else if (!newProductId && props.modelValue) {
                // Dacă nu e specificat productId, încarcă toate rezultatele
                await loadAllResults();
            }
        }, { immediate: true });

        watch(() => props.modelValue, async (newValue) => {
            if (newValue && props.productId) {
                await loadResults(props.productId);
            } else if (newValue && !props.productId) {
                await loadAllResults();
            }
        });

        const loadResults = async (productId) => {
            if (!productId) return;

            isLoading.value = true;
            try {
                const response = await aiAgentStore.loadProcessingResults(productId);
                
                if (response.success) {
                    results.value = response.results;
                    timestamp.value = new Date();
                } else {
                    results.value = [];
                    toast.add({
                        severity: 'warn',
                        summary: 'No Results',
                        detail: 'No processing results found for this product.',
                        life: 3000
                    });
                }
            } catch (error) {
                console.error('Error loading results:', error);
                toast.add({
                    severity: 'error',
                    summary: 'Error',
                    detail: 'Failed to load processing results.',
                    life: 3000
                });
                results.value = [];
            } finally {
                isLoading.value = false;
            }
        };
        
        const loadAllResults = async () => {
            isLoading.value = true;
            try {
                const response = await aiAgentStore.loadAllProcessingResults();
                
                if (response.success) {
                    // Flatten toate rezultatele într-un singur array
                    const allResults = [];
                    Object.keys(response.results).forEach(productId => {
                        response.results[productId].forEach(file => {
                            allResults.push({
                                ...file,
                                productId: productId
                            });
                        });
                    });
                    
                    results.value = allResults;
                    timestamp.value = new Date();
                } else {
                    results.value = [];
                    toast.add({
                        severity: 'warn',
                        summary: 'No Results',
                        detail: 'No processing results found.',
                        life: 3000
                    });
                }
            } catch (error) {
                console.error('Error loading all results:', error);
                toast.add({
                    severity: 'error',
                    summary: 'Error',
                    detail: 'Failed to load processing results.',
                    life: 3000
                });
                results.value = [];
            } finally {
                isLoading.value = false;
            }
        };

        const downloadFile = (fileData) => {
            const downloadUrl = aiAgentStore.getDownloadUrl(fileData.filename);
            
            // Creează un link temporar și declanșează descărcarea
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = fileData.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            toast.add({
                severity: 'info',
                summary: 'Download Started',
                detail: `Downloading ${fileData.filename}`,
                life: 3000
            });
        };

        const downloadAll = () => {
            results.value.forEach((fileData, index) => {
                setTimeout(() => {
                    downloadFile(fileData);
                }, index * 500); // Stagger downloads by 500ms
            });

            toast.add({
                severity: 'info',
                summary: 'Download All',
                detail: `Starting download of ${results.value.length} files`,
                life: 3000
            });
        };

        const viewOnMap = () => {
            // TODO: Implement map visualization
            toast.add({
                severity: 'info',
                summary: 'Coming Soon',
                detail: 'Map visualization feature will be available soon!',
                life: 3000
            });
        };

        const formatFileSize = (bytes) => {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        };

        const formatDate = (date) => {
            return moment(date).format('MMMM Do YYYY, h:mm:ss a');
        };

        const formatDateTime = (date) => {
            return moment(date).format('MMM D, YYYY HH:mm');
        };

        const close = () => {
            visible.value = false;
        };

        const getTypeSeverity = (type) => {
            const severities = {
                'Canopy Height': 'success',
                'Uncertainty (Std Dev)': 'info',
                'SR Fidelity': 'warning',
                'SR Balanced': 'warning', 
                'SR Sharp': 'warning',
                'SR Output': 'warning',
                'CVA Magnitude': 'danger',
                'Delta NDVI': 'danger',
                'Change Mask': 'danger',
                'CD Results Archive': 'contrast',
                'Delta CHM': 'contrast',
                'Deforestation Mask': 'danger',
                'Regrowth Mask': 'success',
                'Change Classification': 'info'
            };
            return severities[type] || 'secondary';
        };

        return {
            visible,
            isLoading,
            results,
            timestamp,
            dialogTitle,
            downloadFile,
            downloadAll,
            viewOnMap,
            formatFileSize,
            formatDate,
            formatDateTime,
            close,
            getTypeSeverity
        };
    }
};
</script>

<style lang="scss" scoped>
.processing-results-dialog {
    min-height: 300px;

    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3rem;
        gap: 1rem;

        p {
            color: var(--text-color-secondary);
            margin: 0;
        }
    }

    .results-list {
        .success-message,
        .warning-message {
            display: flex;
            align-items: center;
            gap: 0.75rem;

            i {
                font-size: 1.25rem;
            }
        }

        .product-info {
            margin: 1.5rem 0;
            padding: 1rem;
            background: var(--surface-50);
            border-radius: 6px;

            h3 {
                margin: 0 0 0.5rem 0;
                font-size: 1rem;
                color: var(--text-color);
                word-break: break-all;
            }

            .text-muted {
                margin: 0;
                font-size: 0.875rem;
                color: var(--text-color-secondary);
            }
        }

        .results-table {
            margin: 1rem 0;

            .filename {
                font-family: 'Courier New', monospace;
                font-size: 0.875rem;
                word-break: break-all;
            }
        }

        .actions-footer {
            display: flex;
            gap: 1rem;
            justify-content: flex-end;
            margin-top: 1.5rem;
            padding-top: 1rem;
            border-top: 1px solid var(--surface-border);
        }
    }

    .no-results {
        padding: 2rem;
        text-align: center;

        .text-muted {
            margin-top: 1rem;
            color: var(--text-color-secondary);
        }
    }
}
</style>
