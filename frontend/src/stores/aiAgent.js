import { defineStore } from "pinia";
import aiService from "@/services/aiService";

export default defineStore('aiAgent', {
    state: () => ({
        availableAgents: [],
        selectedAgent: null,
        isLoading: false,
        error: null,
        processingResults: {}, // { productId: { results: [], timestamp: Date } }
        lastProcessedProduct: null
    }),
    getters: {
        /**
         * Returnează agentul selectat cu toate detaliile
         */
        getSelectedAgent: (state) => {
            return state.availableAgents.find(agent => agent.id === state.selectedAgent);
        },
        
        /**
         * Verifică dacă există agenți disponibili
         */
        hasAgents: (state) => {
            return state.availableAgents.length > 0;
        },
        
        /**
         * Returnează rezultatele pentru un produs specific
         */
        getResultsForProduct: (state) => (productId) => {
            return state.processingResults[productId] || null;
        },
        
        /**
         * Verifică dacă există rezultate pentru ultimul produs procesat
         */
        hasLastResults: (state) => {
            return state.lastProcessedProduct && 
                   state.processingResults[state.lastProcessedProduct] !== undefined;
        }
    },
    actions: {
        /**
         * Încarcă lista de agenți AI disponibili
         */
        async loadAvailableAgents() {
            this.isLoading = true;
            this.error = null;
            
            try {
                const response = await aiService.getAvailableAgents();
                
                if (response.success) {
                    this.availableAgents = response.agents;
                    
                    // Selectează primul agent by default dacă există
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
        
        /**
         * Setează agentul selectat
         */
        setSelectedAgent(agentId) {
            this.selectedAgent = agentId;
        },
        
        /**
         * Verifică starea de sănătate a unui agent
         */
        async checkAgentHealth(agentId) {
            try {
                const response = await aiService.checkAgentHealth(agentId);
                return response.health;
            } catch (error) {
                console.error(`Eroare la verificarea health pentru ${agentId}:`, error);
                return { available: false, error: error.message };
            }
        },
        
        /**
         * Procesează date cu agentul selectat
         */
        async processWithSelectedAgent(inputData) {
            if (!this.selectedAgent) {
                throw new Error('Niciun agent selectat');
            }
            
            try {
                const response = await aiService.processWithAgent(this.selectedAgent, inputData);
                return response;
            } catch (error) {
                console.error('Eroare la procesarea cu AI:', error);
                throw error;
            }
        },
        
        /**
         * Încarcă rezultatele procesării pentru un produs specific
         */
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
        
        /**
         * Încarcă toate rezultatele disponibile
         */
        async loadAllProcessingResults() {
            this.isLoading = true;
            try {
                const response = await aiService.getAllProcessingResults();
                
                if (response.success) {
                    // Actualizează state-ul cu toate rezultatele
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
        
        /**
         * Obține URL-ul de descărcare pentru un fișier rezultat
         */
        getDownloadUrl(filename) {
            return aiService.getDownloadUrl(filename);
        },
        
        /**
         * Șterge rezultatele din cache pentru un produs
         */
        clearResultsForProduct(productId) {
            delete this.processingResults[productId];
            if (this.lastProcessedProduct === productId) {
                this.lastProcessedProduct = null;
            }
        }
    }
});
