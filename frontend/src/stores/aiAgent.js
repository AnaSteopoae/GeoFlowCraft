import { defineStore } from "pinia";
import aiService from "@/services/aiService";

export default defineStore('aiAgent', {
    state: () => ({
        availableAgents: [],
        selectedAgent: null,
        isLoading: false,
        error: null,
        processingResults: {},
        lastProcessedProduct: null,
        // SR-specific state
        srModes: null,          // { presets: {...}, custom_alpha: {...} }
        selectedSRMode: 'balanced',
        customAlpha: null       // null = folosește preset, 0.0-1.0 = custom
    }),
    getters: {
        getSelectedAgent: (state) => {
            return state.availableAgents.find(agent => agent.id === state.selectedAgent);
        },
        
        hasAgents: (state) => {
            return state.availableAgents.length > 0;
        },
        
        getResultsForProduct: (state) => (productId) => {
            return state.processingResults[productId] || null;
        },
        
        hasLastResults: (state) => {
            return state.lastProcessedProduct && 
                   state.processingResults[state.lastProcessedProduct] !== undefined;
        },

        /**
         * Verifică dacă agentul selectat este SR
         */
        isSRSelected: (state) => {
            return state.selectedAgent === 'sr-processor';
        },

        /**
         * Returnează preseturile SR ca array pentru dropdown
         */
        srPresetOptions: (state) => {
            if (!state.srModes?.presets) return [];
            return Object.keys(state.srModes.presets).map(key => ({
                id: key,
                name: key.charAt(0).toUpperCase() + key.slice(1),
                description: state.srModes.presets[key].description,
                alpha: state.srModes.presets[key].alpha
            }));
        }
    },
    actions: {
        async loadAvailableAgents() {
            this.isLoading = true;
            this.error = null;
            
            try {
                const response = await aiService.getAvailableAgents();
                
                if (response.success) {
                    this.availableAgents = response.agents;
                    
                    if (this.availableAgents.length > 0 && !this.selectedAgent) {
                        this.selectedAgent = this.availableAgents[0].id;
                    }
                }
            } catch (error) {
                this.error = error.message;
                console.error('Eroare la încărcarea agenților AI:', error);
            } finally {
                this.isLoading = false;
            }
        },
        
        setSelectedAgent(agentId) {
            this.selectedAgent = agentId;
            
            // Dacă SR e selectat, încarcă modurile disponibile
            if (agentId === 'sr-processor' && !this.srModes) {
                this.loadSRModes();
            }
        },
        
        /**
         * Încarcă modurile SR de la serviciu
         */
        async loadSRModes() {
            try {
                const response = await aiService.getSRModes();
                if (response.success) {
                    this.srModes = response.modes;
                }
            } catch (error) {
                console.error('Eroare la încărcarea modurilor SR:', error);
                // Fallback: moduri hardcodate
                this.srModes = {
                    presets: {
                        fidelity: { alpha: 0.0, description: 'Maximum spectral fidelity (PSNR). Best for NDVI, change detection.' },
                        balanced: { alpha: 0.9, description: 'Best balance between fidelity and sharpness.' },
                        sharp: { alpha: 1.0, description: 'Sharpest edges, lowest blur. For visual inspection.' }
                    },
                    custom_alpha: { min: 0.0, max: 1.0, step: 0.05 }
                };
            }
        },

        /**
         * Setează modul SR selectat
         */
        setSRMode(mode) {
            this.selectedSRMode = mode;
            this.customAlpha = null; // resetează alpha custom
        },

        /**
         * Setează alpha custom (suprascrie preset)
         */
        setCustomAlpha(alpha) {
            this.customAlpha = alpha;
        },

        async checkAgentHealth(agentId) {
            try {
                const response = await aiService.checkAgentHealth(agentId);
                return response.health;
            } catch (error) {
                console.error(`Eroare la verificarea health pentru ${agentId}:`, error);
                return { available: false, error: error.message };
            }
        },
        
        async processWithSelectedAgent(inputData) {
            if (!this.selectedAgent) {
                throw new Error('Niciun agent selectat');
            }
            
            try {
                // Dacă SR, adaugă mode și alpha la inputData
                if (this.selectedAgent === 'sr-processor') {
                    inputData.mode = this.selectedSRMode;
                    if (this.customAlpha !== null) {
                        inputData.alpha = this.customAlpha;
                    }
                }

                const response = await aiService.processWithAgent(this.selectedAgent, inputData);
                return response;
            } catch (error) {
                console.error('Eroare la procesarea cu AI:', error);
                throw error;
            }
        },
        
        async loadProcessingResults(productId) {
            this.isLoading = true;
            try {
                const response = await aiService.getProcessingResults(productId);
                
                if (response.success) {
                    this.processingResults[productId] = {
                        results: response.results,
                        timestamp: new Date(),
                        count: response.count
                    };
                    this.lastProcessedProduct = productId;
                }
                
                return response;
            } catch (error) {
                console.error(`Eroare la încărcarea rezultatelor pentru ${productId}:`, error);
                throw error;
            } finally {
                this.isLoading = false;
            }
        },
        
        async loadAllProcessingResults() {
            this.isLoading = true;
            try {
                const response = await aiService.getAllProcessingResults();
                
                if (response.success) {
                    this.processingResults = {};
                    Object.keys(response.results).forEach(productId => {
                        this.processingResults[productId] = {
                            results: response.results[productId],
                            timestamp: new Date(),
                            count: response.results[productId].length
                        };
                    });
                }
                
                return response;
            } catch (error) {
                console.error('Eroare la încărcarea tuturor rezultatelor:', error);
                throw error;
            } finally {
                this.isLoading = false;
            }
        },
        
        getDownloadUrl(filename) {
            return aiService.getDownloadUrl(filename);
        },
        
        clearResultsForProduct(productId) {
            delete this.processingResults[productId];
            if (this.lastProcessedProduct === productId) {
                this.lastProcessedProduct = null;
            }
        }
    }
});